# -*- coding: utf-8 -*-
"""ورك سبيس «الأتمتة» تشمل كل حاجة تخص الأتمتة — شاشات ونصوص وإعدادات وسجلات."""

import json

import frappe

DT = "Automation Job"

SECTIONS = [
	("الشاشات", [
		("Report", "الأتمتة — كل الورك فلو", "كل الورك فلو", DT),
		("Report", "الأتمتة — محتاجة قرار", "محتاجة قرار", DT),
		("DocType", DT, "كل الأتمتة", None),
	]),
	("نصوص الرسايل", [
		("DocType", "Webshop Lifecycle Message", "رسايل ما بعد العمليات", None),
		("DocType", "Renewal Message Template", "رسايل حملة التجديد", None),
		("DocType", "Webshop Agent Training", "تدريب المساعد", None),
	]),
	("الإعدادات", [
		("DocType", "Webshop Content Settings", "أرقام الواتساب والمفاتيح", None),
		("DocType", "Webshop API Settings", "الربط بـ n8n", None),
		("DocType", "Renewal Campaign Settings", "إعدادات حملة التجديد", None),
	]),
	("أدوات ERPNext", [
		("DocType", "Scheduled Job Type", "المهام المجدولة", None),
		("DocType", "Notification", "التنبيهات", None),
		("DocType", "Webhook", "الويب هوك", None),
		("DocType", "Server Script", "سكربتات السيرفر", None),
	]),
	("السجلات", [
		("DocType", "Renewal Conversation Log", "محادثات التجديد", None),
		("DocType", "Error Log", "سجل الأخطاء", None),
		("DocType", "Scheduled Job Log", "سجل المهام", None),
	]),
]

ROW1 = ["الأتمتة — الإجمالي", "الأتمتة — شغالة",
        "الأتمتة — ميتة", "الأتمتة — فيها أخطاء"]
ROW2 = ["الأتمتة — في n8n", "الأتمتة — جوّه ERPNext", "الأتمتة — مقفولة"]


def _content():
	blocks = [{"id": "auhdr1", "type": "header", "data": {
		"text": "<span class=\"h4\"><b>نظرة سريعة</b></span>", "col": 12}}]
	n = 2
	for name in ROW1:
		blocks.append({"id": "aucard%s" % n, "type": "number_card",
		               "data": {"number_card_name": name, "col": 3}})
		n += 1
	blocks.append({"id": "auspc%s" % n, "type": "spacer", "data": {"col": 12}})
	n += 1
	blocks.append({"id": "auhdr%s" % n, "type": "header", "data": {
		"text": "<span class=\"h4\"><b>الأتمتة فين</b></span>", "col": 12}})
	n += 1
	for name in ROW2:
		blocks.append({"id": "aucard%s" % n, "type": "number_card",
		               "data": {"number_card_name": name, "col": 4}})
		n += 1
	return json.dumps(blocks, ensure_ascii=False)


def execute():
	label = "الأتمتة"
	doc = frappe.get_doc("Workspace", label)
	doc.links = []
	doc.number_cards = []
	doc.content = _content()

	missing = []
	for card, entries in SECTIONS:
		live = [e for e in entries if frappe.db.exists(e[0], e[1])]
		for entry in entries:
			if entry not in live:
				missing.append("%s: %s" % (entry[0], entry[1]))
		if not live:
			continue
		doc.append("links", {"type": "Card Break", "label": card,
		                     "link_count": len(live), "hidden": 0, "onboard": 0})
		for link_type, link_to, text, dep in live:
			row = {"type": "Link", "label": text, "link_type": link_type,
			       "link_to": link_to, "hidden": 0, "onboard": 0}
			if link_type == "Report":
				row["is_query_report"] = 1
				row["dependencies"] = dep
			doc.append("links", row)
		print("  ✓ %s (%s)" % (card, len(live)))

	for name in ROW1 + ROW2:
		doc.append("number_cards", {"number_card_name": name, "label": name})

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	if missing:
		print("\n  — مش موجودة فاتشالت: %s" % ", ".join(missing))
	print("\n✓ الورك سبيس فيها %s رابط" % len([l for l in doc.links
	                                            if l.type == "Link"]))
