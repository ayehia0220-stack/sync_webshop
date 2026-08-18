# -*- coding: utf-8 -*-
"""
تربو — creating and tracking shipments.

The shop never has to open Turbo's dashboard: a submitted order becomes a
shipment here, and Turbo posts status changes back onto the Sales Order.

Two things this deliberately does not do:

  * it never raises into the order flow. A courier being down must not stop a
    customer buying coffee — the failure is recorded on the order and the
    shipment can be created again with the button.
  * it never invents an address. Turbo rejects an unknown area outright, so the
    checkout only ever offers areas Turbo itself listed.
"""
import json

import frappe
import requests
from frappe.utils import now_datetime

TIMEOUT = 30
# Cloudflare sits in front of Turbo and rejects the default python agent.
HEADERS = {"Accept": "application/json", "User-Agent": "dpono-shop/1.0"}


def _settings():
	return frappe.get_single("Webshop Turbo Settings")


def _credentials(settings=None):
	settings = settings or _settings()
	key = settings.get_password("authentication_key", raise_exception=False)
	if not settings.enabled or not key or not settings.main_client_code:
		return None
	return frappe._dict({
		"key": key,
		"client": settings.main_client_code,
		"base": (settings.base_url or "https://platform.turbo.info").rstrip("/"),
		"settings": settings,
	})


def _call(path, payload, creds):
	"""One POST. Returns (ok, data_or_message) and never raises."""
	try:
		res = requests.post(
			creds.base + path,
			json=dict(payload, authentication_key=creds.key,
			          main_client_code=creds.client),
			headers=HEADERS, timeout=TIMEOUT)
	except Exception as exc:
		return False, "connection: %s" % str(exc)[:200]

	try:
		data = res.json()
	except ValueError:
		return False, "HTTP %s: %s" % (res.status_code, res.text[:200])

	if not data.get("success"):
		return False, data.get("message") or ("HTTP %s" % res.status_code)
	return True, data


def _order_summary(order):
	"""What is in the box, in the words the courier will read out."""
	parts = []
	for row in order.items[:6]:
		name = (row.item_name or row.item_code or "").strip()
		parts.append("%s x%g" % (name[:40], row.qty))
	if len(order.items) > 6:
		parts.append("+%d" % (len(order.items) - 6))
	return " / ".join(parts)[:250]


def _weight(order, settings):
	total = 0.0
	for row in order.items:
		per = frappe.db.get_value("Item", row.item_code, "weight_per_unit") or 0
		total += float(per) * float(row.qty or 0)
	return round(total, 2) or float(settings.default_weight or 1)


def _address(order):
	if not order.shipping_address_name:
		return None
	return frappe.get_doc("Address", order.shipping_address_name)


def _map_note(addr, settings):
	"""
	Turbo's own "الموقع" box is not exposed by the API, so the pin travels as a
	link inside the notes where the captain can still tap it.
	"""
	if not settings.send_map_link:
		return ""
	lat, lng = addr.get("latitude"), addr.get("longitude")
	if not lat or not lng:
		return ""
	return "\u0627\u0644\u0645\u0648\u0642\u0639: https://maps.google.com/?q=%s,%s" % (lat, lng)


