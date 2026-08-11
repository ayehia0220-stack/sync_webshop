# -*- coding: utf-8 -*-
"""
Give the swallowed fields their section back.

Inserting a Section Break does not create a closed box — every field after it,
until the next Section Break, becomes part of it. So "شحنة تربو" quietly
absorbed seven of the shop's own fields (customer phone, second phone, address,
remark, actual name, tax id, reference id). Worse, that section carries
depends_on docstatus==1, so on a draft order the whole group vanished.

The fix closes the Turbo group with a fresh Section Break of its own, and drops
the depends_on so nothing can hide someone else's fields again. The Turbo fields
are empty before a shipment exists, which is a clear enough signal on its own.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	# A plain section break right after the last Turbo field, so the fields that
	# follow belong to themselves again.
	create_custom_fields({"Sales Order": [{
		"fieldname": "sec_after_turbo",
		"label": "",
		"fieldtype": "Section Break",
		"insert_after": "turbo_error",
	}]}, ignore_validate=True)

	# A section that hides itself must never contain fields it does not own.
	for fieldname in ("sec_turbo", "sec_turbo_issue"):
		name = frappe.db.get_value(
			"Custom Field", {"dt": "Sales Order", "fieldname": fieldname}, "name")
		if not name:
			continue
		if fieldname == "sec_turbo":
			frappe.db.set_value("Custom Field", name, "depends_on", "")
			frappe.db.set_value("Custom Field", name, "collapsible", 1)

	frappe.clear_cache(doctype="Sales Order")
	frappe.db.commit()

	# --- prove the trapped fields are outside the Turbo group now -----------
	fields = frappe.get_meta("Sales Order", cached=False).fields
	start = next(i for i, f in enumerate(fields) if f.fieldname == "sec_turbo")
	end = next(i for i, f in enumerate(fields)
	           if f.fieldname == "sec_after_turbo")
	inside = [f.fieldname for f in fields[start + 1:end]]
	strays = [f for f in inside if not f.startswith(("turbo", "sec_turbo"))]

	print("داخل قسم تربو: %d حقل" % len(inside))
	print("حقول غريبة جواه: %s" % (strays or "لا يوجد ✅"))
	print("depends_on بعد الإصلاح: %r" % frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "sec_turbo"}, "depends_on"))
	print()
	print("الحقول اللي رجعت بره القسم:")
	for f in fields[end + 1:end + 8]:
		print("   %-16s %s" % (f.fieldname, f.label or ""))
