# -*- coding: utf-8 -*-
"""
يربط بوابات المتجر بـ Mode of Payment بتاع ERPNext بدل ما تكون بديل عنها.

`Mode of Payment` هو المصدر الرسمي (22 طريقة عند دبونو، مربوطة بحسابات).
`Webshop Payment Gateway` بقى «إعدادات عرض في المتجر» لطريقة موجودة أصلًا:
النص اللي يشوفه العميل، ومفاتيح البوابة الإلكترونية، وترتيب الظهور.
"""
import frappe

# الربط الواضح بس — الباقي المالك يختاره بنفسه
OBVIOUS = {
	"Cash on Delivery": ["Cash", "نقدي", "Cash on Delivery"],
	"Fawry": ["Fawry", "فوري"],
}


def _add_field():
	name = "Webshop Payment Gateway-mode_of_payment"
	if frappe.db.exists("Custom Field", name):
		return False
	cf = frappe.new_doc("Custom Field")
	cf.dt = "Webshop Payment Gateway"
	cf.fieldname = "mode_of_payment"
	cf.label = "طريقة الدفع في ERPNext"
	cf.fieldtype = "Link"
	cf.options = "Mode of Payment"
	cf.insert_after = "enabled"
	cf.reqd = 0
	cf.in_list_view = 1
	cf.description = ("اختار من طرق الدفع الموجودة في ERPNext. دي هي الطريقة الرسمية "
	                  "اللي بتترحّل عليها الفلوس — المستند ده بيتحكم في شكلها للعميل بس.")
	cf.flags.ignore_permissions = True
	cf.insert()
	return True


def _link_existing():
	modes = frappe.get_all("Mode of Payment", pluck="name")
	lower = {m.lower(): m for m in modes}
	linked, manual = [], []
	for gw in frappe.get_all("Webshop Payment Gateway", fields=["name", "enabled"]):
		doc = frappe.get_doc("Webshop Payment Gateway", gw.name)
		if doc.get("mode_of_payment"):
			continue
		match = None
		for candidate in OBVIOUS.get(gw.name, []):
			if candidate in modes:
				match = candidate
				break
			if candidate.lower() in lower:
				match = lower[candidate.lower()]
				break
		if match:
			doc.db_set("mode_of_payment", match, update_modified=False)
			linked.append(f"{gw.name} → {match}")
		else:
			manual.append(f"{gw.name} (مفعّل: {gw.enabled})")
	return linked, manual


def execute():
	print("حقل الربط:", "اتضاف" if _add_field() else "موجود")
	frappe.db.commit()
	frappe.clear_cache()

	linked, manual = _link_existing()
	print("\nاتربط تلقائي:")
	for l in linked:
		print("   ✓", l)
	print("\nمحتاج تختارها بنفسك:")
	for m in manual:
		print("   •", m)
	frappe.db.commit()

	print("\nطرق الدفع المتاحة في ERPNext للاختيار منها:")
	for m in frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name"):
		print("   -", m)