def build_payload(order, creds):
	settings = creds.settings
	addr = _address(order)
	if not addr:
		return None, "\u0627\u0644\u0637\u0644\u0628 \u0645\u0641\u064a\u0647\u0648\u0634 \u0639\u0646\u0648\u0627\u0646 \u0634\u062d\u0646"

	# Nobody ships on a number nobody read.
	if not order.get("turbo_cod_confirmed"):
		return None, "علّم على مراجعة مبلغ التحصيل الأول"

	pieces = [order.get("webshop_customer_note") or ""]
	link = _map_note(addr, settings)
	if link and settings.map_link_field == "notes":
		pieces.append(link)
	notes = " | ".join(p for p in pieces if p)[:250]

	line1 = addr.address_line1 or ""
	if link and settings.map_link_field == "address":
		line1 = (line1 + " | " + link)[:250]

	# customer_name is the phone whenever the customer was matched by phone, so
	# the name the shopper actually typed — kept on the address — comes first.
	receiver = (addr.address_title or "").replace(" - Web", "").strip()
	if not receiver or receiver.startswith("+"):
		receiver = order.customer_name or order.customer

	payload = {
		"receiver": receiver,
		"phone1": order.get("custom_mobile_phone") or addr.phone or "",
		"phone2": order.get("webshop_phone_alt") or None,
		"government": addr.city or "",
		"area": addr.address_line2 or "",
		"address": line1,
		"notes": notes,
		"order_summary": _order_summary(order),
		"number_of_items": int(sum(row.qty for row in order.items) or 1),
		"weight": _weight(order, settings),
		"invoice_number": order.name,
		"remote_order_id": order.name,
		# Collect unless the order is provably paid already. The payment method
		# is free text ("Cash on Delivery", "cod", …) and cannot be matched
		# reliably, so the paid flag is what decides.
		# The balance, not the order value — see amount_still_owed.
		# What the desk reviewed and saved, not a fresh calculation — a
		# deliberate correction has to survive the trip.
		"amount_to_be_collected": float(
			order.get("turbo_cod_amount") or amount_still_owed(order)),
		"is_order": 0,
		"is_fragile": 1 if settings.is_fragile else 0,
		"can_open": 1 if settings.allow_open else 0,
		# 1 tells Turbo the customer collects from a point rather than the door.
		"delivery_type": 1 if _is_pickup(addr) else 0,
	}
	return payload, None


def _is_pickup(addr):
	"""Whether Turbo serves this area from a collection point."""
	try:
		from sync_webshop.api.regions import get_regions
		for gov in get_regions():
			if gov["governorate"] != (addr.city or ""):
				continue
			for area in gov["areas"]:
				if area["name"] == (addr.address_line2 or ""):
					return bool(area.get("pickup"))
	except Exception:
		pass
	return False


@frappe.whitelist()
def create_shipment(order_name):
	"""Hand one order to Turbo. Safe to call twice — it will not duplicate."""
	order = frappe.get_doc("Sales Order", order_name)
	if order.docstatus != 1:
		frappe.throw(frappe._("\u0623\u0643\u0651\u062f \u0627\u0644\u0637\u0644\u0628 \u0627\u0644\u0623\u0648\u0644."))
	if order.get("turbo_order_number"):
		return {"ok": True, "already": True,
		        "order_number": order.turbo_order_number}

	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\u0641\u0639\u0651\u0644 \u062a\u0631\u0628\u0648 \u0648\u062d\u0637 \u0627\u0644\u0645\u0641\u062a\u0627\u062d \u0627\u0644\u0623\u0648\u0644."))

	payload, err = build_payload(order, creds)
	if err:
		order.db_set("turbo_error", err, update_modified=False)
		return {"ok": False, "message": err}

	ok, result = _call("/external-api/add-order", payload, creds)
	if not ok:
		order.db_set("turbo_error", str(result)[:500], update_modified=False)
		creds.settings.db_set("last_error", str(result)[:500], update_modified=False)
		return {"ok": False, "message": result}

	# Turbo replies {"result": {"code": …, "bar_code": …, "expected_branch": …}}.
	feed = result.get("result") or result.get("feed") or result.get("data") or {}
	number = feed.get("code") or feed.get("bar_code") or feed.get("order_number")
	if not number:
		msg = "Turbo accepted the order but returned no code: %s" % str(result)[:300]
		order.db_set("turbo_error", msg, update_modified=False)
		frappe.log_error(title="Turbo add-order without code", message=msg)
		return {"ok": False, "message": msg}

	order.db_set({
		"turbo_order_number": str(number),
		# The waybill print button predates this integration and reads the
		# older field; leaving it empty switched that button off.
		"custom_turbo_tracking_code": str(number),
		"turbo_cod_amount": payload.get("amount_to_be_collected") or 0,
		"turbo_branch": (feed.get("expected_branch") or "")[:140] or None,
		"turbo_error": None,
		"turbo_last_sync": now_datetime(),
	}, update_modified=False)
	creds.settings.db_set("last_sync", now_datetime(), update_modified=False)
	frappe.db.commit()
	return {"ok": True, "order_number": number}


@frappe.whitelist()
def cancel_shipment(order_name):
	order = frappe.get_doc("Sales Order", order_name)
	number = order.get("turbo_order_number")
	if not number:
		frappe.throw(frappe._("\u0645\u0641\u064a\u0634 \u0634\u062d\u0646\u0629 \u0644\u0644\u0637\u0644\u0628 \u062f\u0647."))

	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\u062a\u0631\u0628\u0648 \u0645\u0642\u0641\u0648\u0644."))

	ok, result = _call("/external-api/canceled", {"id": number, "type": 1}, creds)
	if not ok:
		return {"ok": False, "message": result}

	order.db_set({"turbo_status_text": frappe._("\u0645\u0644\u063a\u064a\u0629"),
	              "turbo_last_sync": now_datetime()}, update_modified=False)
	frappe.db.commit()
	return {"ok": True}


