# -*- coding: utf-8 -*-
"""
Order emails.

Everything a customer receives is driven by an Email Template in ERPNext, so
the wording is edited in the Desk, never here. Each message is sent at most
once per order — a resave, a background retry, or a double submit will not
send it twice.
"""
import frappe

CONFIRMATION_TEMPLATE = "Webshop Order Confirmation"
SHIPPED_TEMPLATE = "Webshop Order Shipped"


def _settings():
	return frappe.get_single("Webshop Content Settings")


def _store_name():
	return _settings().get("site_name") or "dpono"


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
		frappe.sendmail(recipients=[recipient], subject=subject, message=message, now=False)
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
