# -*- coding: utf-8 -*-
"""
Telegram settings and the list of people allowed to use the bot.

Nobody can use the bot until their chat id is added here and pointed at an ERP
user — that pairing is what decides which data they can see.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _f(fieldname, label, fieldtype, **kw):
	return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, **kw}


TELEGRAM_USER = {
	"name": "Webshop Telegram User",
	"autoname": "field:chat_id",
	"title_field": "erp_user",
	"fields": [
		_f("chat_id", "رقم المحادثة / Chat ID", "Data", reqd=1, unique=1, in_list_view=1,
		   description="ابعت أي رسالة للبوت وهو هيرد بالرقم بتاعك، وحُطّه هنا."),
		_f("erp_user", "مستخدم الـERP", "Link", options="User", reqd=1, in_list_view=1,
		   description="المساعد هيرد بصلاحيات المستخدم ده بالظبط."),
		_f("enabled", "مفعّل", "Check", default="1", in_list_view=1),
		_f("cb1", "", "Column Break"),
		_f("person_name", "الاسم", "Data", in_list_view=1),
		_f("notes", "ملاحظات", "Small Text"),
	],
}

SETTINGS_FIELDS = {
	"Webshop Agent Settings": [
		_f("sec_telegram", "تليجرام / Telegram", "Section Break",
		   insert_after="log_conversations"),
		_f("telegram_enabled", "بوت تليجرام شغّال", "Check", default="0",
		   insert_after="sec_telegram"),
		_f("telegram_bot_token", "توكن البوت / Bot Token", "Password",
		   insert_after="telegram_enabled",
		   description="من @BotFather في تليجرام. محفوظ مشفّرًا."),
		_f("telegram_cb", "", "Column Break", insert_after="telegram_bot_token"),
		_f("telegram_webhook_secret", "سر الـWebhook", "Password",
		   insert_after="telegram_cb", read_only=1,
		   description="بيتولّد لوحده عند الربط. تليجرام بيبعته مع كل رسالة عشان نتأكد إن الرسالة منه."),
		_f("telegram_help", "", "HTML", insert_after="telegram_webhook_secret",
		   options="<div style='background:#F2FCE4;padding:12px;border-radius:8px;line-height:1.9'>"
		           "<b>الخطوات:</b><br>"
		           "1. احفظ التوكن هنا.<br>"
		           "2. شغّل <code>sync_webshop.api.telegram.register_webhook</code> مرة واحدة.<br>"
		           "3. ابعت رسالة للبوت — هيرد برقم محادثتك.<br>"
		           "4. ضيف الرقم في <b>Webshop Telegram User</b> واربطه بمستخدم ERP.<br>"
		           "5. علّم «بوت تليجرام شغّال».</div>"),
	],
}

PERMS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
]


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		if frappe.db.exists("DocType", TELEGRAM_USER["name"]):
			doc = frappe.get_doc("DocType", TELEGRAM_USER["name"])
			doc.fields = []
		else:
			doc = frappe.new_doc("DocType")
			doc.name = TELEGRAM_USER["name"]

		doc.module = "Sync Webshop"
		doc.custom = 0
		doc.engine = "InnoDB"
		doc.autoname = TELEGRAM_USER["autoname"]
		doc.title_field = TELEGRAM_USER["title_field"]
		doc.track_changes = 1
		for idx, field in enumerate(TELEGRAM_USER["fields"], start=1):
			doc.append("fields", {**field, "idx": idx})
		doc.permissions = []
		for perm in PERMS:
			doc.append("permissions", perm)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.save()
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	create_custom_fields(SETTINGS_FIELDS, ignore_validate=True)
	frappe.db.commit()
	frappe.clear_cache()
	print("TELEGRAM READY")
