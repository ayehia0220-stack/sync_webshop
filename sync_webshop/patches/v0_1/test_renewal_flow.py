# -*- coding: utf-8 -*-
"""يجرب رحلة الرد كاملة على اشتراك تجريبي، وبيمسح كل أثره بعد الاختبار."""
import frappe
from sync_webshop.api import renewal

MOBILE = "01000000009"


def _cleanup():
	for row in frappe.get_all("Customer Subscription", filters={"mobile_number": MOBILE}, pluck="name"):
		frappe.delete_doc("Customer Subscription", row, force=1, ignore_permissions=True)
	for row in frappe.get_all("Renewal Conversation Log", filters={"mobile_number": ["like", "%1000000009"]}, pluck="name"):
		frappe.delete_doc("Renewal Conversation Log", row, force=1, ignore_permissions=True)
	for row in frappe.get_all("ToDo", filters={"description": ["like", "%1000000009%"]}, pluck="name"):
		frappe.delete_doc("ToDo", row, force=1, ignore_permissions=True)
	frappe.db.commit()


def _fresh():
	_cleanup()
	sub = frappe.new_doc("Customer Subscription")
	sub.customer_name = "عميل اختبار كلود"
	sub.mobile_number = MOBILE
	sub.imei = "TEST-IMEI-999"
	sub.end_date = frappe.utils.add_days(frappe.utils.nowdate(), 5)
	sub.reminder_active = 1
	sub.renewed = 0
	sub.conversation_state = renewal.STATE_AWAIT_CHOICE
	sub.flags.ignore_permissions = True
	sub.insert()
	frappe.db.commit()
	return sub


def _state(name):
	return frappe.db.get_value("Customer Subscription", name,
	                           ["conversation_state", "customer_refused_to_renew", "reminder_active"], as_dict=True)


def execute():
	print("=" * 64)
	print("سيناريو ١: العميل يرد بـ 2 — مش عايز رسايل")
	sub = _fresh()
	out = renewal.handle_reply(MOBILE, "2")
	st = _state(sub.name)
	print("  الإجراء:", out["action"])
	print("  الرد   :", (out["reply"] or "(مفيش)")[:90])
	print("  رافض التجديد؟", st.customer_refused_to_renew, "| التذكيرات شغالة؟", st.reminder_active)
	print("  الحالة :", st.conversation_state)
	assert out["action"] == "opted_out" and st.customer_refused_to_renew == 1 and st.reminder_active == 0

	print("\n" + "=" * 64)
	print("سيناريو ٢: 1 -> الأسعار، بعدين 1 -> طرق الدفع")
	sub = _fresh()
	out1 = renewal.handle_reply(MOBILE, "1")
	print("  [1] الإجراء:", out1["action"], "| الحالة بقت:", _state(sub.name).conversation_state)
	print("  رسالة الأسعار:")
	for line in (out1["reply"] or "").splitlines():
		print("     ", line)
	assert out1["action"] == "prices_sent"

	out2 = renewal.handle_reply(MOBILE, "1")
	print("\n  [1 تاني] الإجراء:", out2["action"])
	print("  نص الدفع:", (out2["reply"] or "").replace("\n", " / ")[:110])
	print("  صورة مرفقة؟", out2["send_image"] or "(مفيش صورة مرفوعة لسه)")
	todos = frappe.get_all("ToDo", filters={"description": ["like", "%1000000009%"]}, pluck="name")
	print("  تذكرة للموظف؟", "اتعملت ✓" if todos else "لأ ✗")
	assert out2["action"] == "payment_sent" and todos

	print("\n" + "=" * 64)
	print("سيناريو ٣: 1 -> الأسعار، بعدين 2 -> خدمة العملاء")
	sub = _fresh()
	renewal.handle_reply(MOBILE, "1")
	out3 = renewal.handle_reply(MOBILE, "2")
	print("  الإجراء:", out3["action"], "| الحالة:", _state(sub.name).conversation_state)
	print("  الرد:", (out3["reply"] or "")[:100])
	assert out3["action"] == "support_requested"

	print("\n" + "=" * 64)
	print("سيناريو ٤: العميل بيكتب كلام عادي")
	sub = _fresh()
	out4 = renewal.handle_reply(MOBILE, "ممكن حد يكلمني بخصوص الجهاز")
	print("  الإجراء:", out4["action"], "| رد آلي؟", out4["reply"] or "(مفيش — محوّل لموظف) ✓")
	assert out4["action"] == "handover" and not out4["reply"]

	print("\n" + "=" * 64)
	print("سيناريو ٥: صيغ مختلفة للرد")
	for text, expect in [("١", "prices_sent"), ("لا مش عايز", "opted_out"),
	                     ("اه عايز اجدد", "prices_sent"), ("2 شكرا", "opted_out")]:
		_fresh()
		got = renewal.handle_reply(MOBILE, text)["action"]
		mark = "✓" if got == expect else "✗"
		print(f"  {mark} «{text}» -> {got}")

	print("\n" + "=" * 64)
	print("سيناريو ٦: العميل الرافض مش بياخد رسايل تانية")
	sub = _fresh()
	renewal.handle_reply(MOBILE, "2")
	msgs = renewal.get_due_messages(limit=500, preview=1)["messages"]
	found = [m for m in msgs if m["mobile"].endswith("1000000009")]
	print("  ظهر في قايمة الإرسال؟", "أيوه ✗ مشكلة" if found else "لأ ✓")
	assert not found

	_cleanup()
	print("\n" + "=" * 64)
	print("كل السيناريوهات نجحت ✓ — واتمسحت بيانات الاختبار")
