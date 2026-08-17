# -*- coding: utf-8 -*-
"""
Order emails.

Everything a customer receives is driven by an Email Template in ERPNext, so
the wording is edited in the Desk, never here. Each message is sent at most
once per order — a resave, a background retry, or a double submit will not
send it twice.
"""
import requests

import frappe

CONFIRMATION_TEMPLATE = "Webshop Order Confirmation"
SHIPPED_TEMPLATE = "Webshop Order Shipped"


def _settings():
	return frappe.get_single("Webshop Content Settings")


def _store_name():
	return _settings().get("site_name") or "dpono"


def _reply_to():
	"""Where a customer's reply should land. Set in Webshop Content Settings."""
	address = (_settings().get("email_address") or "").strip()
	return address or None


def _recipient(sales_order):
	"""The address the shopper typed at checkout, falling back to their contact."""
	if sales_order.get("contact_email"):
		return sales_order.contact_email
	contact = frappe.db.sql(
		"""
		SELECT ce.email_id FROM `tabContact Email` ce
		JOIN `tabDynamic Link` dl ON dl.parent = ce.parent AND dl.parenttype = 'Contact'
		WHERE dl.link_doctype = 'Customer' AND dl.link_name = %s AND ce.email_id != ''
		ORDER BY ce.is_primary DESC LIMIT 1
		""",
		sales_order.customer,
	)
	return contact[0][0] if contact else None


def _context(sales_order):
	"""Values the template can use. Nothing here is invented — all from the order."""
	items = [
		{
			"item_name": row.item_name,
			"qty": int(row.qty),
			"rate": frappe.utils.fmt_money(row.rate, currency=sales_order.currency),
			"amount": frappe.utils.fmt_money(row.amount, currency=sales_order.currency),
		}
		for row in sales_order.items
	]
	return {
		"doc": sales_order,
		"store_name": _store_name(),
		"order_id": sales_order.name,
		"customer_name": sales_order.customer_name or sales_order.customer,
		"items": items,
		"grand_total": frappe.utils.fmt_money(sales_order.grand_total, currency=sales_order.currency),
		"currency": sales_order.currency,
		"delivery_date": frappe.utils.formatdate(sales_order.delivery_date),
		"tracking_number": sales_order.get("tracking_number"),
		"payment_method": sales_order.get("webshop_payment_method"),
		"track_url": "https://shop.dpono.com/track",
	}


def _already_sent(sales_order_name, kind):
	"""One send per order per message, recorded so retries are harmless."""
	return bool(
		frappe.db.exists(
			"Comment",
			{
				"reference_doctype": "Sales Order",
				"reference_name": sales_order_name,
				"content": f"webshop-notification:{kind}",
			},
		)
	)


def _mark_sent(sales_order_name, kind):
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Sales Order",
			"reference_name": sales_order_name,
			"content": f"webshop-notification:{kind}",
		}
	).insert(ignore_permissions=True)


def _send(sales_order, template_name, kind):
	if _already_sent(sales_order.name, kind):
		return False

	recipient = _recipient(sales_order)
	if not recipient:
		return False

	if not frappe.db.exists("Email Template", template_name):
		return False

	template = frappe.get_doc("Email Template", template_name)
	context = _context(sales_order)

	try:
		subject = frappe.render_template(template.subject, context)
		message = frappe.render_template(template.response_html or template.response, context)
		frappe.sendmail(
			recipients=[recipient],
			subject=subject,
			message=message,
			reply_to=_reply_to(),
			now=False,
		)
	except Exception:
		# A failed email must never roll back or block the order itself.
		frappe.log_error(
			title=f"Webshop {kind} email failed for {sales_order.name}",
			message=frappe.get_traceback(),
		)
		return False

	_mark_sent(sales_order.name, kind)
	return True


def on_sales_order_submit(doc, method=None):
	"""Order confirmation, only for orders placed through the store."""
	if not doc.get("is_webshop_order"):
		return
	if not _settings().get("send_order_confirmation"):
		return
	_send(doc, CONFIRMATION_TEMPLATE, "confirmation")


