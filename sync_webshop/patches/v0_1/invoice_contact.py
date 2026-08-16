# -*- coding: utf-8 -*-
"""
Put the customer's phone and address on the invoice.

Only 1 invoice in 3,580 carried an address and 2 carried a phone — ERPNext fills
address_display from an Address record, and this business has 18 of those for
5,207 customers. The real data lives on the sales order, where the team types it:
2,976 phones and 2,747 addresses.

So the invoice reads, in order of how much it can be trusted:
  1. the sales order this invoice was raised from
  2. the customer's Address record
  3. the customer's own mobile field
  4. the customer's most recent order

Nothing already on the invoice is overwritten.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "custom_customer_phone_number",
			"label": "تليفون العميل",
			"fieldtype": "Data",
			"insert_after": "customer_name",
			"translatable": 0,
			"description": "بيتجاب من أمر البيع أو من بيانات العميل.",
		},
		{
			"fieldname": "custom_address_for_customer_",
			"label": "عنوان العميل",
			"fieldtype": "Small Text",
			"insert_after": "custom_customer_phone_number",
			"translatable": 0,
		},
	],
}

HELPER = u'''

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
		addr = (row.get("custom_address_for_customer_") or "").strip()

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
'''


def execute():
	import io

	create_custom_fields(FIELDS, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "def fill_invoice_contact" not in s:
		io.open(p, "w", encoding="utf-8").write(s + HELPER)
		print("turbo.py: invoice contact")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "fill_invoice_contact" not in s:
		old = '\t"Sales Order": {'
		new = ('\t"Sales Invoice": {\n'
		       '\t\t"validate": "sync_webshop.api.turbo.fill_invoice_contact",\n'
		       '\t},\n'
		       '\t"Sales Order": {')
		if old not in s:
			frappe.throw("Sales Order hooks block not found")
		io.open(h, "w", encoding="utf-8").write(s.replace(old, new, 1))
		print("hooks: Sales Invoice validate")

	frappe.db.commit()
	frappe.clear_cache()
	print("INVOICE CONTACT READY")
