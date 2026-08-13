# -*- coding: utf-8 -*-
"""
تجديد الاشتراكات — its own workspace, with cards that actually count something.

All eight renewal cards carried an empty filter, so every one of them returned
the same figure: the total number of subscriptions. Eight tiles reading 1363,
labelled as if they meant eight different things. One of them ("عدد العملاء")
had no document type at all and could not have rendered.

Each card now carries the filter its label promises. Customer counts use a
report on distinct customers, because a Number Card counts rows — and one
customer can hold several subscriptions, so counting rows would have overstated
every customer figure.
"""
import frappe

CS = "Customer Subscription"

# label → filters. Renewed and refused are the two flags on the record.
SERIAL_CARDS = [
	("عدد السيريالات", {}),
	("عدد السيريال تم التجديد", {"renewed": 1}),
	("عدد السيريال رفض التجديد", {"customer_refused_to_renew": 1}),
	("عدد السيريال لم تجدد", {"renewed": 0, "customer_refused_to_renew": 0}),
]

CUSTOMER_REPORT = "تجديد الاشتراكات — العملاء"

CUSTOMER_SQL = """
SELECT
    'إجمالي العملاء'  AS "الحالة::200",
    COUNT(DISTINCT customer) AS "عدد العملاء:Int:130"
FROM `tabCustomer Subscription` WHERE IFNULL(customer,'') != ''
UNION ALL
SELECT 'تم التجديد', COUNT(DISTINCT customer)
FROM `tabCustomer Subscription` WHERE renewed = 1
UNION ALL
SELECT 'رفض التجديد', COUNT(DISTINCT customer)
FROM `tabCustomer Subscription` WHERE customer_refused_to_renew = 1
UNION ALL
SELECT 'لم يجدد بعد', COUNT(DISTINCT customer)
FROM `tabCustomer Subscription`
WHERE renewed = 0 AND customer_refused_to_renew = 0
"""

CONFLICT_REPORT = "تجديد الاشتراكات — تعارض في الحالة"

CONFLICT_SQL = """
SELECT
    cs.name           AS "الاشتراك:Link/Customer Subscription:180",
    cs.customer_name  AS "العميل::220",
    cs.imei           AS "IMEI::160",
    cs.renewed_date   AS "تاريخ التجديد:Date:110",
    cs.end_date       AS "تاريخ الانتهاء:Date:110"
FROM `tabCustomer Subscription` cs
WHERE cs.renewed = 1 AND cs.customer_refused_to_renew = 1
ORDER BY cs.renewed_date DESC
"""


def fix_card(label, filters):
	if not frappe.db.exists("Number Card", label):
		print("  missing card:", label)
		return False
	doc = frappe.get_doc("Number Card", label)
	doc.document_type = CS
	doc.function = "Count"
	doc.filters_json = frappe.as_json(filters)
	doc.is_public = 1
	doc.show_percentage_stats = 0
	doc.flags.ignore_permissions = True
	doc.save()
	return True


def make_report(name, sql):
	doc = frappe.get_doc("Report", name) if frappe.db.exists("Report", name) \
		else frappe.new_doc("Report")
	if doc.is_new():
		doc.report_name = name
		doc.ref_doctype = CS
		doc.report_type = "Query Report"
		doc.module = "Merciful"
		doc.is_standard = "No"
		doc.append("roles", {"role": "System Manager"})
		doc.append("roles", {"role": "Sales Manager"})
	doc.query = sql
	doc.disabled = 0
	doc.flags.ignore_permissions = True
	doc.save()


def execute():
	for label, filters in SERIAL_CARDS:
		if fix_card(label, filters):
			print("  fixed:", label, filters or "(الكل)")

	make_report(CUSTOMER_REPORT, CUSTOMER_SQL)
	make_report(CONFLICT_REPORT, CONFLICT_SQL)
	print("  reports ready")

	# --- the workspace -------------------------------------------------------
	name = "تجديد الاشتراكات"
	ws = frappe.get_doc("Workspace", name) if frappe.db.exists("Workspace", name) \
		else frappe.new_doc("Workspace")
	if ws.is_new():
		ws.name = name
	ws.title = name
	ws.label = name
	ws.module = "Merciful"
	ws.icon = "retweet"
	ws.public = 1
	ws.is_hidden = 0
	ws.sequence_id = 90

	ws.set("number_cards", [])
	for label, _f in SERIAL_CARDS:
		if frappe.db.exists("Number Card", label):
			ws.append("number_cards", {"number_card_name": label, "label": label})

	ws.set("shortcuts", [])
	for label, link_to, kind in [
		("العملاء بالأرقام", CUSTOMER_REPORT, "Report"),
		("تعارض في الحالة", CONFLICT_REPORT, "Report"),
		("كل الاشتراكات", CS, "DocType"),
	]:
		ws.append("shortcuts", {"label": label, "link_to": link_to, "type": kind})

	ws.content = frappe.as_json([
		{"id": "h1", "type": "header",
		 "data": {"text": "<span class='h4'>تجديد الاشتراكات</span>", "col": 12}},
		{"id": "n1", "type": "number_card", "data": {"number_card_name": SERIAL_CARDS[0][0], "col": 3}},
		{"id": "n2", "type": "number_card", "data": {"number_card_name": SERIAL_CARDS[1][0], "col": 3}},
		{"id": "n3", "type": "number_card", "data": {"number_card_name": SERIAL_CARDS[2][0], "col": 3}},
		{"id": "n4", "type": "number_card", "data": {"number_card_name": SERIAL_CARDS[3][0], "col": 3}},
		{"id": "s1", "type": "card", "data": {"card_name": "الشاشات", "col": 4}},
	])
	ws.flags.ignore_permissions = True
	ws.flags.ignore_mandatory = True
	ws.save()
	print("  workspace saved:", name)

	# --- take the renewal cards out of Board ---------------------------------
	MOVED = [c[0] for c in SERIAL_CARDS] + [
		"عدد العملاء", "عدد العملاء تم التجديد",
		"عدد العملاء لم تجدد", "عدد العملاء رفضت التجديد"]
	if frappe.db.exists("Workspace", "Board"):
		board = frappe.get_doc("Workspace", "Board")
		before = len(board.number_cards)
		board.set("number_cards", [
			r for r in board.number_cards if r.number_card_name not in MOVED])
		# Cards also live in the layout JSON; leaving them there renders a gap.
		import json
		try:
			content = json.loads(board.content or "[]")
			content = [b for b in content
			           if not (b.get("type") == "number_card"
			                   and (b.get("data") or {}).get("number_card_name") in MOVED)]
			board.content = json.dumps(content)
		except Exception:
			pass
		board.flags.ignore_permissions = True
		board.flags.ignore_mandatory = True
		board.save()
		print("  Board: %d → %d cards" % (before, len(board.number_cards)))

	# The four customer cards were duplicates that could never work as counts.
	for label in ("عدد العملاء", "عدد العملاء تم التجديد",
	              "عدد العملاء لم تجدد", "عدد العملاء رفضت التجديد"):
		if frappe.db.exists("Number Card", label):
			frappe.db.set_value("Number Card", label, "is_public", 0)

	frappe.db.commit()
	frappe.clear_cache()
	print("RENEWAL WORKSPACE READY")
