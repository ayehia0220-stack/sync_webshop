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
