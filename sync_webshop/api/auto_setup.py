# -*- coding: utf-8 -*-
"""يبني كل حاجة شاشة «الأتمتة» محتاجاها: الجدول، الإعدادات، والمهمة المجدولة."""

import frappe


def _field(fieldname, label, fieldtype, **kw):
	d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	d.update(kw)
	return d


FIELDS = [
	_field("job_name", "الاسم", "Data", reqd=1, in_list_view=1, in_standard_filter=1),
	_field("source", "المصدر", "Select", options="n8n\nERPNext",
	       default="n8n", in_list_view=1, in_standard_filter=1),
	_field("health", "الحالة", "Select",
	       options="شغال\nمتوقف\nميت\nفيه أخطاء", default="شغال",
	       in_list_view=1, in_standard_filter=1),
	_field("is_active", "مفعّلة", "Check", default="0", in_list_view=1),
	_field("col1", "", "Column Break"),
	_field("last_run", "آخر تشغيل", "Datetime", in_list_view=1),
	_field("runs_7d", "تشغيل (7 أيام)", "Int"),
	_field("success_7d", "نجاح (7 أيام)", "Int"),
	_field("error_7d", "فشل (7 أيام)", "Int"),
	_field("sec2", "تفاصيل", "Section Break"),
	_field("job_key", "المفتاح", "Data", reqd=1, unique=1, read_only=1),
	_field("node_count", "عدد الخطوات", "Int", read_only=1),
	_field("open_url", "الرابط", "Data", read_only=1),
	_field("detail", "ملاحظات", "Small Text", read_only=1),
]


def _doctype():
	if frappe.db.exists("DocType", "Automation Job"):
		print("  — الجدول موجود")
		return
	doc = frappe.get_doc({
		"doctype": "DocType",
		"name": "Automation Job",
		"module": "Sync Webshop",
		"custom": 1,
		"autoname": "field:job_key",
		"title_field": "job_name",
		"search_fields": "source,health,job_name",
		"sort_field": "last_run",
		"sort_order": "DESC",
		"track_changes": 0,
		"fields": FIELDS,
		"permissions": [
			{"role": "System Manager", "read": 1, "write": 1,
			 "create": 1, "delete": 1, "report": 1, "export": 1},
			{"role": "Sales Manager", "read": 1, "report": 1},
		],
	})
	doc.insert(ignore_permissions=True)
	print("  ✓ اتعمل جدول Automation Job")


def _settings_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({
		"Webshop API Settings": [
			{"fieldname": "n8n_section", "label": "n8n",
			 "fieldtype": "Section Break", "insert_after": "allowed_origins"},
			{"fieldname": "n8n_url", "label": "عنوان n8n",
			 "fieldtype": "Data", "insert_after": "n8n_section",
			 "description": "زي http://127.0.0.1:5678"},
			{"fieldname": "n8n_api_key", "label": "مفتاح n8n",
			 "fieldtype": "Password", "insert_after": "n8n_url"},
		]
	}, ignore_validate=True)
	print("  ✓ حقول إعدادات n8n")


def _scheduled_job():
	method = "sync_webshop.api.automation.sync_workflows"
	if frappe.db.exists("Scheduled Job Type", {"method": method}):
		print("  — المهمة المجدولة موجودة")
		return
	frappe.get_doc({
		"doctype": "Scheduled Job Type",
		"method": method,
		"frequency": "Cron",
		"cron_format": "*/15 * * * *",
		"create_log": 0,
	}).insert(ignore_permissions=True)
	print("  ✓ مهمة مجدولة كل ربع ساعة")


def execute():
	_doctype()
	_settings_fields()
	_scheduled_job()
	frappe.db.commit()
	print("\n✓ تمام")
