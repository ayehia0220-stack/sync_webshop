# -*- coding: utf-8 -*-
"""جدول السجل + إعدادات فيسبوك + وصل الواتساب بالـ ERP بدل n8n."""

import frappe

DT = "Social Interaction"

FIELDS = [
	{"fieldname": "channel", "label": "القناة", "fieldtype": "Select",
	 "options": "فيسبوك\nواتساب", "reqd": 1,
	 "in_list_view": 1, "in_standard_filter": 1},
	{"fieldname": "status", "label": "النتيجة", "fieldtype": "Select",
	 "options": "تم الرد\nمتجاهل\nفشل", "default": "تم الرد",
	 "in_list_view": 1, "in_standard_filter": 1},
	{"fieldname": "user_name", "label": "العميل", "fieldtype": "Data",
	 "in_list_view": 1},
	{"fieldname": "user_ref", "label": "المعرّف", "fieldtype": "Data"},
	{"fieldname": "col1", "label": "", "fieldtype": "Column Break"},
	{"fieldname": "external_id", "label": "رقم الحدث", "fieldtype": "Data",
	 "reqd": 1, "unique": 1, "read_only": 1},
	{"fieldname": "post_id", "label": "المنشور", "fieldtype": "Data"},
	{"fieldname": "reason", "label": "السبب", "fieldtype": "Data",
	 "in_list_view": 1},
	{"fieldname": "sec", "label": "الكلام", "fieldtype": "Section Break"},
	{"fieldname": "incoming", "label": "رسالة العميل", "fieldtype": "Small Text"},
	{"fieldname": "reply", "label": "ردّنا", "fieldtype": "Small Text"},
]

SETTINGS_FIELDS = [
	{"fieldname": "social_section", "label": "الرد على العملاء",
	 "fieldtype": "Section Break", "insert_after": "lifecycle_messages_on"},
	{"fieldname": "social_replies_on", "label": "شغّل الرد التلقائي",
	 "fieldtype": "Check", "default": "0", "insert_after": "social_section",
	 "description": "كومنتات فيسبوك ورسايل واتساب"},
	{"fieldname": "wa_bot_instances", "label": "أرقام الواتساب اللي البوت يرد منها",
	 "fieldtype": "Data", "default": "1212",
	 "insert_after": "social_replies_on",
	 "description": "أرقام مفصولة بفاصلة. رقم الـ GPS (97) ليه حملة "
	                "التجديد فماينفعش يتحط هنا."},
	{"fieldname": "fb_col", "label": "", "fieldtype": "Column Break",
	 "insert_after": "wa_bot_instances"},
	{"fieldname": "fb_page_ids", "label": "أرقام صفحات فيسبوك بتاعتنا",
	 "fieldtype": "Small Text", "insert_after": "fb_col",
	 "description": "عشان البوت مايردش على الصفحة نفسها"},
	{"fieldname": "fb_verify_token", "label": "كلمة التحقق مع ميتا",
	 "fieldtype": "Data", "insert_after": "fb_page_ids"},
	{"fieldname": "fb_page_token", "label": "توكن صفحة فيسبوك",
	 "fieldtype": "Password", "insert_after": "fb_verify_token"},
]


def _doctype():
	if frappe.db.exists("DocType", DT):
		print("  — الجدول موجود")
		return
	frappe.get_doc({
		"doctype": "DocType", "name": DT, "module": "Sync Webshop",
		"custom": 1, "autoname": "hash", "title_field": "user_name",
		"sort_field": "creation", "sort_order": "DESC",
		"fields": FIELDS,
		"permissions": [{"role": "System Manager", "read": 1, "write": 1,
		                 "create": 1, "delete": 1, "report": 1, "export": 1},
		                {"role": "Sales Manager", "read": 1, "report": 1}],
	}).insert(ignore_permissions=True)
	print("  ✓ اتعمل جدول %s" % DT)


def _settings():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({"Webshop Content Settings": SETTINGS_FIELDS},
	                     ignore_validate=True)
	print("  ✓ إعدادات الرد على العملاء")


def execute():
	_doctype()
	_settings()
	frappe.db.commit()
	print("\n✓ تمام — المفتاح لسه مقفول لحد ما نجرّب")
