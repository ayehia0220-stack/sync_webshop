import frappe
from sync_webshop.api.utils import set_cors_headers


def _find_customer(email=None, phone=None):
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
			"tracking_number",
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


@frappe.whitelist(allow_guest=True)
def get_order_status(order_name, email=None, phone=None):
	set_cors_headers()
	
	filters = {"name": order_name}
	if email or phone:
		customer = _find_customer(email=email, phone=phone)
		if customer:
			filters["customer"] = customer
		else:
			frappe.throw("Customer not found with provided contact info.")
	
	order = frappe.get_all(
		"Sales Order",
		filters=filters,
		fields=[
			"name",
			"transaction_date",
			"delivery_date",
			"status",
			"grand_total",
			"currency",
			"docstatus",
			"tracking_number",
			"webshop_payment_status"
		],
		limit=1
	)
	
	if not order:
		frappe.throw("Order not found.")
		
	order = order[0]
	order["items"] = frappe.get_all(
		"Sales Order Item",
		filters={"parent": order.name},
		fields=["item_code", "item_name", "qty"],
	)
	
	# Also check for Delivery Note tracking
	delivery_notes = frappe.get_all(
		"Delivery Note",
		filters={"against_sales_order": order.name},
		fields=["name", "status", "tracking_number"]
	)
	order["delivery_notes"] = delivery_notes
	
	return order
