# -*- coding: utf-8 -*-
"""
أصناف خطتي التجديد + إضافة كل المستندات الجديدة لمساحة العمل «متجر دبونو».

خطة مدى الحياة عند دبونو صنفين مع بعض (2300 + 140 = 2440)، فالإعدادات بقت
جدول أصناف لكل خطة بدل صنف واحد.
"""
import json

import frappe

PLAN_ITEM = {
	"name": "Renewal Plan Item",
	"istable": 1,
	"fields": [
		{"fieldname": "item_code", "label": "الصنف / Item", "fieldtype": "Link",
		 "options": "Item", "reqd": 1, "in_list_view": 1},
		{"fieldname": "qty", "label": "الكمية", "fieldtype": "Float", "default": "1",
		 "in_list_view": 1},
		{"fieldname": "rate", "label": "السعر", "fieldtype": "Currency", "in_list_view": 1,
		 "description": "سيبه فاضي عشان ياخد سعر الصنف من قائمة أسعار ERPNext."},
	],
}

# الأصناف الفعلية عند دبونو — متحقق منها من قائمة الأسعار
YEARLY = [("Mi Coins - 1 Year", 1, 1040)]
LIFETIME = [("ET  Serial Life", 1, 2300), ("MI   Serial", 1, 140)]

# اختصارات مساحة العمل: (اللابل، الدوك تايب)
NEW_SHORTCUTS = [
	("تدريب المساعد", "Webshop Agent Training"),
	("إعدادات حملة التجديد", "Renewal Campaign Settings"),
	("قوالب رسائل التجديد", "Renewal Message Template"),
	("سجل محادثات التجديد", "Renewal Conversation Log"),
	("الاشتراكات", "Customer Subscription"),
	("تذاكر المتابعة", "ToDo"),
]

SECTIONS = [
	("المساعد الذكي", ["تدريب المساعد"]),
	("حملة تجديد الاشتراكات", ["إعدادات حملة التجديد", "قوالب رسائل التجديد",
	                            "الاشتراكات", "سجل محادثات التجديد", "تذاكر المتابعة"]),
]


def _sync_plan_item():
	spec = PLAN_ITEM
	if frappe.db.exists("DocType", spec["name"]):
		doc = frappe.get_doc("DocType", spec["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = spec["name"]
	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.istable = 1
	doc.editable_grid = 1
	doc.engine = "InnoDB"
	for idx, f in enumerate(spec["fields"], start=1):
		doc.append("fields", {**f, "idx": idx})
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def _swap_settings_fields():
	"""يشيل «صنف التجديد» المفرد ويحط جدول أصناف لكل خطة."""
	dt = frappe.get_doc("DocType", "Renewal Campaign Settings")
	fields = [f for f in dt.fields if f.fieldname != "renewal_item"]

	new = [
		{"fieldname": "yearly_items", "label": "أصناف خطة السنة", "fieldtype": "Table",
		 "options": "Renewal Plan Item",
		 "description": "البنود اللي بتتحط في أمر البيع لما العميل يجدد سنة."},
		{"fieldname": "sec_life_items", "label": "", "fieldtype": "Section Break"},
		{"fieldname": "lifetime_items", "label": "أصناف خطة مدى الحياة", "fieldtype": "Table",
		 "options": "Renewal Plan Item",
		 "description": "ممكن تحط أكتر من صنف — المجموع هو السعر النهائي."},
	]

	out, done = [], False
	for f in fields:
		out.append(f.as_dict())
		if f.fieldname == "auto_sales_order" and not done:
			out.extend(new)
			done = True
	if not done:
		out.extend(new)

	dt.fields = []
	for idx, f in enumerate(out, start=1):
		f = dict(f)
		f.pop("idx", None)
		f.pop("name", None)
		f.pop("parent", None)
		dt.append("fields", {**f, "idx": idx})
	dt.flags.ignore_permissions = True
	dt.flags.ignore_mandatory = True
	dt.save()


def _fill_plans():
	s = frappe.get_single("Renewal Campaign Settings")
	missing = []
	for code, _q, _r in YEARLY + LIFETIME:
		if not frappe.db.exists("Item", code):
			missing.append(code)
	if missing:
		return f"مالقيتش الأصناف دي: {missing}"

	if not s.yearly_items:
		for code, qty, rate in YEARLY:
			s.append("yearly_items", {"item_code": code, "qty": qty, "rate": rate})
	if not s.lifetime_items:
		for code, qty, rate in LIFETIME:
			s.append("lifetime_items", {"item_code": code, "qty": qty, "rate": rate})

	total_y = sum(r.qty * r.rate for r in s.yearly_items)
	total_l = sum(r.qty * r.rate for r in s.lifetime_items)
	s.price_yearly = total_y
	s.price_lifetime = total_l
	s.flags.ignore_permissions = True
	s.save()
	return f"خطة السنة {total_y:.0f} | خطة مدى الحياة {total_l:.0f}"


def _workspace():
	ws = frappe.get_doc("Workspace", "متجر دبونو")
	have = {s.label for s in ws.shortcuts}
	added = []
	for label, doctype in NEW_SHORTCUTS:
		if label in have:
			continue
		if not frappe.db.exists("DocType", doctype):
			continue
		ws.append("shortcuts", {"type": "DocType", "link_to": doctype, "label": label,
		                        "doc_view": ""})
		added.append(label)

	content = json.loads(ws.content or "[]")
	present = {b.get("data", {}).get("shortcut_name") for b in content if b.get("type") == "shortcut"}
	headers = {b.get("data", {}).get("text", "") for b in content if b.get("type") == "header"}

	for title, labels in SECTIONS:
		if not any(title in h for h in headers):
			content.append({"id": f"hdr{abs(hash(title)) % 10**8}", "type": "header",
			                "data": {"text": f'<span class="h4"><b>{title}</b></span>', "col": 12}})
		for label in labels:
			if label in present:
				continue
			if label not in {s.label for s in ws.shortcuts}:
				continue
			content.append({"id": f"sc{abs(hash(label)) % 10**8}", "type": "shortcut",
			                "data": {"shortcut_name": label, "col": 3}})
			present.add(label)

	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return added


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		_sync_plan_item()
		_swap_settings_fields()
	finally:
		frappe.conf["developer_mode"] = was_dev or 0
	frappe.db.commit()
	frappe.clear_cache()

	print("الأسعار:", _fill_plans())
	print("اتضاف لمساحة العمل:", ", ".join(_workspace()) or "(كانوا موجودين)")
	frappe.db.commit()
	frappe.clear_cache()

	s = frappe.get_single("Renewal Campaign Settings")
	print("\nخطة السنة:")
	for r in s.yearly_items:
		print(f"   {r.item_code} × {r.qty:.0f} = {r.rate:.0f}")
	print("خطة مدى الحياة:")
	for r in s.lifetime_items:
		print(f"   {r.item_code} × {r.qty:.0f} = {r.rate:.0f}")
