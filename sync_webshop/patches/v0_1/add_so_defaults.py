# -*- coding: utf-8 -*-
"""أوامر البيع عند دبونو محتاجة شريك بيع ومركز تكلفة وفريق بيع — بتتحط من الإعدادات."""
import frappe

FIELDS = [
	("sales_partner", "شريك البيع", "Link", "Sales Partner", "price_list", "إجباري على أوامر البيع."),
	("cost_center", "مركز التكلفة", "Link", "Cost Center", "sales_partner", "لتجديدات GPS استخدم مركز الـ GPS."),
	("sales_person", "مندوب البيع", "Link", "Sales Person", "cost_center", "بيتحط بنسبة 100%."),
]


def execute():
	added = []
	for fieldname, label, ftype, options, after, desc in FIELDS:
		name = f"Renewal Campaign Settings-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			continue
		cf = frappe.new_doc("Custom Field")
		cf.dt = "Renewal Campaign Settings"
		cf.fieldname, cf.label, cf.fieldtype = fieldname, label, ftype
		cf.options, cf.insert_after, cf.description = options, after, desc
		cf.flags.ignore_permissions = True
		cf.insert()
		added.append(label)
	frappe.db.commit()
	frappe.clear_cache()

	# القيم من آخر أوامر بيع حقيقية
	defaults = {
		"price_list": "ويب سايت",
		"sales_partner": "عام",
		"cost_center": "1112 - GPS - DP",
		"sales_person": "Doha",
	}
	s = frappe.get_single("Renewal Campaign Settings")
	for key, value in defaults.items():
		dt = {"price_list": "Price List", "sales_partner": "Sales Partner",
		      "cost_center": "Cost Center", "sales_person": "Sales Person"}[key]
		if frappe.db.exists(dt, value) and not s.get(key):
			s.set(key, value)
	s.flags.ignore_permissions = True
	s.save()
	frappe.db.commit()

	print("حقول جديدة:", ", ".join(added) or "(موجودة)")
	for key in defaults:
		print(f"  {key} = {s.get(key)}")