def on_sales_order_update(doc, method=None):
	"""Let the customer know once a tracking number appears."""
	if not doc.get("is_webshop_order") or doc.docstatus != 1:
		return
	if not _settings().get("send_shipping_notification"):
		return
	if not doc.get("tracking_number"):
		return
	_send(doc, SHIPPED_TEMPLATE, "shipped")


@frappe.whitelist()
def resend_order_email(sales_order, kind="confirmation"):
	"""Manual resend from the Desk, for when a customer says nothing arrived."""
	frappe.only_for(("System Manager", "Sales Manager", "Sales User"))
	doc = frappe.get_doc("Sales Order", sales_order)

	for comment in frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": "Sales Order",
			"reference_name": doc.name,
			"content": f"webshop-notification:{kind}",
		},
		pluck="name",
	):
		frappe.delete_doc("Comment", comment, force=1, ignore_permissions=True)

	template = CONFIRMATION_TEMPLATE if kind == "confirmation" else SHIPPED_TEMPLATE
	sent = _send(doc, template, kind)
	return {"sent": sent, "to": _recipient(doc)}


# ============================================================================
# واتساب — WhatsApp Cloud API
# ============================================================================

def _wa_settings():
	s = frappe.get_single("Webshop Content Settings")
	if not s.get("wa_enabled"):
		return None
	token = s.get_password("wa_token", raise_exception=False)
	phone_id = (s.get("wa_phone_number_id") or "").strip()
	if not token or not phone_id:
		return None
	return frappe._dict({
		"token": token,
		"phone_id": phone_id,
		"language": (s.get("wa_language") or "ar").strip(),
		"confirm": (s.get("wa_template_confirm") or "").strip(),
		"shipped": (s.get("wa_template_shipped") or "").strip(),
	})


def normalise_msisdn(phone):
	"""
	An Egyptian mobile in the form Meta expects: 20 then ten digits, no plus.

	Customers type 01012345678, +201012345678, 0020..., or with spaces. Sending
	any of those verbatim gets silently dropped by Meta.
	"""
	digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
	if digits.startswith("00"):
		digits = digits[2:]
	if digits.startswith("0") and len(digits) == 11:
		digits = "20" + digits[1:]
	elif len(digits) == 10 and digits.startswith("1"):
		digits = "20" + digits
	return digits if digits.startswith("20") and len(digits) == 12 else None


def send_whatsapp_template(phone, template, params=None):
	"""
	One templated message. Returns (ok, detail) — never raises into the caller,
	because a messaging failure must not roll back an order that was placed.
	"""
	settings = _wa_settings()
	if not settings or not template:
		return False, "whatsapp not configured"

	to = normalise_msisdn(phone)
	if not to:
		return False, "bad number: %s" % phone

	body = {
		"messaging_product": "whatsapp",
		"to": to,
		"type": "template",
		"template": {
			"name": template,
			"language": {"code": settings.language},
		},
	}
	if params:
		body["template"]["components"] = [{
			"type": "body",
			"parameters": [{"type": "text", "text": str(p)} for p in params],
		}]

	try:
		res = requests.post(
			"https://graph.facebook.com/v21.0/%s/messages" % settings.phone_id,
			headers={
				"Authorization": "Bearer %s" % settings.token,
				"Content-Type": "application/json",
			},
			data=json.dumps(body),
			timeout=TIMEOUT,
		)
		ok = res.status_code < 300
		detail = res.text[:400]
	except Exception as exc:
		ok, detail = False, str(exc)[:400]

	log_whatsapp(to, "\u0642\u0627\u0644\u0628: " + str(template), sent=True)

	if not ok:
		# Logged, not swallowed — the shop needs to know a customer went untold.
		frappe.log_error(
			title="WhatsApp send failed",
			message="to=%s template=%s\n%s" % (to, template, detail),
		)
	return ok, detail


@frappe.whitelist()
def send_test(phone):
	"""Fire one message from the Desk so the setup can be proven before launch."""
	settings = _wa_settings()
	if not settings:
		frappe.throw(frappe._("فعّل واتساب وحط التوكن و Phone Number ID الأول."))
	if not settings.confirm:
		frappe.throw(frappe._("اكتب اسم قالب تأكيد الطلب."))
	ok, detail = send_whatsapp_template(phone, settings.confirm, ["اختبار", "0"])
	return {"ok": ok, "detail": detail}


