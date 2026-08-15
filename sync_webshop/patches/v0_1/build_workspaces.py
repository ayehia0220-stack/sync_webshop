# -*- coding: utf-8 -*-
"""
ثلاث مساحات عمل: متجر دبونو (بروابطها راجعة)، تجديد الاشتراك، و bord.

`bord` لوحة تقصير فقط — بتعرض اللي متأخر أو منسي، مفيهاش مبيعات ولا أرباح.
الهدف إن المالك يفتحها فيشوف اللي محتاج تدخّل، مش أرقام يتفرج عليها.
"""
import json

import frappe

TODAY = "frappe.utils.nowdate()"


def _block(btype, data):
	return {"id": f"{btype}{abs(hash(json.dumps(data, sort_keys=True))) % 10**9}",
	        "type": btype, "data": data}


# ─────────────────── لوحة التقصير ───────────────────
CARDS = [
	("فواتير مستحقة لم تُحصّل", "Sales Invoice",
	 {"status": ["in", ["Overdue", "Unpaid", "Partly Paid"]], "docstatus": 1}, "Count", None),
	("أوامر بيع فات ميعاد تسليمها", "Sales Order",
	 {"delivery_date": ["<", "Today"], "status": ["not in", ["Completed", "Closed"]], "docstatus": 1},
	 "Count", None),
	("إذون تسليم لم تُفوتر", "Delivery Note", {"status": "To Bill", "docstatus": 1}, "Count", None),
	("قضايا فات تاريخ متابعتها", "Legal Case",
	 {"following_date": ["<", "Today"], "case_status": ["not in", ["تم التنفيذ"]]}, "Count", None),
	("إيصالات لم تُسلَّم للمحامي", "Legal Case",
	 {"موقف_أصل_الإيصال": "لم يتم التسليم"}, "Count", None),
	("عملاء طالبين مكالمة", "Customer Subscription",
	 {"needs_call": 1}, "Count", None),
	("مهام مفتوحة على الفريق", "ToDo", {"status": "Open"}, "Count", None),
	("زيارات مناديب فاشلة", "Sales Visit", {"visit_status": "Failed"}, "Count", None),
	("مبلغ مستحق على العملاء", "Sales Invoice",
	 {"status": ["in", ["Overdue", "Unpaid", "Partly Paid"]], "docstatus": 1},
	 "Sum", "outstanding_amount"),
]

BORD_SHORTCUTS = [
	("الفواتير", "Sales Invoice"),
	("أوامر البيع", "Sales Order"),
	("إذون التسليم", "Delivery Note"),
	("القضايا", "Legal Case"),
	("زيارات المناديب", "Sales Visit"),
	("المهام والتذاكر", "ToDo"),
	("الاشتراكات", "Customer Subscription"),
	("العملاء", "Customer"),
]

RENEWAL_SHORTCUTS = [
	("إعدادات حملة التجديد", "Renewal Campaign Settings"),
	("قوالب رسائل التجديد", "Renewal Message Template"),
	("الاشتراكات", "Customer Subscription"),
	("سجل محادثات التجديد", "Renewal Conversation Log"),
	("تذاكر المتابعة", "ToDo"),
	("تدريب المساعد", "Webshop Agent Training"),
]

# روابط «متجر دبونو» متجمّعة في كروت — من غير Card Break مبتظهرش
STORE_CARDS = [
	("محتوى الموقع وشكله", ["إعدادات المظهر", "محتوى الموقع", "الشريط العلوي",
	                        "التذييل", "النافذة المنبثقة", "صفحات الموقع"]),
	("المنتجات والأسعار", ["الأصناف", "مجموعات الأصناف", "أسعار الأصناف", "إعدادات المنتجات"]),
	("الطلبات والدفع", ["أوامر البيع", "إعدادات الدفع", "شركات الشحن", "طرق الدفع",
	                    "قواعد الشحن (قديم)", "السلات المتروكة"]),
	("المساعد والبوتات", ["إعدادات المساعد", "مهارات المساعد", "مستخدمو تليجرام",
	                      "سجل المحادثات", "أسئلة وأجوبة", "سجل الأسئلة"]),
	("إعدادات فنية", ["تقسيم العملاء", "إعدادات الـ API", "إعدادات SEO", "حساب البريد"]),
]


def _number_card(label, doctype, filters, function, field):
	if not frappe.db.exists("DocType", doctype):
		return None
	name = f"bord — {label}"
	doc = frappe.get_doc("Number Card", name) if frappe.db.exists("Number Card", name) else frappe.new_doc("Number Card")
	doc.name = name
	doc.label = label
	doc.document_type = doctype
	doc.function = function
	if field:
		doc.aggregate_function_based_on = field
	doc.filters_json = json.dumps([
		[doctype, k, (v[0] if isinstance(v, list) else "="), (v[1] if isinstance(v, list) else v), False]
		for k, v in filters.items()
	])
	doc.is_public = 1
	doc.show_percentage_stats = 0
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def _ensure_workspace(name, title, icon, sequence):
	if frappe.db.exists("Workspace", name):
		ws = frappe.get_doc("Workspace", name)
	else:
		ws = frappe.new_doc("Workspace")
		ws.name = name
	ws.title = title
	ws.label = name
	ws.module = "Sync Webshop"
	ws.public = 1
	ws.icon = icon
	ws.sequence_id = sequence
	return ws


