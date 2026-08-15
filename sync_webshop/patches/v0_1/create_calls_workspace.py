# -*- coding: utf-8 -*-
"""مساحة عمل «المكالمات» — كل حاجة تخص السنترال في مكان واحد."""
import json

import frappe

WS = "المكالمات"
MEDIUM = "Issabel"

SHORTCUTS = [
	("سجل المكالمات", "Call Log"),
	("العملاء", "Customer"),
	("جهات الاتصال", "Contact"),
	("الموظفين والتحويلات", "Employee"),
	("فريق المكالمات", "Employee Group"),
	("وسيلة الاتصال والورديات", "Communication Medium"),
	("تذاكر المتابعة", "ToDo"),
]

# (اللابل، الفلتر، الدالة، الحقل)
CARDS = [
	("مكالمات النهاردة", {"medium": MEDIUM}, "Count", None),
	("مكالمات فايتة", {"medium": MEDIUM, "status": ["in", ["No Answer", "Missed"]]}, "Count", None),
	("مكالمات مردود عليها", {"medium": MEDIUM, "status": "Completed"}, "Count", None),
	("أرقام مش في العملاء", {"medium": MEDIUM, "customer": ["is", "not set"]}, "Count", None),
	("إجمالي دقايق المكالمات", {"medium": MEDIUM, "status": "Completed"}, "Sum", "duration"),
]


def _block(btype, data):
	return {"id": f"{btype}{abs(hash(json.dumps(data, sort_keys=True))) % 10**9}",
	        "type": btype, "data": data}


def _card(label, filters, function, field):
	name = label
	doc = frappe.get_doc("Number Card", name) if frappe.db.exists("Number Card", name) else frappe.new_doc("Number Card")
	doc.name = name
	doc.label = label
	doc.document_type = "Call Log"
	doc.function = function
	if field:
		doc.aggregate_function_based_on = field
	rows = []
	for k, v in filters.items():
		op, val = (v[0], v[1]) if isinstance(v, list) else ("=", v)
		rows.append(["Call Log", k, op, val, False])
	doc.filters_json = json.dumps(rows)
	doc.is_public = 1
	doc.show_percentage_stats = 0
	doc.flags.ignore_permissions = True
	doc.save()
	return name


def execute():
	ws = frappe.get_doc("Workspace", WS) if frappe.db.exists("Workspace", WS) else frappe.new_doc("Workspace")
	if not ws.get("name"):
		ws.name = WS
	ws.title = WS
	ws.label = WS
	ws.module = "Sync Webshop"
	ws.public = 1
	ws.icon = "call"
	ws.sequence_id = 3

	ws.shortcuts = []
	for label, dt in SHORTCUTS:
		if frappe.db.exists("DocType", dt):
			ws.append("shortcuts", {"type": "DocType", "link_to": dt, "label": label})

	ws.number_cards = []
	made = []
	for label, filters, func, field in CARDS:
		name = _card(label, filters, func, field)
		ws.append("number_cards", {"number_card_name": name, "label": label})
		made.append(label)

	content = [_block("header", {"text": '<span class="h4"><b>أرقام المكالمات</b></span>', "col": 12})]
	for label in made:
		content.append(_block("number_card", {"number_card_name": label, "col": 4}))
	content.append(_block("spacer", {"col": 12}))
	content.append(_block("header", {"text": '<span class="h4"><b>افتح بسرعة</b></span>', "col": 12}))
	for s in ws.shortcuts:
		content.append(_block("shortcut", {"shortcut_name": s.label, "col": 3}))

	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	frappe.db.commit()
	frappe.clear_cache()

	print(f"مساحة «{WS}»: {len(ws.number_cards)} مؤشر + {len(ws.shortcuts)} اختصار")
	print("\nالأرقام دلوقتي:")
	for label, filters, func, field in CARDS:
		f = {k: (v if not isinstance(v, list) else v) for k, v in filters.items()}
		try:
			if func == "Count":
				val = frappe.db.count("Call Log", f)
			else:
				r = frappe.get_all("Call Log", filters=f, fields=[f"sum({field}) as t"])
				val = f"{round((r[0].t or 0) / 60)} دقيقة"
		except Exception as e:
			val = f"— ({str(e)[:30]})"
		print(f"   {label}: {val}")
