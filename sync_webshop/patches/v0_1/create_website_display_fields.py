# -*- coding: utf-8 -*-
"""
Shop-facing names, separate from the operational ones.

Item and Item Group names here describe production ("أكياس بن منتج تام-
فاتح سادة-500 X"), which is right for the warehouse and wrong for a customer.
Renaming them would ripple through stock, BOMs and reports, so the storefront
gets its own optional title instead. Leave it empty and nothing changes.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DISPLAY_FIELDS = {
	"Item": [
		{
			"fieldname": "website_section",
			"label": "Online Store",
			"fieldtype": "Section Break",
			"insert_after": "image",
			"collapsible": 1,
		},
		{
			"fieldname": "website_title",
			"label": "Store Name",
			"fieldtype": "Data",
			"insert_after": "website_section",
			"translatable": 1,
			"description": "Name shoppers see. Leave empty to use the item name.",
		},
		{
			"fieldname": "website_short_description",
			"label": "Store Short Description",
			"fieldtype": "Small Text",
			"insert_after": "website_title",
			"description": "One or two lines shown under the product name.",
		},
	],
	"Item Group": [
		{
			"fieldname": "website_title",
			"label": "Store Name",
			"fieldtype": "Data",
			"insert_after": "show_in_website",
			"translatable": 1,
			"description": "Category name shoppers see. Leave empty to use the group name.",
		},
	],
}


def execute():
	create_custom_fields(DISPLAY_FIELDS, ignore_validate=True)
	frappe.db.commit()
