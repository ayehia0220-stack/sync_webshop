# -*- coding: utf-8 -*-
"""كل تقرير في مساحته: تربو مع تربو، المتجر مع المتجر، المكالمات مع المكالمات."""
import json

import frappe

PLACEMENT = {
	"تربو": ("تقارير الشحن", [
		"تربو — في انتظار الشحن",
		"تربو — شحنات على الطريق",
		"تربو — شحنات فيها مشكلة",
		"تربو — الفلوس عند الشركة",
	]),
	"متجر دبونو": ("تقارير المتجر", [
		"تحليلات المتجر — أكثر المنتجات مبيعًا",
		"تحليلات المتجر — شهريًا",
		"تقسيم العملاء",
	]),
}


def _block(btype, data):
	return {"id": f"{btype}{abs(hash(json.dumps(data, sort_keys=True))) % 10**9}",
	        "type": btype, "data": data}


def place(ws_name, card_label, reports):
	ws = frappe.get_doc("Workspace", ws_name)
	reports = [r for r in reports if frappe.db.exists("Report", r)]
	if not reports:
		return 0

	# نسيب أي كروت تانية زي ما هي ونستبدل كارت التقارير بس
	keep, skip = [], False
	for l in ws.links:
		if l.type == "Card Break":
			skip = l.label == card_label
		if not skip:
			keep.append({"type": l.type, "label": l.label, "link_type": l.link_type,
			             "link_to": l.link_to, "is_query_report": l.is_query_report,
			             "hidden": l.hidden, "link_count": l.link_count})

	ws.links = []
	for row in keep:
		ws.append("links", row)
	ws.append("links", {"type": "Card Break", "label": card_label, "link_count": len(reports)})
	for r in reports:
		ws.append("links", {"type": "Link", "label": r, "link_type": "Report",
		                    "link_to": r, "is_query_report": 1, "hidden": 0})

	content = json.loads(ws.content or "[]")
	if not any(b.get("type") == "card" and b.get("data", {}).get("card_name") == card_label
	           for b in content):
		content.append(_block("spacer", {"col": 12}))
		content.append(_block("card", {"card_name": card_label, "col": 4}))
	ws.content = json.dumps(content, ensure_ascii=False)
	ws.flags.ignore_permissions = True
	ws.save()
	return len(reports)


def execute():
	for ws_name, (card, reports) in PLACEMENT.items():
		if not frappe.db.exists("Workspace", ws_name):
			print(f"  ✗ مفيش مساحة {ws_name}")
			continue
		n = place(ws_name, card, reports)
		print(f"  ✓ {ws_name}: {n} تقرير تحت «{card}»")
	frappe.db.commit()
	frappe.clear_cache()

	print("\n=== كل مساحة وتقاريرها ===")
	for w in ["متجر دبونو", "تربو", "المكالمات", "تجديد الاشتراكات", "Board"]:
		if not frappe.db.exists("Workspace", w):
			continue
		ws = frappe.get_doc("Workspace", w)
		reps = [l.label for l in ws.links if l.type == "Link" and l.is_query_report]
		print(f"  {w}: {len(reps)} تقرير")
		for r in reps:
			print(f"     • {r}")
