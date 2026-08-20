# -*- coding: utf-8 -*-
"""تجربة مشغّل الحملة من غير ما نبعت — والردود على رسايل وهمية."""
import frappe
from sync_webshop.api import renewal, renewal_runner

OWNER = "201114021275@s.whatsapp.net"


def _pl(text, image=False, mid="RT1", instance="97"):
    msg = {"conversation": text} if not image else {"imageMessage": {"caption": text}}
    return {"event": "messages.upsert", "instance": instance,
            "data": {"key": {"remoteJid": OWNER, "fromMe": False, "id": mid},
                     "pushName": "اسلام", "message": msg}}


def execute():
    s = renewal._settings()
    line, inst = renewal_runner._campaign_line(s)
    print("1) الإعدادات")
    print("   الحملة:", "شغّالة" if s.enabled else "مقفولة",
          "| رقم الحملة:", inst,
          "| الخط اتلقى:", "✓" if line else "✗")
    print("   حد يومي:", s.daily_limit, "| ساعات:", s.send_hours)

    print("\n2) الرسالة الجاية (من غير إرسال)")
    p = renewal_runner.preview_next()
    if p.get("send"):
        print("   العميل:", p.get("customer"), "| المرحلة:", p.get("stage"),
              "| الرقم:", p.get("to"))
        for row in (p.get("body") or "").split("\n")[:6]:
            print("      | " + row)
    else:
        print("   مفيش:", p.get("reason"))

    print("\n3) الردود — بنجرّب الاختيارات على رقم المالك")
    sent = []
    from sync_webshop.api import notifications as N
    orig = N.send_whatsapp_text
    N.send_whatsapp_text = lambda phone, text, **k: (sent.append((phone, text)), (True, "ok"))[1]
    import sys
    sys.modules["sync_webshop.api.renewal_runner"].__dict__.pop("send_whatsapp_text", None)

    imgs = []
    o_pay, o_pri = renewal.send_payment_image, renewal.send_prices_image
    renewal.send_payment_image = lambda m, brand="gps": imgs.append("دفع") or {"sent": 1}
    renewal.send_prices_image = lambda m: imgs.append("أسعار") or {"sent": 1}

    for i, text in enumerate(["1", "2", "3", "4", "هوه هاينتهي امته", "كلام مالوش معنى"]):
        n0, m0 = len(sent), len(imgs)
        renewal_runner.handle_reply(_pl(text, mid="RT%s" % i), "97")
        reply = sent[-1][1].replace("\n", " ")[:56] if len(sent) > n0 else "— مفيش رد (تحويل لموظف)"
        print("   %-18s | صور: %-8s | %s" % (text[:18], ", ".join(imgs[m0:]) or "—", reply))

    n0 = len(sent)
    renewal_runner.handle_reply(_pl("صورة تحويل", image=True, mid="RTIMG"), "97")
    print("   %-18s | %s" % ("صورة من العميل",
          sent[-1][1].replace("\n", " ")[:56] if len(sent) > n0 else "— مفيش رد"))

    print("\n4) رقم غير رقم الحملة")
    print("   1212 ->", renewal_runner.handle_reply(_pl("اهلا", mid="RTX", instance="1212"), "1212"),
          "(المفروض False)")

    N.send_whatsapp_text = orig
    renewal.send_payment_image, renewal.send_prices_image = o_pay, o_pri
    print("\n✓ خلصت — مفيش رسالة اتبعتت فعلًا")