def _apply_status(order_name, data):
	"""Write whatever Turbo reported onto the order."""
	fields = {
		"turbo_status_text": (data.get("status_text") or "")[:140] or None,
		"turbo_status_code": data.get("status"),
		"turbo_delivery_date": data.get("delivery_date") or None,
		"turbo_captain_name": (data.get("captain_name") or "")[:140] or None,
		"turbo_captain_phone": (data.get("captain_number1") or "")[:140] or None,
		"turbo_branch": (data.get("branch_name") or "")[:140] or None,
		"turbo_delay_reason": (data.get("delay_reason") or "")[:500] or None,
		"turbo_return_reason": (data.get("return_reason") or "")[:500] or None,
		"turbo_last_sync": now_datetime(),
	}
	if data.get("order_number"):
		fields["turbo_order_number"] = str(data["order_number"])[:140]
	frappe.db.set_value("Sales Order", order_name, fields, update_modified=False)


@frappe.whitelist(allow_guest=True)
def status_webhook():
	"""
	Where Turbo posts a status change.

	Guest-callable by necessity — Turbo cannot log in. The order is found by the
	id we gave them, and an optional shared secret can be required, so a
	stranger cannot rewrite an order's status by guessing.
	"""
	settings = _settings()
	secret = settings.get_password("webhook_secret", raise_exception=False)
	if secret:
		sent = (frappe.get_request_header("X-Webhook-Secret")
		        or frappe.form_dict.get("secret") or "")
		if sent != secret:
			frappe.local.response["http_status_code"] = 401
			return {"success": False, "message": "unauthorized"}

	data = frappe.local.form_dict or {}
	if frappe.request and frappe.request.data:
		try:
			data = json.loads(frappe.request.data) or data
		except Exception:
			pass

	order_name = data.get("remote_order_id") or data.get("invoice_number")
	if not order_name or not frappe.db.exists("Sales Order", order_name):
		# Fall back to the tracking number, in case remote_order_id was dropped.
		number = data.get("order_number")
		order_name = number and frappe.db.get_value(
			"Sales Order", {"turbo_order_number": str(number)}, "name")
	if not order_name:
		frappe.local.response["http_status_code"] = 404
		return {"success": False, "message": "order not found"}

	_apply_status(order_name, data)
	frappe.db.commit()
	return {"success": True}


def poll_statuses():
	"""
	Scheduled catch-up.

	The webhook is the fast path; this exists because a webhook that silently
	stops is invisible otherwise, and the shop would show stale statuses without
	knowing.
	"""
	creds = _credentials()
	if not creds:
		return

	from frappe.utils import add_days, nowdate
	ok, result = _call("/external-api/get-status", {
		"from": add_days(nowdate(), -30), "to": nowdate(),
	}, creds)
	if not ok:
		creds.settings.db_set("last_error", str(result)[:500], update_modified=False)
		return

	for row in (result.get("feed") or []):
		name = row.get("remote_order_id") or row.get("invoice_number")
		if name and frappe.db.exists("Sales Order", name):
			_apply_status(name, row)

	creds.settings.db_set("last_sync", now_datetime(), update_modified=False)
	frappe.db.commit()


def on_order_submit(doc, method=None):
	"""Create the shipment when an order is confirmed, if that is switched on."""
	settings = _settings()
	if not settings.enabled or not settings.auto_create:
		return
	try:
		create_shipment(doc.name)
	except Exception as exc:
		# The sale already happened; a courier problem must not undo it.
		frappe.log_error(title="Turbo auto-create failed",
		                 message="%s\n%s" % (doc.name, str(exc)[:400]))