# ============================================================================
# سجل محادثات واتساب
# ============================================================================

def _digits(phone):
	return "".join(ch for ch in str(phone or "") if ch.isdigit())


def customer_by_phone(phone):
	"""
	Which customer this number belongs to.

	Numbers are stored inconsistently — with the country code, without it, with
	spaces — so the last nine digits are what gets compared. That is enough to
	identify an Egyptian mobile and short enough to survive the formatting.
	"""
	tail = _digits(phone)[-9:]
	if len(tail) < 9:
		return None

	for query in (
		"SELECT name FROM `tabCustomer` WHERE REPLACE(REPLACE(IFNULL(mobile_no,''),' ',''),'+','') LIKE %s LIMIT 1",
		"""SELECT so.customer FROM `tabSales Order` so
		   WHERE REPLACE(REPLACE(IFNULL(so.custom_customer_phone_number,''),' ',''),'+','') LIKE %s
		   ORDER BY so.creation DESC LIMIT 1""",
	):
		rows = frappe.db.sql(query, "%" + tail)
		if rows and rows[0][0]:
			return rows[0][0]
	return None


def log_whatsapp(phone, message, sent=True, customer=None, reference=None):
	"""
	Record one WhatsApp message against the customer.

	Never raises: a logging failure must not stop a message going out or a
	webhook returning 200, or Meta will retry forever.
	"""
	try:
		customer = customer or customer_by_phone(phone)
		doc = frappe.get_doc({
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Chat",
			"content": (message or "")[:5000],
			"subject": ("\u0648\u0627\u062a\u0633\u0627\u0628 " +
			            ("\u0635\u0627\u062f\u0631" if sent else "\u0648\u0627\u0631\u062f")),
			"sent_or_received": "Sent" if sent else "Received",
			"phone_no": str(phone or "")[:40],
			"status": "Linked" if customer else "Open",
			"reference_doctype": "Customer" if customer else None,
			"reference_name": customer,
		})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		# Not every caller commits — a scheduled send would otherwise lose this.
		frappe.db.commit()

		# Also pin it to the order it was about, when there is one.
		if reference and frappe.db.exists("Sales Order", reference):
			doc.db_set("timeline_doctype", "Sales Order", update_modified=False)
			doc.db_set("timeline_name", reference, update_modified=False)
		return doc.name
	except Exception:
		frappe.log_error(title="WhatsApp log failed",
		                 message=frappe.get_traceback()[:2000])
		return None


@frappe.whitelist(allow_guest=True)
def incoming_webhook():
	"""
	Meta calls this when a customer sends a message.

	Verification (hub.challenge) and delivery share one endpoint, which is how
	Meta expects it. The reply is always 200 — an error here makes Meta retry
	the same message for hours.
	"""
	from sync_webshop.api.utils import set_cors_headers
	set_cors_headers()

	# Meta verifies the endpoint once, with a GET.
	args = frappe.local.form_dict
	if args.get("hub.mode") == "subscribe":
		settings = frappe.get_single("Webshop Content Settings")
		expected = settings.get_password("wa_verify_token", raise_exception=False)
		if expected and args.get("hub.verify_token") == expected:
			frappe.local.response["type"] = "page"
			frappe.local.response["page_name"] = args.get("hub.challenge")
			return
		return {"ok": False}

	try:
		data = frappe.request.get_json(force=True, silent=True) or {}
		for entry in data.get("entry", []):
			for change in entry.get("changes", []):
				value = change.get("value") or {}
				for msg in value.get("messages", []):
					body = ((msg.get("text") or {}).get("body")
					        or "[%s]" % msg.get("type", "media"))
					log_whatsapp(msg.get("from"), body, sent=False)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="WhatsApp webhook", message=frappe.get_traceback()[:2000])

	return {"ok": True}


# ============================================================================
# اختيار خط الواتساب حسب نوع الشغل
# ============================================================================

def _split(text):
	return [p.strip() for p in str(text or "").replace("\n", ",").split(",") if p.strip()]


