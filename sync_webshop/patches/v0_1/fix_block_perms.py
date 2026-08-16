# -*- coding: utf-8 -*-
"""
Give back the roles that a permission edit quietly removed.

Custom HTML Block ships with read for Desk User, System Manager and Workspace
Manager. Someone later added a Custom DocPerm for App Super Admin — and in
Frappe the moment one custom permission row exists for a doctype, the standard
rows stop applying altogether. They are replaced, not merged.

So the block that Fatma could not see was not blocked by the workspace or by the
block's own roles table. Every role except App Super Admin had lost read on the
doctype, and nobody noticed because the people testing it had that role.

The standard rows are restored alongside the custom one.
"""
import frappe

WANT = [
	# role, read, write, create, delete, if_owner
	("Desk User", 1, 0, 0, 0, 0),
	("Desk User", 1, 1, 1, 1, 1),
	("System Manager", 1, 1, 1, 1, 0),
	("Workspace Manager", 1, 1, 1, 1, 0),
]

DT = "Custom HTML Block"


def execute():
	existing = {
		(p.role, p.if_owner or 0)
		for p in frappe.get_all("Custom DocPerm", filters={"parent": DT},
		                        fields=["role", "if_owner"])
	}

	added = []
	for role, read, write, create, delete, if_owner in WANT:
		if (role, if_owner) in existing:
			continue
		if not frappe.db.exists("Role", role):
			continue
		doc = frappe.get_doc({
			"doctype": "Custom DocPerm",
			"parent": DT, "parenttype": "DocType", "parentfield": "permissions",
			"role": role, "permlevel": 0,
			"read": read, "write": write, "create": create, "delete": delete,
			"if_owner": if_owner,
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		added.append("%s%s" % (role, " (if_owner)" if if_owner else ""))

	frappe.clear_cache()
	frappe.db.commit()

	print("added:", added or "(nothing missing)")
	print()
	print("permissions now:")
	for p in frappe.get_all("Custom DocPerm", filters={"parent": DT},
	                        fields=["role", "read", "write", "if_owner"],
	                        order_by="role"):
		print("   %-22s read=%s write=%s if_owner=%s" % (p.role, p.read, p.write, p.if_owner))
