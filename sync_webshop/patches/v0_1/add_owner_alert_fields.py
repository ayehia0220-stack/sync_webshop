# -*- coding: utf-8 -*-
"""حقول إشعار المالك في «إعدادات محتوى الموقع» — الأرقام وبيانات Evolution."""
import frappe

FIELDS = [
	("sec_owner_alerts", "إشعار الطلبات الجديدة / New Order Alerts", "Section Break", None, None,
	 "لما عميل يطلب من الموقع، بتوصلك رسالة واتساب فيها تفاصيل الطلب."),
	("owner_alert_enabled", "ابعتلي إشعار بكل طلب جديد", "Check", None, "sec_owner_alerts", None),
	("owner_alert_numbers", "أرقام الإشعار", "Small Text", None, "owner_alert_enabled",
	 "رقم أو أكتر، مفصولين بفاصلة أو سطر جديد. مثال: 01114021275, 01016761856"),
	("cb_owner_alerts", "", "Column Break", None, "owner_alert_numbers", None),
	("evolution_instance", "رقم الواتساب المُرسِل", "Data", None, "cb_owner_alerts",
	 "اسم الـ instance في Evolution. الافتراضي: 1212"),
	("evolution_url", "رابط Evolution", "Data", None, "evolution_instance",
	 "سيبه فاضي عشان يستخدم http://localhost:8080"),
	("evolution_api_key", "مفتاح Evolution", "Password", None, "evolution_url", None),
]


def execute():
	added = []
	for fieldname, label, ftype, options, after, desc in FIELDS:
		name = f"Webshop Content Settings-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			continue
		cf = frappe.new_doc("Custom Field")
		cf.dt = "Webshop Content Settings"
		cf.fieldname, cf.label, cf.fieldtype = fieldname, label, ftype
		if options:
			cf.options = options
		if after:
			cf.insert_after = after
		if desc:
			cf.description = desc
		cf.flags.ignore_permissions = True
		cf.insert()
		added.append(label or fieldname)
	frappe.db.commit()
	frappe.clear_cache()

	s = frappe.get_single("Webshop Content Settings")
	if not s.get("evolution_instance"):
		s.evolution_instance = "1212"
	if not s.get("evolution_url"):
		s.evolution_url = "http://localhost:8080"
	if not s.get("evolution_api_key"):
		s.evolution_api_key = "islam123"
	if not s.get("owner_alert_numbers"):
		s.owner_alert_numbers = "01114021275, 01016761856"
	s.flags.ignore_permissions = True
	s.save()
	frappe.db.commit()

	print("حقول جديدة:", ", ".join(added) or "(موجودة)")
	print("  الأرقام:", s.get("owner_alert_numbers"))
	print("  الرقم المُرسِل:", s.get("evolution_instance"))
	print("  مفعّل؟", bool(s.get("owner_alert_enabled")), "— افتحه من الإعدادات لما تحب")
