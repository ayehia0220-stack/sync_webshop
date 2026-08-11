# -*- coding: utf-8 -*-
"""
Example reviews, clearly marked as examples.

The owner asked to see a filled-in version of everything before deciding, so
these go in as placeholders — plausible, but not attributed to a real customer,
because a fabricated review with a real name is a lie to shoppers. They are meant
to be replaced with genuine ones.
"""
import frappe

SAMPLES = [
    (u"البن وصلني تاني يوم ولسه ريحته طالعة من الكيس. أحسن حاجة إن التحميص "
     u"بيبقى جديد مش قاعد على الرف شهور.", u"م. أحمد", u"عميل — القاهرة (مثال)"),
    (u"بجرب بن مختص من سنين، ودي أول مرة ألاقي حد يظبطلي درجة الطحن على "
     u"الماكينة بتاعتي من غير ما أشرح كتير.", u"سارة", u"عميلة — الإسكندرية (مثال)"),
    (u"بطلب للمكتب كل شهر. الطلب بيوصل في ميعاده والفاتورة دايمًا مظبوطة، "
     u"وده اللي بيفرق معايا.", u"ك. محمود", u"مشتريات شركة (مثال)"),
]


def execute():
    settings = frappe.get_single("Webshop Content Settings")
    if settings.testimonials:
        print("testimonials already present: %d" % len(settings.testimonials))
        return
    for i, (quote, author, title) in enumerate(SAMPLES, start=1):
        settings.append("testimonials", {
            "quote_ar": quote, "author": author, "author_title": title,
            "sort_order": i * 10, "is_active": 1,
        })
    settings.flags.ignore_permissions = True
    settings.flags.ignore_mandatory = True
    settings.save()
    frappe.db.commit()
    frappe.clear_cache()
    print("SEEDED %d" % len(SAMPLES))
