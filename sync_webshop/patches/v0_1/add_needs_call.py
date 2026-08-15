# -*- coding: utf-8 -*-
"""علامة «محتاج مكالمة» على الاشتراك + رقم يوصله إشعار لما عميل يطلب الدعم."""
import frappe

FIELDS = [
	("needs_call", "محتاج مكالمة من خدمة العملاء", "Check", None, "conversation_state",
	 "بتتحط تلقائيًا لما العميل يطلب موظف. شيلها بإيدك بعد ما تتكلم معاه."),
	("needs_call_since", "طلب المكالمة من", "Datetime", None, "needs_call", None),
]

SETTING_FIELDS = [
	("support_alert_number", "رقم إشعار خدمة العملاء", "Data", "support_reply",
	 "لما عميل يطلب موظف، بتوصل رسالة واتساب على الرقم ده."),
]


def _cf(dt, fieldname, label, ftype, options, after, desc):
	name = f"{dt}-{fieldname}"
	if frappe.db.exists("Custom Field", name):
		return False
	cf = frappe.new_doc("Custom Field")
	cf.dt = dt
	cf.fieldname, cf.label, cf.fieldtype = fieldname, label, ftype
	if options:
		cf.options = options
	if after:
		cf.insert_after = after
	if desc:
		cf.description = desc
	cf.flags.ignore_permissions = True
	cf.insert()
	return True


def execute():
	added = []
	for fieldname, label, ftype, options, after, desc in FIELDS:
		if _cf("Customer Subscription", fieldname, label, ftype, options, after, desc):
			added.append(label)
	for fieldname, label, ftype, after, desc in SETTING_FIELDS:
		if _cf("Renewal Campaign Settings", fieldname, label, ftype, None, after, desc):
			added.append(label)
	frappe.db.commit()
	frappe.clear_cache()

	if not frappe.db.get_single_value("Renewal Campaign Settings", "support_alert_number"):
		frappe.db.set_single_value("Renewal Campaign Settings", "support_alert_number", "01066858027")
	frappe.db.commit()

	print("حقول جديدة:", ", ".join(added) or "(موجودة)")
	print("رقم الإشعار:", frappe.db.get_single_value("Renewal Campaign Settings", "support_alert_number"))
