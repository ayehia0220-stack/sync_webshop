# -*- coding: utf-8 -*-
import frappe

def execute():
    rows = frappe.get_all("Error Log", filters={"error": ["like", "%%uto%%epeat%%"]},
                          fields=["name", "method", "creation"],
                          order_by="creation desc", limit=4)
    if not rows:
        rows = frappe.get_all("Error Log",
                              filters={"method": ["like", "%%auto_repeat%%"]},
                              fields=["name", "method", "creation"],
                              order_by="creation desc", limit=4)
    print("عدد الأخطاء المسجّلة:", len(rows))
    for r in rows[:2]:
        doc = frappe.get_doc("Error Log", r.name)
        print("\n=== %s | %s ===" % (str(r.creation)[:19], (r.method or "")[:70]))
        text = (doc.error or "")
        tail = [l for l in text.strip().split("\n") if l.strip()][-14:]
        print("\n".join(tail))
