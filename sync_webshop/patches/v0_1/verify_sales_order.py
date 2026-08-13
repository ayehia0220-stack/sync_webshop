# -*- coding: utf-8 -*-
"""يجرب أمر البيع للخطتين على عميل تجريبي، وبيلغي ويمسح كل حاجة بعدها."""
import frappe
from sync_webshop.api import renewal

MOBILE = "01555000777"
CUST = "عميل اختبار أمر البيع"


def _cleanup():
	for dt, filt in [("Sales Order", {"customer": CUST}),
	                 ("Customer Subscription", {"mobile_number": MOBILE}),
	                 ("Renewal Conversation Log", {"mobile_number": ["like", "%1555000777"]})]:
		for n in frappe.get_all(dt, filters=filt, pluck="name"):
			d = frappe.get_doc(dt, n)
			if getattr(d, "docstatus", 0) == 1:
				d.cancel()
			frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
	if frappe.db.exists("Customer", CUST):
		frappe.delete_doc("Customer", CUST, force=1, ignore_permissions=True)
	frappe.db.commit()


def execute():
	_cleanup()
	c = frappe.new_doc("Customer")
	c.customer_name = CUST
	c.customer_type = "Individual"
	c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	c.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	c.custom_mobile_phone = MOBILE   # إجباري على العملاء عند دبونو
	c.flags.ignore_permissions = True
	c.insert()

	s = frappe.new_doc("Customer Subscription")
	s.customer_name = CUST
	s.mobile_number = MOBILE
	s.imei = "SO-TEST-001"
	s.end_date = frappe.utils.add_days(frappe.utils.nowdate(), 3)
	s.reminder_active = 1
	s.flags.ignore_permissions = True
	s.insert()
	frappe.db.commit()
	print("اتعمل عميل واشتراك تجريبي\n")

	for plan, label in [("yearly", "خطة السنة"), ("lifetime", "خطة مدى الحياة")]:
		if plan == "lifetime":
			frappe.db.set_value("Customer Subscription", s.name, "renewed", 0)
			frappe.db.set_value("Customer Subscription", s.name, "end_date",
			                    frappe.utils.add_days(frappe.utils.nowdate(), 3))
			frappe.db.commit()
		print("=" * 58)
		print(label)
		out = renewal.record_payment(s.name, plan=plan)
		if not out.get("ok"):
			print("  ✗ فشل:", out.get("reason"))
			continue
		so = frappe.get_doc("Sales Order", out["sales_order"])
		print(f"  ✓ أمر بيع {so.name} | الحالة: {so.status} | معتمد: {so.docstatus == 1}")
		for it in so.items:
			print(f"     {it.item_code} × {it.qty:.0f} = {it.rate:,.0f}")
		print(f"  الإجمالي: {so.grand_total:,.0f} جنيه")
		sub = frappe.get_doc("Customer Subscription", s.name)
		print(f"  الاشتراك: مجدد={sub.renewed} | تاريخ الانتهاء الجديد={sub.end_date}")

	print("\n" + "=" * 58)
	print("تجربة قيد الدفع (مقفول في الإعدادات دلوقتي):")
	st = frappe.get_single("Renewal Campaign Settings")
	print("  auto_payment_entry =", st.auto_payment_entry,
	      "| حساب الاستلام =", st.payment_account or "(مش محدد)")

	_cleanup()
	print("\n✓ اتلغت وامّسحت كل بيانات الاختبار — مفيش أثر في حساباتك")
	print("  أوامر بيع باسم العميل التجريبي دلوقتي:",
	      frappe.db.count("Sales Order", {"customer": CUST}))
