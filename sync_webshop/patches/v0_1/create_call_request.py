# -*- coding: utf-8 -*-
"""
اتصال بضغطة من ERPNext.

السنترال على شبكة داخلية والـ ERP على سيرفر برّه، فالـ ERP **مش بيقدر**
ينده السنترال. الحل: الطلب بيتسجّل هنا، والجسر اللي على السنترال بيسأل
كل تلات ثواني وينفّذه. نفس اتجاه الاتصال الآمن — السنترال هو اللي بيبادر.

الاتصال بيرن على تليفون الموظف الأول، ولما يرد السنترال بيوصله بالعميل.
"""
import frappe
from frappe.utils import now_datetime

STATUS_PENDING = "في الانتظار"
STATUS_SENT = "اتنفذ"
STATUS_FAILED = "فشل"


def _field(fieldname, label, fieldtype, **kw):
	f = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	f.update(kw)
	return f


SPEC = {
	"name": "Call Request",
	"autoname": "hash",
	"title_field": "to_number",
	"fields": [
		_field("to_number", "الرقم المطلوب", "Data", reqd=1, in_list_view=1),
		_field("extension", "من تحويلة", "Data", reqd=1, in_list_view=1),
		_field("status", "الحالة", "Select", in_list_view=1,
		       options="\n".join([STATUS_PENDING, STATUS_SENT, STATUS_FAILED]),
		       default=STATUS_PENDING),
		_field("cb1", "", "Column Break"),
		_field("requested_by", "طلبها", "Link", options="User", in_list_view=1),
		_field("customer", "العميل", "Link", options="Customer"),
		_field("sec_result", "", "Section Break"),
		_field("error", "الخطأ", "Small Text", read_only=1),
	],
}

PERMISSIONS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
	{"role": "Sales User", "read": 1, "write": 1, "create": 1},
]


def ensure_doctype():
	if frappe.db.exists("DocType", SPEC["name"]):
		doc = frappe.get_doc("DocType", SPEC["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = SPEC["name"]
	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.autoname = SPEC["autoname"]
	doc.title_field = SPEC["title_field"]
	doc.engine = "InnoDB"
	for idx, f in enumerate(SPEC["fields"], start=1):
		doc.append("fields", {**f, "idx": idx})
	doc.permissions = []
	for p in PERMISSIONS:
		doc.append("permissions", p)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		name = ensure_doctype()
	finally:
		frappe.conf["developer_mode"] = was_dev or 0
	frappe.db.commit()
	frappe.clear_cache()
	print("DocType:", name)

	# زرار الاتصال على كارت العميل
	if not frappe.db.exists("Custom Field", "Customer-custom_call_button"):
		cf = frappe.new_doc("Custom Field")
		cf.dt = "Customer"
		cf.fieldname = "custom_call_button"
		cf.label = "📞 اتصل بالعميل"
		cf.fieldtype = "Button"
		cf.insert_after = "custom_mobile_phone"
		cf.flags.ignore_permissions = True
		cf.insert()
		frappe.db.commit()
		print("اتضاف زرار الاتصال على كارت العميل")
	else:
		print("زرار الاتصال موجود")
