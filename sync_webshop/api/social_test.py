# -*- coding: utf-8 -*-
"""
تجربة الرد على العملاء من غير ما ننشر ولا نبعت حاجة.

بنجرّب تلات حاجات: الفلترة بترفض إيه، المساعد بيرد إيه على كلام
حقيقي، والواتساب الوارد بيتقسّم صح بين رقم البوت ورقم التجديد.
"""

import frappe

from sync_webshop.api import social

# كومنتات: (النص، parent==post؟، مين كاتبه، المتوقع)
COMMENTS = [
	("بكام الكيلو؟", True, "user1", "يرد"),
	("عايز اعرف اسعار اجهزة التتبع", True, "user1", "يرد"),
	("ممتاز 👌", True, "user1", "يرد"),
	("ااااااا", True, "user1", "يتجاهل — حروف مكررة"),
	("01012345678", True, "user1", "يتجاهل — أرقام لوحدها"),
	(".", True, "user1", "يتجاهل — قصير"),
	("test123", True, "user1", "يتجاهل — سبام"),
	("شكرا", True, "320708401126027", "يتجاهل — الصفحة نفسها"),
	("تمام", False, "user1", "يتجاهل — رد على رد"),
]


def _fake(text, direct, user_id, comment_id):
	return {"entry": [{"changes": [{"field": "feed", "value": {
		"item": "comment", "verb": "add", "comment_id": comment_id,
		"post_id": "POST1", "parent_id": "POST1" if direct else "OTHER",
		"message": text, "from": {"id": user_id, "name": "عميل تجريبي"},
	}}]}]}


def execute():
	print("1) الإعدادات:")
	s = frappe.get_single("Webshop Content Settings")
	cfg = social._fb()
	print("   الرد التلقائي: %s" % ("شغّال" if social._on() else "مقفول"))
	print("   صفحاتنا: %s" % cfg.pages)
	print("   توكن الصفحة: %s" % ("موجود ✓" if cfg.token else "✗ ناقص"))
	print("   كلمة التحقق: %s" % ("موجودة ✓" if cfg.verify else "✗ ناقصة"))
	print("   أرقام البوت: %s" % social._bot_instances())

	print("\n2) الفلترة — إيه اللي بيعدّي وإيه اللي بيتمنع:")
	sent = []
	orig_post, orig_ask = social._fb_post, social._ask
	social._fb_post = lambda *a, **k: sent.append(1) or True
	social._ask = lambda t, c: "رد تجريبي على: %s" % t[:30]

	before = frappe.db.count("Social Interaction")
	for i, (text, direct, user_id, expect) in enumerate(COMMENTS):
		cid = "TESTC%s" % i
		n0 = len(sent)
		social.handle_facebook(_fake(text, direct, user_id, cid))
		row = frappe.db.get_value("Social Interaction", {"external_id": cid},
		                          ["status", "reason"], as_dict=True)
		acted = "نشر" if len(sent) > n0 else "—"
		got = (row.status if row else "اتخطّى بالكامل")
		print("   %-32s | %-6s | %-10s | %s" % (
			text[:30], acted, got, expect))

	social._fb_post, social._ask = orig_post, orig_ask

	print("\n3) رد المساعد الحقيقي على كلام عملاء:")
	for q in ("بكام كيلو البن؟", "عايز جهاز تتبع للعربية",
	          "فين مقركم؟", "بتوصلوا اسكندرية؟"):
		res = social.try_reply(q, "facebook")
		reply = (res["reply"] or "").replace("\n", " ")
		print("   س: %-26s" % q[:26])
		print("      ج: %s" % reply[:96])

	print("\n4) توزيع الواتساب الوارد:")
	for inst, label in (("1212", "البن — المفروض المساعد يرد"),
	                    ("97", "GPS — المفروض يعدّي لحملة التجديد")):
		ok = str(inst) in social._bot_instances()
		print("   %-5s | %-38s | %s" % (
			inst, label, "المساعد ✓" if ok else "بيعدّي لـ n8n"))

	print("\n5) تنظيف:")
	for name in frappe.get_all("Social Interaction",
	                           filters={"external_id": ["like", "TESTC%%"]},
	                           pluck="name"):
		frappe.delete_doc("Social Interaction", name,
		                  force=1, ignore_permissions=True)
	frappe.db.commit()
	after = frappe.db.count("Social Interaction")
	print("   السجل رجع زي ما كان: %s" % ("✓" if after == before else "✗"))
