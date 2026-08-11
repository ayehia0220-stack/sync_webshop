# -*- coding: utf-8 -*-
"""
إعدادات تربو — credentials and switches for the courier integration.

The authentication key is a Password field, so Frappe encrypts it at rest and
never returns it to a browser. Everything else about how the integration behaves
is a setting, so the owner can pause it, point it at a test account, or change
the default weight without anyone touching code.
"""
import frappe

FIELDS = [
	{"fieldname": "enabled", "label": "فعّل الربط مع تربو", "fieldtype": "Check",
	 "default": "0", "idx": 1,
	 "description": "قفله لو عايز توقف إنشاء الشحنات مؤقتًا."},
	{"fieldname": "auto_create", "label": "اعمل الشحنة تلقائيًا مع كل طلب", "fieldtype": "Check",
	 "default": "0", "idx": 2,
	 "description": "لو مقفول، الشحنة تتعمل بزرار من أمر المبيعات."},
	{"fieldname": "cb0", "fieldtype": "Column Break", "idx": 3},
	{"fieldname": "base_url", "label": "عنوان الـ API", "fieldtype": "Data",
	 "default": "https://platform.turbo.info", "idx": 4},
	{"fieldname": "sec_auth", "label": "بيانات الحساب", "fieldtype": "Section Break", "idx": 5},
	{"fieldname": "authentication_key", "label": "مفتاح الربط", "fieldtype": "Password",
	 "idx": 6,
	 "description": "من لوحة تربو ← الإعدادات. بيتخزّن مشفّر ومش بيظهر تاني."},
	{"fieldname": "main_client_code", "label": "كود العميل", "fieldtype": "Data",
	 "idx": 7, "translatable": 0},
	{"fieldname": "sec_defaults", "label": "الافتراضيات", "fieldtype": "Section Break", "idx": 8},
	{"fieldname": "default_weight", "label": "الوزن الافتراضي (كجم)", "fieldtype": "Float",
	 "default": "1", "idx": 9,
	 "description": "بيتبعت لتربو لو مفيش وزن محسوب للمنتجات."},
	{"fieldname": "is_fragile", "label": "الشحنة قابلة للكسر", "fieldtype": "Check",
	 "default": "0", "idx": 10},
	{"fieldname": "cb1", "fieldtype": "Column Break", "idx": 11},
	{"fieldname": "send_map_link", "label": "ابعت لينك الخريطة مع الشحنة", "fieldtype": "Check",
	 "default": "1", "idx": 12,
	 "description": "لينك موقع العميل بيتحط في «معلومات إضافية عن العنوان» عند تربو."},
	{"fieldname": "map_link_field", "label": "يتحط في خانة", "fieldtype": "Select",
	 "options": "notes\naddress", "default": "notes", "idx": 13,
	 "depends_on": "send_map_link",
	 "description": "لو مظهرش في خانة الموقع عند تربو، جرّب التانية."},
	{"fieldname": "sec_webhook", "label": "تحديثات الحالة", "fieldtype": "Section Break", "idx": 14},
	{"fieldname": "webhook_secret", "label": "كلمة سر الويب هوك", "fieldtype": "Password", "idx": 15,
	 "description": "اختياري. لو حطيتها، تربو لازم يبعتها مع كل تحديث."},
	{"fieldname": "webhook_url", "label": "اللينك اللي تديه لتربو", "fieldtype": "Small Text",
	 "idx": 16, "read_only": 1,
	 "description": "انسخه وابعته لتربو عشان يبعت عليه تحديث حالة الشحنات."},
	{"fieldname": "sec_log", "label": "آخر عملية", "fieldtype": "Section Break", "idx": 17},
	{"fieldname": "last_error", "label": "آخر خطأ", "fieldtype": "Small Text",
	 "idx": 18, "read_only": 1, "translatable": 0},
	{"fieldname": "last_sync", "label": "آخر مزامنة", "fieldtype": "Datetime",
	 "idx": 19, "read_only": 1},
]


def execute():
	name = "Webshop Turbo Settings"
	if not frappe.db.exists("DocType", name):
		frappe.conf["developer_mode"] = 1
		frappe.flags.in_migrate = True
		try:
			doc = frappe.get_doc({
				"doctype": "DocType", "name": name, "module": "Sync Webshop",
				"custom": 0, "issingle": 1, "track_changes": 0,
				"fields": FIELDS,
				"permissions": [{
					"role": "System Manager",
					"read": 1, "write": 1, "create": 1, "delete": 1,
				}],
			})
			doc.flags.ignore_permissions = True
			doc.insert()
			print("created: " + name)
		finally:
			frappe.conf["developer_mode"] = 0
			frappe.flags.in_migrate = False
	else:
		print("exists: " + name)

	settings = frappe.get_single(name)
	if not settings.get("base_url"):
		settings.base_url = "https://platform.turbo.info"
	# Turbo posts status updates here; the owner hands this URL to their rep.
	settings.webhook_url = (
		"https://erp1.dpono.com/api/method/sync_webshop.api.turbo.status_webhook")
	if settings.get("default_weight") in (None, 0):
		settings.default_weight = 1
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("TURBO SETTINGS READY")
