# -*- coding: utf-8 -*-
"""
حساب للمالك مربوط بكارت موظفه وبالإكستنشن 67.

مش بيتحط باسورد هنا — ERPNext بيبعت للمستخدم رابط يحط بيه باسورده بنفسه.
"""
import frappe

EMAIL = "a.yehia0220@gmail.com"
EMPLOYEE = "Abdelkhalek Yehia Abdelkhalek"
EXTENSION = "67"
GROUP = "فريق المكالمات"


def execute():
	# ١) المستخدم
	if frappe.db.exists("User", EMAIL):
		user = frappe.get_doc("User", EMAIL)
		print("المستخدم موجود بالفعل:", EMAIL)
	else:
		user = frappe.new_doc("User")
		user.email = EMAIL
		user.first_name = "عبدالخالق"
		user.last_name = "يحيى"
		user.user_type = "System User"
		user.send_welcome_email = 1
		user.flags.ignore_permissions = True
		user.insert()
		print("اتعمل مستخدم:", EMAIL)

	for role in ("System Manager", "Sales Manager", "Sales User"):
		if frappe.db.exists("Role", role) and role not in [r.role for r in user.roles]:
			user.append("roles", {"role": role})
	user.enabled = 1
	user.flags.ignore_permissions = True
	user.save()
	print("  الصلاحيات:", ", ".join(r.role for r in user.roles))

	# ٢) الكارت
	emp = frappe.get_doc("Employee", EMPLOYEE)
	emp.db_set("user_id", EMAIL, update_modified=False)
	emp.db_set("custom_extension", EXTENSION, update_modified=False)
	if emp.status != "Active":
		emp.db_set("status", "Active", update_modified=False)
	print("  كارت الموظف:", emp.employee_name, "| داخلي", EXTENSION, "| الحالة", emp.status)

	# ٣) فريق المكالمات
	group = frappe.get_doc("Employee Group", GROUP)
	if EMPLOYEE not in {r.employee for r in group.employee_list}:
		group.append("employee_list", {"employee": EMPLOYEE,
		                               "employee_name": emp.employee_name,
		                               "user_id": EMAIL})
		group.flags.ignore_permissions = True
		group.save()
		print("  اتضاف لفريق المكالمات")

	frappe.db.commit()
	frappe.clear_cache()

	from erpnext.crm.doctype.utils import get_scheduled_employees_for_popup
	print("\nالشاشة هتطلع عند:", get_scheduled_employees_for_popup("Issabel"))
	print("\nالمربوطين بالإكستنشنات:")
	for r in frappe.get_all("Employee", filters={"custom_extension": ["!=", ""]},
	                        fields=["employee_name", "custom_extension", "user_id"]):
		print(f"   {r.custom_extension} → {r.employee_name} ({r.user_id})")
