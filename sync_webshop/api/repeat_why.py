# -*- coding: utf-8 -*-
import frappe

def execute():
    for r in frappe.get_all("Auto Repeat", filters={"status": "Active"},
                            fields=["name", "reference_doctype", "reference_document",
                                    "next_schedule_date", "disabled", "start_date",
                                    "end_date", "frequency", "repeat_on_day",
                                    "docstatus"]):
        print("%-13s | %-16s | docstatus=%s | معطّل=%s | يوم=%s | من %s" % (
            r.name, r.reference_doctype, r.docstatus, r.disabled,
            r.repeat_on_day, r.start_date))
    print()
    from frappe.automation.doctype.auto_repeat.auto_repeat import get_auto_repeat_entries
    picked = get_auto_repeat_entries(frappe.utils.getdate(frappe.utils.today()))
    print("اللي المجدول بيشوفهم النهاردة:", len(picked))
    for p in picked:
        print("  ", p.name if hasattr(p, "name") else p)
