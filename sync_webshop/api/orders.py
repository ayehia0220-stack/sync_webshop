import frappe
from sync_webshop.api.utils import set_cors_headers


def _find_customer(email=None, phone=None):
	"""Read-only version of checkout's customer lookup - does not create."""
	contact_name = None
	if email:
		contact_name = frappe.db.get_value("Contact", {"email_id": email}, "name")
	if not contact_name and phone:
		contact_name = frappe.db.get_value("Contact", {"phone": phone}, "name")
	if not contact_name and phone:
		contact_name = frappe.db.get_value("Contact", {"mobile_no": phone}, "name")

	if not contact_name:
		return None

	links = frappe.get_all(
		"Dynamic Link",
		filters={"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
		fields=["link_name"],
	)
	return links[0].link_name if links else None


@frappe.whitelist(allow_guest=True)
def list_my_orders(email=None, phone=None):
	"""
	Returns this customer's Sales Orders, matched by the email or phone
	they used at checkout. Guest-accessible by design, matching the same
	identity model as checkout - there is no customer login system yet,
	so this trades a small amount of privacy (anyone with the email/phone
	can view that history) for simplicity. Revisit alongside checkout's
	abuse-protection note before a real public launch.
	"""
	set_cors_headers()

	if not email and not phone:
		frappe.throw("Provide an email or phone number to look up orders.")

	customer = _find_customer(email=email, phone=phone)
	if not customer:
		return {"customer": None, "orders": []}

	orders = frappe.get_all(
		"Sales Order",
		filters={"customer": customer},
		fields=[
			"name",
			"transaction_date",
			"delivery_date",
			"status",
			"grand_total",
			"currency",
			"docstatus",
		],
		order_by="creation desc",
		limit_page_length=50,
	)

	for order in orders:
		order["items"] = frappe.get_all(
			"Sales Order Item",
			filters={"parent": order.name},
			fields=["item_code", "item_name", "qty"],
		)

	return {"customer": customer, "orders": orders}
