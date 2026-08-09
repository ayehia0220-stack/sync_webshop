import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# The storefront writes these on every order it creates. They were referenced by
# the API long before they existed, which is why order tracking returned a 500
# and payment status was never recorded. Adding them here keeps the schema
# reproducible on any site — running it twice is a no-op.
WEBSHOP_FIELDS = {
	"Sales Order": [
		{
			"fieldname": "webshop_section",
			"label": "Webshop",
			"fieldtype": "Section Break",
			"insert_after": "customer_name",
			"collapsible": 1,
		},
		{
			"fieldname": "is_webshop_order",
			"label": "Webshop Order",
			"fieldtype": "Check",
			"insert_after": "webshop_section",
			"read_only": 1,
			"in_standard_filter": 1,
			"description": "Placed through the online store rather than by a salesperson.",
		},
		{
			"fieldname": "webshop_payment_method",
			"label": "Payment Method",
			"fieldtype": "Data",
			"insert_after": "is_webshop_order",
			"read_only": 1,
		},
		{
			"fieldname": "webshop_payment_status",
			"label": "Payment Status",
			"fieldtype": "Select",
			"options": "\nPending\nPaid\nFailed\nRefunded\nCOD",
			"insert_after": "webshop_payment_method",
			"read_only": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "webshop_column_break",
			"fieldtype": "Column Break",
			"insert_after": "webshop_payment_status",
		},
		{
			"fieldname": "webshop_payment_reference",
			"label": "Payment Reference",
			"fieldtype": "Data",
			"insert_after": "webshop_column_break",
			"read_only": 1,
			"description": "Gateway payment intent or transaction id.",
		},
		{
			"fieldname": "webshop_idempotency_key",
			"label": "Idempotency Key",
			"fieldtype": "Data",
			"insert_after": "webshop_payment_reference",
			"read_only": 1,
			"unique": 1,
			"description": "Stops a double-submitted checkout from creating two orders.",
		},
		{
			"fieldname": "tracking_number",
			"label": "Tracking Number",
			"fieldtype": "Data",
			"insert_after": "webshop_idempotency_key",
		},
		{
			"fieldname": "webshop_customer_note",
			"label": "Customer Note",
			"fieldtype": "Small Text",
			"insert_after": "tracking_number",
			"read_only": 1,
		},
	],
	"Delivery Note": [
		{
			"fieldname": "tracking_number",
			"label": "Tracking Number",
			"fieldtype": "Data",
			"insert_after": "customer_name",
		},
	],
}


def execute():
	create_custom_fields(WEBSHOP_FIELDS, ignore_validate=True)
	frappe.db.commit()
