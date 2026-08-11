# -*- coding: utf-8 -*-
"""Writes sync_webshop/api/turbo.py — the courier integration itself."""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"

SRC = u'''# -*- coding: utf-8 -*-
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
	return "\\u0627\\u0644\\u0645\\u0648\\u0642\\u0639: https://maps.google.com/?q=%s,%s" % (lat, lng)


def build_payload(order, creds):
	settings = creds.settings
	addr = _address(order)
	if not addr:
		return None, "\\u0627\\u0644\\u0637\\u0644\\u0628 \\u0645\\u0641\\u064a\\u0647\\u0648\\u0634 \\u0639\\u0646\\u0648\\u0627\\u0646 \\u0634\\u062d\\u0646"

	pieces = [order.get("webshop_customer_note") or ""]
	link = _map_note(addr, settings)
	if link and settings.map_link_field == "notes":
		pieces.append(link)
	notes = " | ".join(p for p in pieces if p)[:250]

	line1 = addr.address_line1 or ""
	if link and settings.map_link_field == "address":
		line1 = (line1 + " | " + link)[:250]

	payload = {
		"receiver": order.customer_name or order.customer,
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
		# Cash on delivery collects the full total; a prepaid order collects nothing.
		"amount_to_be_collected": (
			0 if (order.get("webshop_payment_method") or "cod") != "cod"
			else float(order.grand_total or 0)),
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
		frappe.throw(frappe._("\\u0623\\u0643\\u0651\\u062f \\u0627\\u0644\\u0637\\u0644\\u0628 \\u0627\\u0644\\u0623\\u0648\\u0644."))
	if order.get("turbo_order_number"):
		return {"ok": True, "already": True,
		        "order_number": order.turbo_order_number}

	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\\u0641\\u0639\\u0651\\u0644 \\u062a\\u0631\\u0628\\u0648 \\u0648\\u062d\\u0637 \\u0627\\u0644\\u0645\\u0641\\u062a\\u0627\\u062d \\u0627\\u0644\\u0623\\u0648\\u0644."))

	payload, err = build_payload(order, creds)
	if err:
		order.db_set("turbo_error", err, update_modified=False)
		return {"ok": False, "message": err}

	ok, result = _call("/external-api/add-order", payload, creds)
	if not ok:
		order.db_set("turbo_error", str(result)[:500], update_modified=False)
		creds.settings.db_set("last_error", str(result)[:500], update_modified=False)
		return {"ok": False, "message": result}

	feed = result.get("feed") or result.get("data") or {}
	number = (feed.get("order_number") or feed.get("code")
	          or feed.get("id") or result.get("id"))

	order.db_set({
		"turbo_order_number": str(number or ""),
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
		frappe.throw(frappe._("\\u0645\\u0641\\u064a\\u0634 \\u0634\\u062d\\u0646\\u0629 \\u0644\\u0644\\u0637\\u0644\\u0628 \\u062f\\u0647."))

	creds = _credentials()
	if not creds:
		frappe.throw(frappe._("\\u062a\\u0631\\u0628\\u0648 \\u0645\\u0642\\u0641\\u0648\\u0644."))

	ok, result = _call("/external-api/canceled", {"id": number, "type": 1}, creds)
	if not ok:
		return {"ok": False, "message": result}

	order.db_set({"turbo_status_text": frappe._("\\u0645\\u0644\\u063a\\u064a\\u0629"),
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
		                 message="%s\\n%s" % (doc.name, str(exc)[:400]))
'''


def execute():
	import frappe
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	io.open(P, "w", encoding="utf-8").write(SRC)

	# Referenced by build_payload; add it to the settings page.
	create_custom_fields({"Webshop Turbo Settings": [{
		"fieldname": "allow_open",
		"label": "العميل يقدر يفتح الشحنة قبل الدفع",
		"fieldtype": "Check",
		"default": "1",
		"insert_after": "is_fragile",
		"description": "بيوصل لتربو كـ can_open. أغلب عملاء مصر بيتوقعوا ده.",
	}]}, ignore_validate=True)

	settings = frappe.get_single("Webshop Turbo Settings")
	if settings.get("allow_open") is None:
		settings.allow_open = 1
		settings.flags.ignore_permissions = True
		settings.save()

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "turbo.poll_statuses" not in s and '"hourly"' in s:
		s = s.replace('"hourly": [', '"hourly": [\n\t\t"sync_webshop.api.turbo.poll_statuses",', 1)
		io.open(h, "w", encoding="utf-8").write(s)
		print("hooks: hourly poll")

	frappe.db.commit()
	frappe.clear_cache()
	print("TURBO API READY")
