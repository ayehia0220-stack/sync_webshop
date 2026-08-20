# -*- coding: utf-8 -*-
"""نتأكد إن كل رقم وكل تقرير بيجيب حاجة حقيقية مش نفس العدد لكل حاجة."""

import json

import frappe
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.desk.query_report import run

CARDS = ["الأتمتة — الإجمالي", "الأتمتة — شغالة", "الأتمتة — ميتة",
         "الأتمتة — فيها أخطاء", "الأتمتة — مقفولة",
         "الأتمتة — في n8n", "الأتمتة — جوّه ERPNext"]

REPORTS = ["الأتمتة — كل الورك فلو", "الأتمتة — محتاجة قرار"]


def execute():
	print("— الأرقام —")
	seen = []
	for name in CARDS:
		doc = frappe.get_doc("Number Card", name)
		try:
			val = get_result(doc, json.loads(doc.filters_json or "[]"))
		except Exception as exc:
			val = "✗ %s" % str(exc)[:60]
		seen.append(val)
		print("  %-26s = %s" % (name, val))

	nums = [v for v in seen if isinstance(v, (int, float))]
	if len(set(nums)) <= 1 and len(nums) > 2:
		print("  ⚠️ كل الأرقام متساوية — الفلاتر مش شغالة")
	else:
		print("  ✓ الأرقام مختلفة، الفلاتر شغالة")

	print("\n— التقارير —")
	for name in REPORTS:
		try:
			res = run(name, filters=None, ignore_prepared_report=True)
			cols = len(res.get("columns") or [])
			rows = len(res.get("result") or [])
			print("  ✓ %-26s %s عمود / %s سطر" % (name, cols, rows))
			for row in (res.get("result") or [])[:4]:
				vals = list(row.values()) if isinstance(row, dict) else list(row)
				print("      " + " | ".join(str(v)[:22] for v in vals[:5]))
		except Exception as exc:
			print("  ✗ %-26s %s" % (name, str(exc)[:120]))

	print("\n— الورك سبيس —")
	ws = frappe.get_doc("Workspace", "الأتمتة")
	print("  روابط: %s | أرقام: %s | محتوى: %s بلوك"
	      % (len(ws.links), len(ws.number_cards),
	         len(json.loads(ws.content or "[]"))))
	missing = [c.number_card_name for c in ws.number_cards
	           if not frappe.db.exists("Number Card", c.number_card_name)]
	broken = [l.link_to for l in ws.links if l.type == "Link"
	          and not frappe.db.exists(l.link_type, l.link_to)]
	print("  %s أرقام ناقصة | %s روابط مكسورة"
	      % (len(missing) or "لا", len(broken) or "لا"))
	if missing:
		print("   ", missing)
	if broken:
		print("   ", broken)
