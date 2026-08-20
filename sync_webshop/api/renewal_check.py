# -*- coding: utf-8 -*-
import frappe

def execute():
    for m in ("sync_webshop.api.renewal_runner.run_campaign",
              "sync_webshop.api.automation.sync_workflows"):
        j = frappe.db.get_value("Scheduled Job Type", {"method": m},
                                ["name", "cron_format", "stopped", "last_execution"],
                                as_dict=True)
        print("  %-46s | %s | متوقف=%s | آخر مرة=%s" % (
            m.split(".")[-1], j.cron_format if j else "✗", j.stopped if j else "-",
            str(j.last_execution)[:19] if j else "-"))

    print("\n  اتبعت النهاردة:", frappe.db.count("Renewal Conversation Log", {
        "direction": "صادر", "creation": [">", frappe.utils.nowdate()]}))
    s = frappe.get_single("Renewal Campaign Settings")
    print("  الحد اليومي:", s.daily_limit, "| ساعات الشغل:", s.send_hours)
