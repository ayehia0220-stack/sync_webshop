# -*- coding: utf-8 -*-
"""يجرب مسار «محتاج مكالمة»: العلامة + التذكرة + إشعار الواتساب."""
import frappe
from sync_webshop.api import renewal

MOBILE = "01555000888"


def _clean():
	for n in frappe.get_all("Customer Subscription", filters={"mobile_number": MOBILE}, pluck="name"):
		frappe.delete_doc("Customer Subscription", n, force=1, ignore_permissions=True)
	for n in frappe.get_all("Renewal Conversation Log", filters={"mobile_number": ["like", "%1555000888"]}, pluck="name"):
		frappe.delete_doc("Renewal Conversation Log", n, force=1, ignore_permissions=True)
	for n in frappe.get_all("ToDo", filters={"description": ["like", "%1555000888%"]}, pluck="name"):
		frappe.delete_doc("ToDo", n, force=1, ignore_permissions=True)
	frappe.db.commit()


def execute():
	_clean()
	s = frappe.new_doc("Customer Subscription")
	s.customer_name = "عميل اختبار الدعم"
	s.mobile_number = MOBILE
	s.imei = "SUP-TEST-1"
	s.end_date = frappe.utils.add_days(frappe.utils.nowdate(), 4)
	s.reminder_active = 1
	s.conversation_state = renewal.STATE_AWAIT_CHOICE
	s.flags.ignore_permissions = True
	s.insert()
	frappe.db.commit()

	print("١) العميل رد بـ 1 (عايز الأسعار)")
	print("   ->", renewal.handle_reply(MOBILE, "1")["action"])

	print("\n٢) العميل رد بـ 2 (عايز موظف)")
	out = renewal.handle_reply(MOBILE, "2")
	print("   ->", out["action"])
	print("   الرد:", (out["reply"] or "")[:80])

	v = frappe.db.get_value("Customer Subscription", s.name,
	                        ["needs_call", "needs_call_since", "conversation_state"], as_dict=True)
	print("\n٣) العلامة في ERPNext")
	print("   محتاج مكالمة؟", "أيوه ✓" if v.needs_call else "لأ ✗")
	print("   من:", v.needs_call_since)
	print("   الحالة:", v.conversation_state)

	todos = frappe.get_all("ToDo", filters={"description": ["like", "%1555000888%"]},
	                       fields=["name", "priority"])
	print("\n٤) تذكرة الموظف:", f"{todos[0].name} (أولوية {todos[0].priority}) ✓" if todos else "✗")

	print("\n٥) إشعار الواتساب لـ 01066858027")
	sent = renewal._alert_support(
		{"customer_name": s.customer_name, "imei": s.imei, "name": s.name},
		MOBILE, "طلب مكالمة من خدمة العملاء")
	print("   ", "اتبعت ✓" if sent else "مااتبعتش ✗")

	print("\n٦) هيظهر في bord؟")
	print("   عملاء طالبين مكالمة:", frappe.db.count("Customer Subscription", {"needs_call": 1}))

	_clean()
	print("\n(اتمسحت بيانات الاختبار)")