@frappe.whitelist()
def refresh_status(order_name):
	"""Ask Turbo about one order now, for the button on the form."""
	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\u062a\u0631\u0628\u0648 \u0645\u0642\u0641\u0648\u0644."))

	number = frappe.db.get_value("Sales Order", order_name, "turbo_order_number")
	if not number:
		frappe.throw(frappe._("\u0645\u0641\u064a\u0634 \u0634\u062d\u0646\u0629 \u0644\u0644\u0637\u0644\u0628 \u062f\u0647."))

	ok, result = _call("/external-api/search-order",
	                   {"search_Key": str(number)}, creds)
	if not ok:
		return {"ok": False, "message": result}

	rows = result.get("result") or result.get("feed") or []
	if isinstance(rows, dict):
		rows = [rows]
	if not rows:
		return {"ok": False, "message": "not found at Turbo"}

	_apply_status(order_name, rows[0])
	frappe.db.commit()
	return {"ok": True}


def on_preparation_status(doc, method=None):
	"""
	Create the Turbo shipment when the desk marks the order as shipped.

	Guarded three ways: the setting has to be on, the order has to be submitted,
	and it must not already carry a waybill — a status re-saved twice would
	otherwise book the same parcel twice.
	"""
	if doc.get("custom_preparation_status") != "\u062a\u0645 \u0639\u0645\u0644 \u0627\u0644\u0634\u062d\u0646\u0647":
		return
	if doc.docstatus != 1 or doc.get("turbo_order_number"):
		return

	try:
		settings = frappe.get_single("Webshop Turbo Settings")
	except Exception:
		return
	if not settings.get("enabled") or not settings.get("auto_create"):
		return

	from sync_webshop.api.turbo import create_shipment

	result = create_shipment(doc.name)
	if result.get("ok"):
		frappe.msgprint(
			frappe._("\u062a\u0645 \u0639\u0645\u0644 \u0627\u0644\u0634\u062d\u0646\u0629 \u2014 ") + str(result.get("order_number")),
			indicator="green", alert=True)
	else:
		# Loud on purpose: a silent failure here means the desk believes the
		# parcel is booked when Turbo never heard about it.
		frappe.msgprint(
			frappe._("\u062a\u0631\u0628\u0648 \u0631\u0641\u0636 \u0627\u0644\u0634\u062d\u0646\u0629") + ": " + str(result.get("message")),
			indicator="red", title=frappe._("\u0627\u0644\u0634\u062d\u0646\u0629 \u0645\u0627\u062a\u0645\u062a\u0634"))


def amount_still_owed(order):
	"""
	What the courier should collect at the door.

	Counts money received three ways, because the shop uses all three: an
	advance recorded on the order, payments allocated to it, and payments
	against an invoice raised from it. Anything already in hand must not be
	asked for twice.
	"""
	total = float(order.grand_total or 0)

	# 1. Marked paid by the storefront (card, wallet).
	if str(order.get("webshop_payment_status") or "").strip().lower() in ("paid", "\u0645\u062f\u0641\u0648\u0639"):
		return 0.0

	# 2. ERPNext keeps advances against the order here.
	received = float(order.get("advance_paid") or 0)

	# 3. Payments settled against invoices raised from this order.
	invoiced = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(si.grand_total - si.outstanding_amount), 0)
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND sii.sales_order = %s
		""",
		order.name,
	)[0][0]

	# Rounding between an invoice total and its outstanding balance can make
	# this negative; treat that as "nothing received" rather than a credit.
	received += max(float(invoiced or 0), 0.0)

	owed = total - received
	# Between zero and the order value, whatever the arithmetic says.
	return round(min(max(owed, 0.0), total), 2)


# ============================================================================
# عنوان العميل — filled from the customer record
# ============================================================================

def _preferred_address(customer):
	"""
	The address to put on the order.

	Shipping beats billing because this field is what the courier reads, and
	the primary flag beats the rest. Falls back to whatever exists rather than
	leaving the field empty.
	"""
	rows = frappe.db.sql(
		"""
		SELECT a.name, a.address_type, a.is_primary_address, a.is_shipping_address
		FROM `tabAddress` a
		JOIN `tabDynamic Link` dl ON dl.parent = a.name AND dl.parenttype = 'Address'
		WHERE dl.link_doctype = 'Customer' AND dl.link_name = %s
		  AND IFNULL(a.disabled, 0) = 0
		ORDER BY a.is_shipping_address DESC, a.is_primary_address DESC, a.modified DESC
		LIMIT 1
		""",
		customer, as_dict=True)
	return rows[0].name if rows else None


def format_address(address_name):
	"""One readable line: street, area, city."""
	if not address_name:
		return ""
	addr = frappe.db.get_value(
		"Address", address_name,
		["address_line1", "address_line2", "city"], as_dict=True)
	if not addr:
		return ""
	parts = [(addr.address_line1 or "").strip(),
	         (addr.address_line2 or "").strip(),
	         (addr.city or "").strip()]
	# "-" is what the checkout writes when a city is unknown; it reads as noise.
	return " - ".join(p for p in parts if p and p != "-")


@frappe.whitelist()
def address_for_customer(customer):
	"""Called by the form the moment a customer is chosen."""
	if not customer:
		return {"address": ""}
	text = format_address(_preferred_address(customer))
	return {"address": text or _address_from_last_order(customer)}


def fill_customer_address(doc, method=None):
	"""Fill the field on save, but never over something a person typed."""
	if doc.get("custom_address_for_customer_"):
		return
	if not doc.get("customer"):
		return

	# An address already chosen on the order is more specific than the
	# customer's default, so it wins.
	source = doc.get("shipping_address_name") or doc.get("customer_address") \
		or _preferred_address(doc.customer)
	text = format_address(source) or _address_from_last_order(doc.customer, doc.name)
	if text:
		doc.custom_address_for_customer_ = text[:140]


def _address_from_last_order(customer, exclude=None):
	"""The address typed on this customer's most recent order."""
	rows = frappe.db.sql(
		"""
		SELECT custom_address_for_customer_ AS addr
		FROM `tabSales Order`
		WHERE customer = %(customer)s
		  AND IFNULL(custom_address_for_customer_, '') != ''
		  AND name != %(exclude)s
		ORDER BY creation DESC
		LIMIT 1
		""",
		{"customer": customer, "exclude": exclude or ""}, as_dict=True)
	if not rows:
		return ""
	text = (rows[0].addr or "").strip()
	return text if _looks_like_address(text) else ""


