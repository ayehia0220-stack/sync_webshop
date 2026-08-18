# -*- coding: utf-8 -*-
"""
Move the phone numbers from the orders onto the customer cards.

97% of customers have no mobile number, while 2,976 sales orders carry one —
the team has been typing the phone on the order for years and the customer card
stayed blank. That is why duplicate customers were invisible: you cannot spot
two records for the same person when neither shows a number.

Only customers with an empty mobile field are touched, and the number taken is
the one on their most recent order. Nothing is overwritten, so a number somebody
typed onto the customer deliberately survives.
"""
import re

import frappe


def norm(value):
	d = re.sub(r"\D", "", str(value or ""))
	if d.startswith("0020"):
		d = d[4:]
	if d.startswith("20") and len(d) == 12:
		d = d[2:]
	if len(d) == 10 and d[0] == "1":
		d = "0" + d
	return d if re.fullmatch(r"01[0-9]{9}", d) else ""


def execute():
	rows = frappe.db.sql(
		"""
		SELECT so.customer, so.custom_customer_phone_number AS phone
		FROM `tabSales Order` so
		JOIN (
			SELECT customer, MAX(creation) AS latest
			FROM `tabSales Order`
			WHERE IFNULL(custom_customer_phone_number, '') != ''
			GROUP BY customer
		) newest ON newest.customer = so.customer AND newest.latest = so.creation
		JOIN `tabCustomer` c ON c.name = so.customer
		WHERE IFNULL(c.mobile_no, '') = ''
		""",
		as_dict=True)

	print("مرشّحين:", len(rows))

	written, unusable = 0, []
	for i, row in enumerate(rows, 1):
		phone = norm(row.phone)
		if not phone:
			unusable.append((row.customer, row.phone))
			continue
		frappe.db.set_value("Customer", row.customer, "mobile_no", phone,
		                    update_modified=False)
		written += 1
		if i % 400 == 0:
			frappe.db.commit()
			print("   ... %d/%d" % (i, len(rows)))

	frappe.db.commit()
	print("اتكتب:", written, "| أرقام مش صالحة:", len(unusable))
	for c, p in unusable[:5]:
		print("   ✗ %-26s %s" % (c[:26], p))

	# --- what the duplicate picture looks like now ---------------------------
	dups = frappe.db.sql(
		"""
		SELECT mobile_no, COUNT(*) n
		FROM `tabCustomer` WHERE IFNULL(mobile_no,'') != ''
		GROUP BY mobile_no HAVING n > 1
		""",
		as_dict=True)
	total = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(n), 0) FROM (
			SELECT COUNT(*) n FROM `tabCustomer`
			WHERE IFNULL(mobile_no,'') != '' GROUP BY mobile_no HAVING COUNT(*) > 1
		) d
		""")[0][0]

	print()
	print("عملاء عندهم رقم دلوقتي:",
	      frappe.db.count("Customer", {"mobile_no": ["!=", ""]}),
	      "من", frappe.db.count("Customer"))
	print("أرقام مكررة:", len(dups), "→ عدد العملاء المتورطين:", total)
