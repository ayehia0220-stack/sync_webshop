# -*- coding: utf-8 -*-
"""مين منهم مصدره اتمسح فعلًا."""
import frappe

def execute():
    rows = frappe.get_all("Auto Repeat", filters={"status": "Active"},
                          fields=["name", "reference_doctype", "reference_document",
                                  "next_schedule_date"])
    gone, alive = [], []
    for r in rows:
        exists = frappe.db.exists(r.reference_doctype, r.reference_document)
        (alive if exists else gone).append(r)
        print("%-6s | %-16s | %-24s | %s" % (
            "موجود" if exists else "اتمسح", r.reference_doctype,
            r.reference_document, r.next_schedule_date))
    print("\nالمصدر اتمسح: %s | المصدر موجود: %s" % (len(gone), len(alive)))
    return gone
