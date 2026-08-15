# -*- coding: utf-8 -*-
"""
ينضّف مساحة Board الموجودة ويدمج شغلي فيها بدل المساحات المكررة.

المالك عايز Board لوحة تقصير: اللي متأخر أو منسي بس. المبيعات والمرتبات
والرسوم البيانية بتتشال لأنها أرقام للفرجة مش حاجة محتاجة تدخّل.
"""
import json

import frappe

BOARD = "Board"
RENEWAL = "تجديد الاشتراكات"          # الموجودة أصلًا (module Merciful)
MY_BORD = "bord"                       # اللي عملتها بالغلط
MY_RENEWAL = "تجديد الاشتراك"          # اللي عملتها بالغلط

# مؤشرات تُشال من Board — مبيعات/مرتبات/عملاء محتملين، مش تقصير
DROP_CARDS = {
	"اجمالي مبيعات الشهر بالكيلو (مدفوع)",
	"اجمالي مبيعات الشهر بالكيلو (غير مدفوع)",
	"اجمالي المرتبات (الشهر السابق)",
	"العميل المحتمل جديد (الشهر السابق)",
}

MY_CARDS = [
	"فواتير مستحقة لم تُحصّل",
	"مبلغ مستحق على العملاء",
	"أوامر بيع فات ميعاد تسليمها",
	"إذون تسليم لم تُفوتر",
	"قضايا فات تاريخ متابعتها",
	"إيصالات لم تُسلَّم للمحامي",
	"عملاء طالبين مكالمة",
	"مهام مفتوحة على الفريق",
	"زيارات مناديب فاشلة",
]

MY_SHORTCUTS = [
	("القضايا", "Legal Case"),
	("زيارات المناديب", "Sales Visit"),
	("المهام والتذاكر", "ToDo"),
	("الاشتراكات", "Customer Subscription"),
	("إذون التسليم", "Delivery Note"),
]

RENEWAL_SHORTCUTS = [
	("إعدادات حملة التجديد", "Renewal Campaign Settings"),
	("قوالب رسائل التجديد", "Renewal Message Template"),
	("الاشتراكات", "Customer Subscription"),
	("سجل محادثات التجديد", "Renewal Conversation Log"),
	("تذاكر المتابعة", "ToDo"),
	("تدريب المساعد", "Webshop Agent Training"),
]


def _block(btype, data):
	return {"id": f"{btype}{abs(hash(json.dumps(data, sort_keys=True))) % 10**9}",
	        "type": btype, "data": data}


def clean_board():
	ws = frappe.get_doc("Workspace", BOARD)

	kept = [c for c in ws.number_cards if c.label not in DROP_CARDS]
	dropped = [c.label for c in ws.number_cards if c.label in DROP_CARDS]
	have = {c.label for c in kept}

	ws.number_cards = []
	for c in kept:
		ws.append("number_cards", {"number_card_name": c.number_card_name, "label": c.label})
	for label in MY_CARDS:
		if label in have or not frappe.db.exists("Number Card", label):
			continue
		ws.append("number_cards", {"number_card_name": label, "label": label})

	charts_removed = [c.label for c in ws.charts]
	ws.charts = []          # الرسوم كلها مبيعات/مرتبات — مش تقصير

	have_sc = {s.label for s in ws.shortcuts}
	for label, dt in MY_SHORTCUTS:
		if label in have_sc or not frappe.db.exists("DocType", dt):
			continue
		ws.append("shortcuts", {"type": "DocType", "link_to": dt, "label": label})

	content = [_block("header", {"text": '<span class="h4"><b>محتاج تدخّل دلوقتي</b></span>', "col": 12})]
	for c in ws.number_cards:
		content.append(_block("number_card", {"number_card_name": c.number_card_name, "col": 4}))
	content.append(_block("spacer", {"col": 12}))
	content.append(_block("header", {"text": '<span class="h4"><b>افتح بسرعة</b></span>', "col": 12}))
	for s in ws.shortcuts:
		content.append(_block("shortcut", {"shortcut_name": s.label, "col": 3}))

	ws.content = json.dumps(content, ensure_ascii=False)
	ws.sequence_id = 0
	ws.flags.ignore_permissions = True
	ws.save()
	return dropped, charts_removed, len(ws.number_cards), len(ws.shortcuts)


def merge_renewal():
	ws = frappe.get_doc("Workspace", RENEWAL)
	have = {s.label for s in ws.shortcuts}
	for label, dt in RENEWAL_SHORTCUTS:
		if label in have or not frappe.db.exists("DocType", dt):
			continue
		ws.append("shortcuts", {"type": "DocType", "link_to": dt, "label": label})

	content = [_block("header", {"text": '<span class="h4"><b>أرقام الاشتراكات</b></span>', "col": 12})]
	for c in ws.number_cards:
		content.append(_block("number_card", {"number_card_name": c.number_card_name, "col": 3}))
	content.append(_block("spacer", {"col": 12}))
	content.append(_block("header", {"text": '<span class="h4"><b>إدارة الحملة</b></span>', "col": 12}))
	for s in ws.shortcuts:
		content.append(_block("shortcut", {"shortcut_name": s.label, "col": 3}))

	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return len(ws.number_cards), len(ws.shortcuts)


def drop_duplicates():
	gone = []
	for name in (MY_BORD, MY_RENEWAL):
		if frappe.db.exists("Workspace", name):
			frappe.delete_doc("Workspace", name, force=1, ignore_permissions=True)
			gone.append(name)
	return gone


def execute():
	dropped, charts, cards, shortcuts = clean_board()
	print("«Board» — اتنضفت:")
	print("  اتشال من المؤشرات:", ", ".join(dropped) or "(مفيش)")
	print("  اتشال من الرسوم :", ", ".join(charts) or "(مفيش)")
	print(f"  بقت: {cards} مؤشر + {shortcuts} اختصار")

	n, s = merge_renewal()
	print(f"\n«تجديد الاشتراكات» — {n} مؤشر + {s} اختصار")

	print("\nاتمسحت المساحات المكررة:", ", ".join(drop_duplicates()) or "(مفيش)")
	frappe.db.commit()
	frappe.clear_cache()
