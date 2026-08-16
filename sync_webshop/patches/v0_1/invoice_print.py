# -*- coding: utf-8 -*-
"""
Rearrange the invoice: customer at the top, company at the bottom.

The header carried the company's own address — which the company already knows.
What a delivery driver or a filing clerk needs at a glance is who the invoice is
for and how to reach them, so the customer's phone and address take that space
and the company address moves to the foot of the page.

The original layout is saved to a backup print format first, so the old one can
be switched back to from the Desk without touching anything.
"""
import json

import frappe

NAME = "Coffee Sales Invoice"
BACKUP = "Coffee Sales Invoice (نسخة قديمة)"


def execute():
	pf = frappe.get_doc("Print Format", NAME)
	data = json.loads(pf.format_data)

	# --- keep an escape route -----------------------------------------------
	if not frappe.db.exists("Print Format", BACKUP):
		copy = frappe.copy_doc(pf)
		copy.name = BACKUP
		copy.disabled = 1
		copy.flags.ignore_permissions = True
		copy.insert()
		print("  backup saved:", BACKUP)

	if any(r.get("fieldname") == "custom_address_for_customer_" for r in data):
		print("  already rearranged")
		return

	# --- take the company address out of the header --------------------------
	company_row = None
	for i, row in enumerate(data):
		if row.get("fieldname") == "company_address_display":
			company_row = data.pop(i)
			break

	# --- customer phone next to the name -------------------------------------
	idx = next(i for i, r in enumerate(data) if r.get("fieldname") == "customer")
	data.insert(idx + 1, {
		"fieldname": "custom_customer_phone_number",
		"label": "تليفون العميل", "fieldtype": "Data", "print_hide": 0,
	})

	# --- customer address in the column the company address vacated ----------
	col = next(i for i, r in enumerate(data)
	           if r.get("fieldname") == "posting_date")
	data.insert(col + 1, {"fieldtype": "Column Break"})
	data.insert(col + 2, {
		"fieldname": "custom_address_for_customer_",
		"label": "عنوان العميل", "fieldtype": "Small Text", "print_hide": 0,
	})

	# --- company address at the foot -----------------------------------------
	data.append({"fieldtype": "Section Break", "label": ""})
	data.append({"fieldtype": "Column Break"})
	data.append(company_row or {
		"fieldname": "company_address_display",
		"label": "عنوان الشركة", "fieldtype": "Small Text", "print_hide": 0,
	})

	pf.format_data = json.dumps(data)
	pf.flags.ignore_permissions = True
	pf.save()

	frappe.db.commit()
	frappe.clear_cache()

	print("  new order:")
	for row in json.loads(pf.format_data):
		fn = row.get("fieldname")
		if fn:
			print("     -", fn, "|", row.get("label") or "")
	print("PRINT FORMAT READY")
