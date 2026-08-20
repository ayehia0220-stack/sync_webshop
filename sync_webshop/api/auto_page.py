# -*- coding: utf-8 -*-
"""صفحة «الأتمتة» — تقريرين، سبع أرقام، وورك سبيس تجمعهم."""

import json

import frappe

DT = "Automation Job"

BASE_COLS = """	health as `الحالة:Data:95`,
	source as `المصدر:Data:85`,
	job_name as `الاسم:Data:300`,
	if(is_active, 'أيوه', 'لأ') as `مفعّلة:Data:75`,
	last_run as `آخر تشغيل:Datetime:155`,
	runs_7d as `تشغيل 7 أيام:Int:115`,
	success_7d as `نجاح:Int:75`,
	error_7d as `فشل:Int:75`,
	node_count as `خطوات:Int:75`,
	detail as `ملاحظات:Data:260`,
	name as `فتح:Link/Automation Job:70`"""

REPORTS = [
	("الأتمتة — كل الورك فلو",
	 "select\n" + BASE_COLS + "\nfrom `tab" + DT + "`\n"
	 "order by is_active desc, runs_7d desc, job_name"),

	("الأتمتة — محتاجة قرار",
	 "select\n" + BASE_COLS + "\nfrom `tab" + DT + "`\n"
	 "where is_active = 1 and health in ('ميت', 'فيه أخطاء')\n"
	 "order by field(health, 'فيه أخطاء', 'ميت'), last_run"),
]

CARDS = [
	("الأتمتة — الإجمالي", []),
	("الأتمتة — شغالة", [[DT, "health", "=", "شغال"]]),
	("الأتمتة — ميتة", [[DT, "health", "=", "ميت"], [DT, "is_active", "=", 1]]),
	("الأتمتة — فيها أخطاء", [[DT, "health", "=", "فيه أخطاء"]]),
	("الأتمتة — مقفولة", [[DT, "health", "=", "متوقف"]]),
	("الأتمتة — في n8n", [[DT, "source", "=", "n8n"]]),
	("الأتمتة — جوّه ERPNext", [[DT, "source", "=", "ERPNext"]]),
]

ROW1 = ["الأتمتة — الإجمالي", "الأتمتة — شغالة",
        "الأتمتة — ميتة", "الأتمتة — فيها أخطاء"]
ROW2 = ["الأتمتة — في n8n", "الأتمتة — جوّه ERPNext", "الأتمتة — مقفولة"]


def _reports():
	for label, query in REPORTS:
		if frappe.db.exists("Report", label):
			doc = frappe.get_doc("Report", label)
			doc.query = query
			doc.save(ignore_permissions=True)
			print("  ↻ %s" % label)
			continue
		frappe.get_doc({
			"doctype": "Report", "report_name": label, "ref_doctype": DT,
			"report_type": "Query Report", "is_standard": "No",
			"module": "Sync Webshop", "disabled": 0, "query": query,
			"roles": [{"role": "System Manager"}, {"role": "Sales Manager"}],
		}).insert(ignore_permissions=True)
		print("  ✓ %s" % label)


def _cards():
	for label, filters in CARDS:
		payload = {
			"label": label, "document_type": DT, "function": "Count",
			"is_public": 1, "show_percentage_stats": 0,
			"filters_json": json.dumps(filters, ensure_ascii=False),
			"color": "#449CF0", "type": "Document Type",
		}
		if frappe.db.exists("Number Card", label):
			frappe.db.set_value("Number Card", label, payload)
		else:
			frappe.get_doc(dict(doctype="Number Card", name=label,
			                    **payload)).insert(ignore_permissions=True)
		print("  ✓ رقم: %s" % label)


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


def _workspace():
	label = "الأتمتة"
	if frappe.db.exists("Workspace", label):
		doc = frappe.get_doc("Workspace", label)
		doc.links = []
		doc.number_cards = []
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = label
		doc.title = label

	doc.label = label
	doc.module = "Sync Webshop"
	doc.public = 1
	doc.icon = "setting-gear"
	doc.sequence_id = 91
	doc.content = _content()

	doc.append("links", {"type": "Card Break", "label": "الشاشات",
	                     "link_count": 2, "hidden": 0, "onboard": 0})
	for label_r, _q in REPORTS:
		doc.append("links", {
			"type": "Link", "label": label_r, "link_type": "Report",
			"link_to": label_r, "is_query_report": 1,
			"dependencies": DT, "hidden": 0, "onboard": 0})

	doc.append("links", {"type": "Card Break", "label": "التفاصيل",
	                     "link_count": 2, "hidden": 0, "onboard": 0})
	doc.append("links", {
		"type": "Link", "label": "كل الأتمتة", "link_type": "DocType",
		"link_to": DT, "hidden": 0, "onboard": 0})
	doc.append("links", {
		"type": "Link", "label": "إعدادات الربط", "link_type": "DocType",
		"link_to": "Webshop API Settings", "hidden": 0, "onboard": 0})

	for name in ROW1 + ROW2:
		doc.append("number_cards", {"number_card_name": name, "label": name})

	doc.save(ignore_permissions=True)
	print("  ✓ ورك سبيس: %s" % label)


def execute():
	_reports()
	_cards()
	_workspace()
	frappe.db.commit()
	print("\n✓ الصفحة جاهزة")
