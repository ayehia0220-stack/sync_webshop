# -*- coding: utf-8 -*-
"""
A switch for public account creation, off by default.

The sign-up endpoint previously created System Users — accounts that can reach
the ERPNext desk. On an ERP carrying this company's accounting and HR, a public
form must not be able to do that, and it should not be reachable at all until
someone deliberately turns it on.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop API Settings": [
		{
			"fieldname": "enable_customer_signup",
			"label": "Enable Customer Signup",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "enable_guest_catalog_access",
			"description": "Let shoppers create an account. Accounts are Website Users and never reach the ERPNext desk.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)
	frappe.db.commit()
