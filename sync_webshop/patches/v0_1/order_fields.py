# -*- coding: utf-8 -*-
"""
Store the confirmation channel and the second phone on the order.

create_order swallows unknown arguments through **kwargs, so without these two
fields the customer's choice would reach the server and quietly vanish — the
worst kind of feature, one that looks like it works.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Sales Order": [
		{
			"fieldname": "webshop_notify_via",
			"label": "العميل عايز التأكيد فين",
			"fieldtype": "Select",
			"options": "\nwhatsapp\nemail\nsms",
			"insert_after": "webshop_customer_note",
			"read_only": 1,
			"translatable": 0,
		},
		{
			"fieldname": "webshop_phone_alt",
			"label": "رقم تاني للعميل",
			"fieldtype": "Data",
			"insert_after": "webshop_notify_via",
			"read_only": 1,
			"translatable": 0,
		},
	],
}

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/checkout.py"


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	s = io.open(P, encoding="utf-8").read()
	if "webshop_notify_via" not in s:
		old = ("\tcustomer, items, payment_method=None, delivery_date=None,\n"
		       "\tnote=None, coupon_code=None, idempotency_key=None, submit=True, **kwargs\n")
		new = ("\tcustomer, items, payment_method=None, delivery_date=None,\n"
		       "\tnote=None, coupon_code=None, idempotency_key=None, submit=True,\n"
		       "\tnotify_via=None, phone_alt=None, **kwargs\n")
		if old not in s:
			frappe.throw("create_order signature moved")
		s = s.replace(old, new, 1)

		old = '\t\t\t"webshop_customer_note": (note or "")[:500] or None,'
		new = (old + "\n"
		       '\t\t\t"webshop_notify_via": (notify_via or "").strip().lower() or None,\n'
		       '\t\t\t"webshop_phone_alt": (phone_alt or "").strip()[:20] or None,')
		if old not in s:
			frappe.throw("note field line moved")
		s = s.replace(old, new, 1)
		io.open(P, "w", encoding="utf-8").write(s)
		print("checkout.py patched")

	frappe.db.commit()
	frappe.clear_cache()
	print("ORDER FIELDS READY")
