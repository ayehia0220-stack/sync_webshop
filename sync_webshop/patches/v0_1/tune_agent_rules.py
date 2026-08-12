# -*- coding: utf-8 -*-
"""المنع لوحده خلّى الردود عامة ومفيدة‑صفر — نضيف التوجيه الإيجابي: استخدم المعلومات اللي عندك."""
import frappe


def execute():
    doc = frappe.get_doc("Webshop Agent Training", "معلومات دبونو العامة")
    rules = [r for r in (doc.rules or "").splitlines() if r.strip()]
    additions = [
        "لازم ترد على سؤال العميل نفسه — متردش رد ترحيبي عام.",
        "استخدم «المعلومات المؤكدة» في ردك: لو سأل عن الشحن أو التوصيل أو الدفع، جاوبه بالمعلومة المكتوبة.",
        "المنع بتاع الاختراع بيخص الأرقام اللي مش مكتوبة عندك بس — مش حجة إنك متردش.",
        "خاطب العميل بصيغة واحدة حسب اسمه، متكتبش «بيك/بيكي».",
    ]
    for a in additions:
        if a not in rules:
            rules.append(a)
    doc.rules = "\n".join(rules)

    doc.when_unsure = (
        "لو العميل سأل عن سعر منتج معيّن وهو مش مكتوب في «المعلومات المؤكدة»: "
        "ممنوع تقول رقم من دماغك، وممنوع تكتب مكان فاضي زي [السعر]. "
        "قوله يشوف السعر على الموقع dpono.com أو إن حد من الفريق هيبعتله التفاصيل. "
        "نفس الكلام على أي رقم تليفون أو ميعاد أو عرض مش مكتوب عندك."
    )
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    from sync_webshop.api import agent_training
    out = agent_training.get_prompt("facebook")
    print("المصادر:", out["sources"], "| الطول:", len(out["system_message"]))
    print("\n--- القواعد دلوقتي ---")
    for line in out["system_message"].split("## المعلومات المؤكدة")[0].splitlines():
        if line.startswith("- "):
            print(" ", line)
