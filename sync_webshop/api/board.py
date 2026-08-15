# -*- coding: utf-8 -*-
"""
مؤشرات «المتأخر» لازم تاريخ حقيقي في الفلتر — Frappe مبيفهمش "Today" هنا،
وكان بيرجّع صفر بدل ما يقول إن الفلتر غلط.

الدالة دي بتكتب تاريخ النهاردة في الفلاتر، وبتتشغّل كل يوم من الـ scheduler.
"""
import json

import frappe

# اسم المؤشر -> (الحقل اللي فيه التاريخ)
DATE_CARDS = {
	"أوامر بيع فات ميعاد تسليمها": "delivery_date",
	"قضايا فات تاريخ متابعتها": "following_date",
}


def refresh_overdue_cards():
	today = frappe.utils.nowdate()
	touched = []
	for name, field in DATE_CARDS.items():
		if not frappe.db.exists("Number Card", name):
			continue
		card = frappe.get_doc("Number Card", name)
		filters = json.loads(card.filters_json or "[]")
		changed = False
		for row in filters:
			if len(row) >= 4 and row[1] == field and row[2] == "<" and row[3] != today:
				row[3] = today
				changed = True
		if changed:
			card.filters_json = json.dumps(filters, ensure_ascii=False)
			card.flags.ignore_permissions = True
			card.save()
			touched.append(name)
	if touched:
		frappe.db.commit()
	return touched


def execute():
	touched = refresh_overdue_cards()
	print("اتحدّثت:", ", ".join(touched) or "(كانت محدّثة)")
	for name in DATE_CARDS:
		if not frappe.db.exists("Number Card", name):
			continue
		card = frappe.get_doc("Number Card", name)
		filters = {}
		for row in json.loads(card.filters_json or "[]"):
			filters[row[1]] = row[3] if row[2] == "=" else [row[2], row[3]]
		print(f"  {name}: {frappe.db.count(card.document_type, filters)}")
