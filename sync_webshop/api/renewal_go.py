# -*- coding: utf-8 -*-
"""نشغّل الحملة من الـ ERP ونقفل ورك فلو الإرسال في n8n."""
import frappe
from sync_webshop.api import automation

METHOD = "sync_webshop.api.renewal_runner.run_campaign"


def execute():
    if frappe.db.exists("Scheduled Job Type", {"method": METHOD}):
        print("  — المهمة موجودة")
    else:
        frappe.get_doc({
            "doctype": "Scheduled Job Type", "method": METHOD,
            "frequency": "Cron", "cron_format": "*/5 * * * *",
            "create_log": 0,
        }).insert(ignore_permissions=True)
        print("  ✓ مهمة كل 5 دقايق")

    # الإرسال بس. الردود بتفضل مفتوحة كشبكة أمان: مابتشتغلش غير لو
    # الـ ERP رمى استثناء ومامسكش الرسالة.
    j = frappe.db.get_value("Automation Job", {"job_key": "n8n:RenewSend000001x"},
                            ["name", "job_name"], as_dict=True)
    if j:
        print(" ", automation.set_active(j.name, 0), "->", j.job_name)
    frappe.db.commit()