def _looks_like_address(text):
	"""
	Enough to route a courier by.

	Not a validator — just a filter against the placeholders sitting in old
	records ("..", "تجديد"). An address has some length and more than one word.
	"""
	text = (text or "").strip()
	if len(text) < 10:
		return False
	if len(text.split()) < 2:
		return False
	# Mostly punctuation or digits is not a place.
	letters = sum(1 for ch in text if ch.isalpha())
	return letters >= 6


def check_cod_amount(doc, method=None):
	"""
	Keep the collection amount honest.

	Empty means nobody has set it, so it takes the computed balance. A number
	below that balance is refused — raising it is a business call (a surcharge,
	a rounding up), lowering it is money the shop will not see.
	"""
	if doc.docstatus == 2:
		return

	expected = amount_still_owed(doc)
	current = doc.get("turbo_cod_amount")

	if current in (None, ""):
		doc.turbo_cod_amount = expected
		return

	if float(current) < expected - 0.01:
		frappe.throw(
			frappe._(
				"\u0627\u0644\u0645\u0637\u0644\u0648\u0628 \u062a\u062d\u0635\u064a\u0644\u0647 \u0645\u0627\u064a\u0646\u0641\u0639\u0634 \u064a\u0642\u0644 \u0639\u0646 {0}. "
				"\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a {1} \u0646\u0627\u0642\u0635 \u0627\u0644\u0645\u062f\u0641\u0648\u0639 {2}."
			).format(
				frappe.format_value(expected, {"fieldtype": "Currency"}),
				frappe.format_value(doc.grand_total or 0, {"fieldtype": "Currency"}),
				frappe.format_value((doc.grand_total or 0) - expected, {"fieldtype": "Currency"}),
			),
			title=frappe._("\u0645\u0628\u0644\u063a \u0627\u0644\u062a\u062d\u0635\u064a\u0644"),
		)


@frappe.whitelist()
def expected_cod(order_name):
	"""The floor for this order, for the form to show and default to."""
	order = frappe.get_doc("Sales Order", order_name)
	return {"owed": amount_still_owed(order)}


# ============================================================================
# بيانات العميل على الفاتورة
# ============================================================================

def _source_order(doc):
	"""The sales order this invoice came from, if any."""
	for row in doc.get("items") or []:
		if row.get("sales_order"):
			return row.sales_order
	return None