def _shortcuts(ws, pairs):
	have = {s.label for s in ws.shortcuts}
	for label, doctype in pairs:
		if label in have or not frappe.db.exists("DocType", doctype):
			continue
		ws.append("shortcuts", {"type": "DocType", "link_to": doctype, "label": label})


def build_renewal_workspace():
	ws = _ensure_workspace("تجديد الاشتراك", "تجديد الاشتراك", "review", 2)
	ws.shortcuts = []
	_shortcuts(ws, RENEWAL_SHORTCUTS)
	content = [_block("header", {"text": '<span class="h4"><b>حملة تجديد الاشتراكات</b></span>', "col": 12})]
	for label, _dt in RENEWAL_SHORTCUTS:
		if label in {s.label for s in ws.shortcuts}:
			content.append(_block("shortcut", {"shortcut_name": label, "col": 3}))
	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return ws.name


def build_bord():
	ws = _ensure_workspace("bord", "bord — لوحة التقصير", "dashboard", 0)
	ws.shortcuts = []
	ws.number_cards = []
	_shortcuts(ws, BORD_SHORTCUTS)

	made = []
	for label, dt, filters, func, field in CARDS:
		card = _number_card(label, dt, filters, func, field)
		if card:
			ws.append("number_cards", {"number_card_name": card, "label": label})
			made.append(label)

	content = [_block("header", {"text": '<span class="h4"><b>محتاج تدخّل دلوقتي</b></span>', "col": 12})]
	for label in made:
		content.append(_block("number_card", {"number_card_name": f"bord — {label}", "col": 4}))
	content.append(_block("header", {"text": '<span class="h4"><b>افتح بسرعة</b></span>', "col": 12}))
	for label, _dt in BORD_SHORTCUTS:
		if label in {s.label for s in ws.shortcuts}:
			content.append(_block("shortcut", {"shortcut_name": label, "col": 3}))
	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return ws.name, made


def rebuild_store():
	"""يرجّع روابط «متجر دبونو» تبان، ويشيل قسم التجديد منها."""
	ws = frappe.get_doc("Workspace", "متجر دبونو")

	renewal_labels = {label for label, _dt in RENEWAL_SHORTCUTS} | {"تدريب المساعد"}
	ws.shortcuts = [s for s in ws.shortcuts if s.label not in renewal_labels]

	# الروابط لازم تتجمّع تحت Card Break عشان Frappe يرسمها كروت
	by_label = {l.label: l for l in ws.links}
	rebuilt, seen = [], set()
	for card_title, labels in STORE_CARDS:
		members = [by_label[l] for l in labels if l in by_label]
		if not members:
			continue
		rebuilt.append({"type": "Card Break", "label": card_title, "link_count": len(members)})
		for l in members:
			rebuilt.append({"type": "Link", "label": l.label, "link_type": l.link_type or "DocType",
			                "link_to": l.link_to, "onboard": l.onboard, "dependencies": l.dependencies,
			                "is_query_report": l.is_query_report, "hidden": 0})
			seen.add(l.label)
	leftovers = [l for l in ws.links if l.label not in seen and l.type == "Link"]
	if leftovers:
		rebuilt.append({"type": "Card Break", "label": "روابط أخرى", "link_count": len(leftovers)})
		for l in leftovers:
			rebuilt.append({"type": "Link", "label": l.label, "link_type": l.link_type or "DocType",
			                "link_to": l.link_to, "hidden": 0})

	ws.links = []
	for row in rebuilt:
		ws.append("links", row)

	content = [_block("header", {"text": '<span class="h4"><b>متجر دبونو</b></span>', "col": 12})]
	for s in ws.shortcuts:
		content.append(_block("shortcut", {"shortcut_name": s.label, "col": 3}))
	content.append(_block("spacer", {"col": 12}))
	for card_title, _labels in STORE_CARDS:
		if any(l.type == "Card Break" and l.label == card_title for l in ws.links):
			content.append(_block("card", {"card_name": card_title, "col": 4}))
	if any(l.type == "Card Break" and l.label == "روابط أخرى" for l in ws.links):
		content.append(_block("card", {"card_name": "روابط أخرى", "col": 4}))

	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return len([l for l in ws.links if l.type == "Card Break"]), len(ws.shortcuts)


def execute():
	cards, shortcuts = rebuild_store()
	print(f"«متجر دبونو»: {cards} كارت روابط راجعة + {shortcuts} اختصار (قسم التجديد اتشال)")

	print("«تجديد الاشتراك»:", build_renewal_workspace())

	name, made = build_bord()
	print(f"«{name}»: {len(made)} مؤشر")
	for m in made:
		print("   •", m)

	frappe.db.commit()
	frappe.clear_cache()
