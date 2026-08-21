# -*- coding: utf-8 -*-
import frappe
from frappe.utils import now_datetime

def execute():
    print("دلوقتي:", str(now_datetime())[:19])
    for m in ("sync_webshop.api.renewal_runner.run_campaign",
              "sync_webshop.api.automation.sync_workflows"):
        d = frappe.get_doc("Scheduled Job Type", {"method": m})
        try:
            nxt = d.get_next_execution()
        except Exception as e:
            nxt = "خطأ: %s" % str(e)[:60]
        print("  %-18s | آخر مرة %s | الجاية %s | مستحقة=%s" % (
            m.split(".")[-1], str(d.last_execution)[:19], str(nxt)[:19],
            d.is_event_due()))
