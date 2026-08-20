# -*- coding: utf-8 -*-
"""التكرارات التلقائية الواقفة — إيه هي وليه وقفت."""
import frappe
from frappe.utils import getdate, nowdate


def execute():
    rows = frappe.get_all("Auto Repeat", filters={"status": "Active"},
                          fields=["name", "reference_doctype", "reference_document",
                                  "frequency", "next_schedule_date", "start_date",
                                  "end_date", "disabled", "submit_on_creation",
                                  "notify_by_email"])
    print("%-26s | %-9s | %-12s | %-12s | %s" % (
        "المستند", "التكرار", "الجاي", "النهاية", "متأخر كام يوم"))
    print("=" * 92)
    for r in sorted(rows, key=lambda x: str(x.next_schedule_date or "")):
        late = ""
        if r.next_schedule_date:
            d = (getdate(nowdate()) - getdate(r.next_schedule_date)).days
            late = "%s يوم ⚠️" % d if d > 0 else "في ميعاده ✓"
        print("%-26s | %-9s | %-12s | %-12s | %s" % (
            ("%s %s" % (r.reference_doctype, r.reference_document or ""))[:26],
            r.frequency or "", r.next_schedule_date or "—",
            r.end_date or "بلا نهاية", late))

    print("\n— هل المهمة المسؤولة عنهم شغّالة؟")
    j = frappe.db.get_value("Scheduled Job Type",
                            {"method": ["like", "%auto_repeat%"]},
                            ["name", "method", "frequency", "stopped",
                             "last_execution"], as_dict=True)
    print("  ", j or "✗ مفيش مهمة اسمها auto_repeat")