def fill_invoice_contact(doc, method=None):
	"""Phone and address on the invoice, from wherever they actually exist."""
	want_phone = not (doc.get("custom_customer_phone_number") or "").strip()
	want_addr = not (doc.get("custom_address_for_customer_") or "").strip()
	if not (want_phone or want_addr) or not doc.get("customer"):
		return

	phone = addr = ""

	order = _source_order(doc)
	if order:
		row = frappe.db.get_value(
			"Sales Order", order,
			["custom_customer_phone_number", "custom_address_for_customer_"],
			as_dict=True) or {}
		phone = (row.get("custom_customer_phone_number") or "").strip()
		candidate = (row.get("custom_address_for_customer_") or "").strip()
		# Same bar as everywhere else — a placeholder is not an address.
		addr = candidate if _looks_like_address(candidate) else ""

	if not addr:
		addr = format_address(_preferred_address(doc.customer))
	if not addr:
		addr = _address_from_last_order(doc.customer)

	if not phone:
		phone = (frappe.db.get_value("Customer", doc.customer, "mobile_no") or "").strip()
	if not phone:
		# The most recent order that recorded one.
		rows = frappe.db.sql(
			"""
			SELECT custom_customer_phone_number AS p FROM `tabSales Order`
			WHERE customer = %s AND IFNULL(custom_customer_phone_number,'') != ''
			ORDER BY creation DESC LIMIT 1
			""",
			doc.customer, as_dict=True)
		phone = (rows[0].p or "").strip() if rows else ""

	if want_phone and phone:
		doc.custom_customer_phone_number = phone[:60]
	if want_addr and addr:
		doc.custom_address_for_customer_ = addr[:200]


# ============================================================================
# ترقيم المشاريع
# ============================================================================

def keep_project_series_ahead(doc, method=None):
	"""
	Stop the naming counter colliding with a name already in use.

	The counter lives apart from the documents, so a restore, an import, or a
	renamed project can leave it behind — and every new project then fails with
	"already exists". Nudging it past the highest number in use costs nothing
	and turns a blocking error into a gap in the sequence.
	"""
	import re

	prefix = (doc.get("naming_series") or "PROJ-.####").split(".")[0]
	rows = frappe.db.sql(
		"SELECT name FROM `tabProject` WHERE name LIKE %s", prefix + "%", as_dict=True)
	pattern = re.compile(r"^%s(\d+)$" % re.escape(prefix))
	used = [int(m.group(1)) for r in rows if (m := pattern.match(r.name or ""))]
	if not used:
		return

	current = frappe.db.sql(
		"SELECT current FROM `tabSeries` WHERE name = %s", prefix)
	current = current[0][0] if current else 0

	if current < max(used):
		frappe.db.sql(
			"UPDATE `tabSeries` SET current = %s WHERE name = %s", (max(used), prefix))


# ============================================================================
# رقم العميل — شكل واحد، ومحصلش تكرار
# ============================================================================

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩"
                              "۰۱۲۳۴۵۶۷۸۹",
                              "01234567890123456789")

# Accounts that share a line on purpose — a marketplace, not a person.
PHONE_EXEMPT = {"amazon", "noon"}


def normalise_customer_phone(value):
	"""One canonical form: 01XXXXXXXXX, or "" if it is not an Egyptian mobile."""
	import re as _re
	d = str(value or "").translate(ARABIC_DIGITS)
	d = _re.sub(r"\D", "", d)
	if d.startswith("0020"):
		d = d[4:]
	if d.startswith("20") and len(d) == 12:
		d = d[2:]
	if len(d) == 10 and d[0] == "1":
		d = "0" + d
	return d if _re.fullmatch(r"01[0-9]{9}", d) else ""


def enforce_unique_phone(doc, method=None):
	raw = (doc.get("mobile_no") or "").strip()
	if not raw:
		return

	clean = normalise_customer_phone(raw)
	if not clean:
		# Left as typed rather than rejected — some records hold two numbers in
		# one field, and refusing the save would block work over formatting.
		return

	doc.mobile_no = clean

	if (doc.get("customer_name") or "").strip().lower() in PHONE_EXEMPT:
		return

	other = frappe.db.sql(
		"""
		SELECT name, customer_name FROM `tabCustomer`
		WHERE mobile_no = %s AND name != %s LIMIT 1
		""",
		(clean, doc.name or ""), as_dict=True)
	if other:
		frappe.throw(
			frappe._("الرقم {0} مسجّل بالفعل للعميل: {1}")
			.format(clean, other[0].customer_name or other[0].name),
			title=frappe._("رقم مكرر"))