def whatsapp_line_for(order_name=None, customer=None):
	"""
	Which WhatsApp number should speak to this customer.

	Decided from the order first, because that is the concrete thing: a box of
	coffee is a coffee conversation whatever group the customer sits in. The
	customer group is the fallback, and a default line catches the rest.
	"""
	settings = frappe.get_single("Webshop Content Settings")
	lines = [l for l in (settings.get("wa_lines") or []) if l.enabled]
	if not lines:
		return None

	groups = set()
	if order_name:
		groups.update(frappe.db.sql_list(
			"""
			SELECT DISTINCT i.item_group FROM `tabSales Order Item` soi
			JOIN `tabItem` i ON i.name = soi.item_code
			WHERE soi.parent = %s
			""",
			order_name))
		customer = customer or frappe.db.get_value("Sales Order", order_name, "customer")

	if groups:
		for line in lines:
			wanted = set(_split(line.item_groups))
			if wanted & groups:
				return line
		# An item group can sit under a configured parent rather than match it.
		for line in lines:
			for wanted in _split(line.item_groups):
				lft, rgt = frappe.db.get_value(
					"Item Group", wanted, ["lft", "rgt"]) or (None, None)
				if not lft:
					continue
				under = frappe.db.sql_list(
					"SELECT name FROM `tabItem Group` WHERE lft >= %s AND rgt <= %s",
					(lft, rgt))
				if groups & set(under):
					return line

	if customer:
		cg = frappe.db.get_value("Customer", customer, "customer_group")
		for line in lines:
			if cg in _split(line.customer_groups):
				return line

	for line in lines:
		if line.is_default:
			return line
	return lines[0]


def communication_permission_query(user=None):
	"""
	A WhatsApp log is as private as the customer it belongs to.

	Communication is readable by anyone with desk access out of the box, which
	would have put every customer conversation in front of every employee. This
	narrows the chat records to customers the user can already open, and leaves
	email and everything else untouched.
	"""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""

	if frappe.has_permission("Customer", "read", user=user):
		return ""

	# No access to customers at all — hide the chat records, keep the rest.
	return "(`tabCommunication`.communication_medium != 'Chat')"


# ============================================================================
# Evolution API — الإرسال من السيرفر
# ============================================================================

def _evo():
	s = frappe.get_single("Webshop Content Settings")
	if (s.get("wa_provider") or "evolution") != "evolution":
		return None
	key = s.get_password("evo_api_key", raise_exception=False)
	if not key:
		return None
	return frappe._dict({
		"url": (s.get("evo_url") or "http://127.0.0.1:8080").rstrip("/"),
		"key": key,
	})


def send_whatsapp_text(phone, text, line=None, order_name=None, customer=None):
	"""
	One plain WhatsApp message down the right line.

	Returns (ok, detail) and never raises — a message that fails to send must
	not roll back the order it was telling someone about.
	"""
	evo = _evo()
	if not evo:
		return False, "evolution not configured"

	line = line or whatsapp_line_for(order_name=order_name, customer=customer)
	instance = (line or {}).get("evo_instance") if line else None
	if not instance:
		return False, "no line for this order"

	to = normalise_msisdn(phone)
	if not to:
		return False, "bad number: %s" % phone

	try:
		res = requests.post(
			"%s/message/sendText/%s" % (evo.url, instance),
			headers={"apikey": evo.key, "Content-Type": "application/json"},
			json={"number": to, "text": text},
			timeout=20,
		)
		ok = res.status_code < 300
		detail = res.text[:300]
	except Exception as exc:
		ok, detail = False, str(exc)[:300]

	# Logged either way — a failed send is the one worth finding later.
	log_whatsapp(to, text, sent=True, customer=customer, reference=order_name)

	if not ok:
		frappe.log_error(title="WhatsApp send failed",
		                 message="line=%s to=%s\n%s" % (instance, to, detail))
	return ok, detail


@frappe.whitelist()
def send_test_message(phone, text=None, line_name=None):
	"""Fire one real message from the Desk, to prove the wiring."""
	settings = frappe.get_single("Webshop Content Settings")
	line = None
	for row in settings.get("wa_lines") or []:
		if not line_name or row.line_name == line_name:
			line = row
			break
	ok, detail = send_whatsapp_text(
		phone, text or "رسالة تجريبية من نظام دبونو ✅", line=line)
	return {"ok": ok, "detail": detail, "line": line.line_name if line else None}
