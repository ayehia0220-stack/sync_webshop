# -*- coding: utf-8 -*-
"""
ربط الأرقام الداخلية بالموظفين عشان شاشة المكالمة تفتح على الشخص الصح.

ERPNext بيدوّر على الموظف بـ `cell_number` (رقم الموبايل)، والسنترال بيبعت
رقم داخلي. بدل ما نمسح أرقام الموبايل، بنضيف حقل للداخلي وبنترجم من عنده
— فالبيانات الأصلية زي ما هي والـ popup الأصلي بيشتغل من غير تعديل.
"""
import frappe

EXTENSIONS = {
	"890": "Doha Samir Abdallah",
	# "67": "…",   # إسلام — مستني كارت الموظف
}


def _add_field():
	name = "Employee-custom_extension"
	if frappe.db.exists("Custom Field", name):
		return False
	cf = frappe.new_doc("Custom Field")
	cf.dt = "Employee"
	cf.fieldname = "custom_extension"
	cf.label = "الرقم الداخلي في السنترال"
	cf.fieldtype = "Data"
	cf.insert_after = "cell_number"
	cf.description = "رقم التحويلة في Issabel. لما مكالمة تيجي عليه بتفتح شاشة العميل عند الموظف."
	cf.flags.ignore_permissions = True
	cf.insert()
	return True


def execute():
	print("حقل الداخلي:", "اتضاف" if _add_field() else "موجود")
	frappe.db.commit()
	frappe.clear_cache()

	for ext, employee in EXTENSIONS.items():
		if not frappe.db.exists("Employee", employee):
			print(f"  ✗ مالقيتش الموظف: {employee}")
			continue
		frappe.db.set_value("Employee", employee, "custom_extension", ext, update_modified=False)
		row = frappe.db.get_value("Employee", employee,
		                          ["employee_name", "user_id", "cell_number"], as_dict=True)
		print(f"  ✓ داخلي {ext} → {row.employee_name} | {row.user_id or '(مفيش مستخدم)'}"
		      f" | موبايل: {row.cell_number or '(فاضي)'}")
	frappe.db.commit()

	print("\nالمربوطين دلوقتي:")
	for r in frappe.get_all("Employee", filters={"custom_extension": ["!=", ""]},
	                        fields=["employee_name", "custom_extension", "user_id"]):
		print(f"   {r.custom_extension} → {r.employee_name} ({r.user_id or 'مفيش مستخدم'})")
