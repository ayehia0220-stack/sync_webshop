import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# This ERP makes cost centre, sales partner and sales team mandatory on every
# Sales Order, and phone + customer source mandatory on every Customer. Online
# orders have no salesperson, so the channel itself is recorded instead of
# attributing the sale to someone who did not make it.
WEBSITE_SALES_PERSON = "الموقع الإلكتروني"

ORDER_DEFAULT_FIELDS = {
	"Webshop API Settings": [
		{
			"fieldname": "default_cost_center",
			"label": "Default Cost Center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"insert_after": "default_company",
		},
		{
			"fieldname": "default_sales_partner",
			"label": "Default Sales Partner",
			"fieldtype": "Link",
			"options": "Sales Partner",
			"insert_after": "default_cost_center",
		},
		{
			"fieldname": "default_sales_person",
			"label": "Default Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"insert_after": "default_sales_partner",
			"description": "Online orders are credited here. Change it if commission should go elsewhere.",
		},
		{
			"fieldname": "customer_source_value",
			"label": "Customer Source",
			"fieldtype": "Data",
			"insert_after": "default_sales_person",
			"description": "Written to the mandatory 'مصدر العميل' field on customers created by the store.",
		},
	],
}


def _ensure_website_sales_person():
	if frappe.db.exists("Sales Person", WEBSITE_SALES_PERSON):
		return WEBSITE_SALES_PERSON
	parent = frappe.db.get_value("Sales Person", {"is_group": 1, "parent_sales_person": ("in", ("", None))}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Sales Person",
			"sales_person_name": WEBSITE_SALES_PERSON,
			"is_group": 0,
			"parent_sales_person": parent,
			"enabled": 1,
		}
	)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


def execute():
	create_custom_fields(ORDER_DEFAULT_FIELDS, ignore_validate=True)

	settings = frappe.get_single("Webshop API Settings")
	changed = False
	company = settings.get("default_company") or frappe.db.get_value("Company", {}, "name")

	if not settings.get("default_cost_center"):
		# Prefer whatever recent orders already use, rather than inventing one.
		recent = frappe.db.sql(
			"""
			SELECT cost_center, COUNT(*) c FROM `tabSales Order`
			WHERE cost_center IS NOT NULL AND cost_center != ''
			GROUP BY cost_center ORDER BY c DESC LIMIT 1
			"""
		)
		cost_center = recent[0][0] if recent else frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		if cost_center:
			settings.default_cost_center = cost_center
			changed = True

	if not settings.get("default_sales_partner"):
		partner = frappe.db.get_value("Sales Partner", {"partner_name": "عام"}, "name") or frappe.db.get_value(
			"Sales Partner", {}, "name"
		)
		if partner:
			settings.default_sales_partner = partner
			changed = True

	if not settings.get("default_sales_person"):
		settings.default_sales_person = _ensure_website_sales_person()
		changed = True

	if not settings.get("customer_source_value"):
		settings.customer_source_value = "الموقع الالكتروني"
		changed = True

	if changed:
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()

	frappe.db.commit()
