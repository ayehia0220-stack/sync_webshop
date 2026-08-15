# -*- coding: utf-8 -*-
"""
تشغيل شاشة المكالمة المنبثقة في ERPNext.

ERPNext مبيبعتش الشاشة لأي حد — بيبعتها للموظفين اللي **في وردية** على
وسيلة الاتصال. ومحتاج تلات حاجات موجودة:
  1. Employee Group فيه الموظفين
  2. Communication Medium اسمه زي `Call Log.medium` (عندنا "Issabel")
  3. Timeslots تغطي وقت المكالمة

من غير التلاتة دول كل حاجة تانية تبقى مظبوطة والشاشة متطلعش من غير أي رسالة خطأ.
"""
import frappe

MEDIUM = "Issabel"
GROUP = "فريق المكالمات"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def ensure_group():
	if frappe.db.exists("Employee Group", GROUP):
		doc = frappe.get_doc("Employee Group", GROUP)
	else:
		doc = frappe.new_doc("Employee Group")
		doc.employee_group_name = GROUP

	# كل موظف متربط بإكستنشن وعنده حساب دخول
	wanted = frappe.get_all("Employee",
	                        filters={"custom_extension": ["!=", ""], "user_id": ["!=", ""],
	                                 "status": "Active"},
	                        fields=["name", "employee_name", "user_id"])
	have = {r.employee for r in doc.employee_list}
	added = []
	for emp in wanted:
		if emp.name in have:
			continue
		doc.append("employee_list", {"employee": emp.name, "employee_name": emp.employee_name,
		                             "user_id": emp.user_id})
		added.append(emp.employee_name)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name, added, len(doc.employee_list)


def ensure_medium():
	if frappe.db.exists("Communication Medium", MEDIUM):
		doc = frappe.get_doc("Communication Medium", MEDIUM)
	else:
		doc = frappe.new_doc("Communication Medium")
		doc.communication_medium_name = MEDIUM
		doc.name = MEDIUM

	doc.communication_medium_type = "Voice"
	doc.communication_channel = "Phone"
	doc.disabled = 0

	# مواعيد على مدار اليوم — المكالمات مش بتلتزم بمواعيد العمل
	doc.timeslots = []
	for day in DAYS:
		doc.append("timeslots", {
			"day_of_week": day,
			"from_time": "00:00:00",
			"to_time": "23:59:59",
			"employee_group": GROUP,
		})
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def execute():
	group, added, total = ensure_group()
	print("مجموعة الموظفين: %s (%d عضو)" % (group, total))
	for a in added:
		print("   + اتضاف:", a)

	medium = ensure_medium()
	print("وسيلة الاتصال: %s — مواعيد 24 ساعة × 7 أيام" % medium)
	frappe.db.commit()
	frappe.clear_cache()

	# التحقق: هل ERPNext هيلاقي حد دلوقتي؟
	from erpnext.crm.doctype.utils import get_scheduled_employees_for_popup
	emails = get_scheduled_employees_for_popup(MEDIUM)
	print("\nالشاشة هتطلع عند: %s" % (emails or "محدش ✗"))
	return emails
