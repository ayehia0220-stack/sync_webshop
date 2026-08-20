# -*- coding: utf-8 -*-
"""تشغيل الرد التلقائي + تجربة واتساب حقيقية على رقم المالك."""
import frappe
from sync_webshop.api import social

OWNER_JID = "201114021275@s.whatsapp.net"


def execute():
    s = frappe.get_single("Webshop Content Settings")
    s.social_replies_on = 1
    s.save(ignore_permissions=True)
    frappe.db.commit()
    print("✓ الرد التلقائي بقى شغّال | أرقام البوت:", social._bot_instances())

    payload = {"event": "messages.upsert", "instance": "1212",
               "data": {"key": {"remoteJid": OWNER_JID, "fromMe": False,
                                "id": "LIVETEST0001"},
                        "pushName": "اسلام",
                        "message": {"conversation": "عايز اعرف سعر المنتج"}}}
    print("\nبنجرّب رسالة واردة على 1212...")
    handled = social.handle_whatsapp(payload, "1212")
    row = frappe.db.get_value("Social Interaction", {"external_id": "LIVETEST0001"},
                              ["status", "reason", "reply"], as_dict=True)
    print("  اتعالجت في الـ ERP:", handled)
    print("  النتيجة:", row.status if row else "مفيش سجل")
    if row:
        print("  الرد:", (row.reply or "")[:160].replace("\n", " "))
        if row.reason:
            print("  السبب:", row.reason)

    print("\nوبنجرّب إن 97 ما بيتلمسش:")
    payload97 = dict(payload, instance="97")
    payload97["data"] = dict(payload["data"])
    payload97["data"]["key"] = dict(payload["data"]["key"], id="LIVETEST0002")
    print("  اتعالجت في الـ ERP:", social.handle_whatsapp(payload97, "97"),
          "(المفروض False يعني عدّت لحملة التجديد)")

    for name in frappe.get_all("Social Interaction",
                               filters={"external_id": ["like", "LIVETEST%%"]},
                               pluck="name"):
        frappe.delete_doc("Social Interaction", name, force=1, ignore_permissions=True)
    frappe.db.commit()
    print("\n✓ اتنضّف السجل التجريبي")
