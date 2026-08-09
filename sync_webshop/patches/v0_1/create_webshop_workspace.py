# -*- coding: utf-8 -*-
"""
One place in ERPNext that holds everything the storefront reads, so changing
the shop never means changing code.
"""
import json

import frappe

WORKSPACE = "متجر دبونو"

# (section, label, doctype, description)
LINKS = [
	("الشكل والمحتوى", "إعدادات المظهر", "Webshop Theme Settings",
	 "الألوان والخطوط والمقاسات — تغييرها هنا يغيّر الموقع كله"),
	("الشكل والمحتوى", "محتوى الموقع", "Webshop Content Settings",
	 "الشعار، الهيرو، البانرات، الفئات المميزة، شارات الثقة، القائمة، التذييل، بيانات التواصل"),
	("الشكل والمحتوى", "الشريط العلوي", "Webshop Announcement Bar",
	 "الشريط اللي فوق الصفحة — فعّله واكتب رسالتك"),
	("الشكل والمحتوى", "التذييل", "Webshop Footer Settings", "أعمدة وروابط أسفل الصفحة"),
	("الشكل والمحتوى", "النافذة المنبثقة", "Webshop Popup", "رسالة تظهر للزائر"),

	("المنتجات", "الأصناف", "Item",
	 "الصورة و«Store Name» تحت قسم Online Store — ده اللي بيظهر للزبون"),
	("المنتجات", "مجموعات الأصناف", "Item Group",
	 "علّم «Show in Website» على اللي عايزه يظهر، واكتب «Store Name» للاسم المعروض"),
	("المنتجات", "أسعار الأصناف", "Item Price", "السعر في قائمة «ويب سايت» هو سعر المتجر"),
	("المنتجات", "إعدادات المنتجات", "Webshop Product Settings", "عناوين أقسام صفحة المنتج"),

	("البيع", "أوامر البيع", "Sales Order", "طلبات المتجر عليها علامة Webshop Order"),
	("البيع", "إعدادات الدفع", "Webshop Payment Settings", "الدفع عند الاستلام وبوابات الدفع"),
	("البيع", "شركات الشحن", "Webshop Shipping Company",
	 "شركة لكل ناقل: التكلفة والمناطق والمحافظات وأيام التوصيل ورابط التتبّع"),
	("البيع", "طرق الدفع", "Webshop Payment Gateway",
	 "طريقة لكل بوابة: التفعيل والمفاتيح والتعليمات والرسوم الإضافية"),
	("البيع", "قواعد الشحن (قديم)", "Webshop Shipping Rule", "يُستخدم فقط لو مفيش شركة شحن مفعّلة"),
	("البيع", "السلات المتروكة", "Webshop Abandoned Cart", "سلات بدأت ولم تكتمل"),

	("الإعدادات الفنية", "إعدادات الـ API", "Webshop API Settings",
	 "قائمة الأسعار، المستودع، مجموعة العميل، مركز التكلفة، النطاقات المسموح لها"),
	("الإعدادات الفنية", "إعدادات SEO", "Webshop SEO Settings", "عناوين وأوصاف محركات البحث والتحويلات"),
	("الإعدادات الفنية", "حساب البريد", "Email Account", "إعدادات إرسال رسائل الطلبات"),
]

SHORTCUTS = [
	("Webshop Content Settings", "محتوى الموقع"),
	("Webshop Theme Settings", "المظهر"),
	("Item", "الأصناف"),
	("Item Group", "الفئات"),
	("Sales Order", "الطلبات"),
	("Webshop API Settings", "إعدادات API"),
]


def execute():
	if frappe.db.exists("Workspace", WORKSPACE):
		doc = frappe.get_doc("Workspace", WORKSPACE)
		doc.links = []
		doc.shortcuts = []
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = WORKSPACE

	doc.title = WORKSPACE
	doc.label = WORKSPACE
	doc.module = "Sync Webshop"
	doc.icon = "retail"
	doc.public = 1
	doc.is_hidden = 0
	doc.sequence_id = 1.0

	content = [
		{"id": "hdr", "type": "header",
		 "data": {"text": "<span class='h4'>متجر دبونو — كل إعدادات الموقع</span>", "col": 12}},
		{"id": "sc", "type": "shortcut", "data": {"shortcut_name": "محتوى الموقع", "col": 4}},
	]
	doc.content = json.dumps(content, ensure_ascii=False)

	seen_sections = set()
	for section, label, doctype, description in LINKS:
		if not frappe.db.exists("DocType", doctype):
			continue
		if section not in seen_sections:
			doc.append("links", {
				"type": "Card Break",
				"label": section,
				"hidden": 0,
			})
			seen_sections.add(section)
		single = frappe.db.get_value("DocType", doctype, "issingle")
		doc.append("links", {
			"type": "Link",
			"link_type": "DocType",
			"link_to": doctype,
			"label": label,
			"description": description,
			"onboard": 0,
			"is_query_report": 0,
			"hidden": 0,
			**({"link_count": 0} if not single else {}),
		})

	for doctype, label in SHORTCUTS:
		if frappe.db.exists("DocType", doctype):
			doc.append("shortcuts", {"type": "DocType", "link_to": doctype, "label": label, "color": "Green"})

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_links = True
	doc.save()

	# The two half-built workspaces from earlier setup only add confusion.
	for old in ("إدارة متجر سينك", "متجر سينك ويب", "إدارة_متجر_سينك", "متجر_سينك_ويب"):
		if frappe.db.exists("Workspace", old) and old != WORKSPACE:
			frappe.db.set_value("Workspace", old, "is_hidden", 1)

	frappe.db.commit()
	frappe.clear_cache()
	print("WORKSPACE=" + doc.name + " links=" + str(len(doc.links)) + " shortcuts=" + str(len(doc.shortcuts)))
