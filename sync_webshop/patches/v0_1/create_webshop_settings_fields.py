import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Checkout used to guess: any non-group warehouse, any account of type Tax.
# On a live ERP that lands stock reservations and revenue in the wrong place,
# so the storefront now asks for these explicitly.
SETTINGS_FIELDS = {
	"Webshop API Settings": [
		{
			"fieldname": "webshop_defaults_section",
			"label": "Order Defaults",
			"fieldtype": "Section Break",
			"insert_after": "default_price_list",
		},
		{
			"fieldname": "default_warehouse",
			"label": "Default Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"insert_after": "webshop_defaults_section",
			"description": "Warehouse used for online orders. Leave empty to let ERPNext choose.",
		},
		{
			"fieldname": "default_customer_group",
			"label": "Default Customer Group",
			"fieldtype": "Link",
			"options": "Customer Group",
			"insert_after": "default_warehouse",
		},
		{
			"fieldname": "default_territory",
			"label": "Default Territory",
			"fieldtype": "Link",
			"options": "Territory",
			"insert_after": "default_customer_group",
		},
		{
			"fieldname": "default_company",
			"label": "Default Company",
			"fieldtype": "Link",
			"options": "Company",
			"insert_after": "default_territory",
		},
	],
	"Webshop Shipping Rule": [
		{
			"fieldname": "shipping_account",
			"label": "Shipping Income Account",
			"fieldtype": "Link",
			"options": "Account",
			"insert_after": "shipping_cost",
			"description": "Where the shipping charge is posted. Required once a shipping cost is set.",
		},
	],
}


def execute():
	create_custom_fields(SETTINGS_FIELDS, ignore_validate=True)

	settings = frappe.get_single("Webshop API Settings")
	changed = False

	if not settings.get("default_company"):
		company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if company:
			settings.default_company = company
			changed = True

	if not settings.get("default_warehouse"):
		company = settings.get("default_company")
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
		if warehouse:
			settings.default_warehouse = warehouse
			changed = True

	if not settings.get("default_customer_group"):
		group = frappe.db.get_single_value("Selling Settings", "customer_group") or frappe.db.get_value(
			"Customer Group", {"is_group": 0}, "name"
		)
		if group:
			settings.default_customer_group = group
			changed = True

	if not settings.get("default_territory"):
		territory = frappe.db.get_single_value("Selling Settings", "territory") or frappe.db.get_value(
			"Territory", {"is_group": 0}, "name"
		)
		if territory:
			settings.default_territory = territory
			changed = True

	if changed:
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()

	frappe.db.commit()
