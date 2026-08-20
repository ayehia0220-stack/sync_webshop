# -*- coding: utf-8 -*-
"""
تجربة على مستندات حقيقية من غير ما يتبعت أي حاجة.

المهم مش إن النص يطلع — المهم إن **الرقم** يطلع صح: بن من 1212،
GPS من 97. عشان كده بنجرّب على طلبات فيها بن وطلبات فيها GPS.
"""

import frappe

from sync_webshop.api import lifecycle as lc

CASES = [
	("Customer", "تسجيل عميل", {}),
	("Sales Order", "طلب بيع", {"docstatus": 1}),
	("Payment Entry", "قيد دفع", {"docstatus": 1, "party_type": "Customer"}),
	("Sales Invoice", "فاتورة بيع", {"docstatus": 1, "is_pos": 0}),
]


def _pick(doctype, filters, limit=6):
	return frappe.get_all(doctype, filters=filters, pluck="name",
	                      order_by="creation desc", limit=limit)


def execute():
	print("الحدث           | المستند                  | الخط | رقم | النتيجة")
	print("=" * 96)
	for doctype, event, filters in CASES:
		names = _pick(doctype, filters)
		if not names:
			print("%-15s | مفيش مستندات للتجربة" % event)
			continue
		shown = 0
		for name in names:
			res = lc.deliver(doctype, name, event, force=1, dry_run=1)
			if res.get("ok"):
				print("%-15s | %-24s | %-4s | %-3s | ✓" % (
					event, name[:24], res["line"], res["instance"]))
				if shown == 0:
					print("      ┌" + "─" * 60)
					for row in (res["text"] or "").split("\n")[:14]:
						print("      │ " + row)
					print("      └" + "─" * 60)
				shown += 1
				if shown >= 2:
					break
			else:
				print("%-15s | %-24s | %-4s | %-3s | ✗ %s" % (
					event, name[:24], "—", "—", res.get("why")))

	print("\n— توزيع الخطوط على آخر 25 طلب —")
	counts = {}
	for name in _pick("Sales Order", {"docstatus": 1}, limit=25):
		res = lc.deliver("Sales Order", name, "طلب بيع", force=1, dry_run=1)
		key = "%s (%s)" % (res.get("line"), res.get("instance")) \
			if res.get("ok") else "مفيش إرسال: %s" % res.get("why")
		counts[key] = counts.get(key, 0) + 1
	for key, n in sorted(counts.items(), key=lambda x: -x[1]):
		print("  %-40s %s" % (key, n))

	print("\n— حالة التشغيل —")
	print(" ", lc.health())
