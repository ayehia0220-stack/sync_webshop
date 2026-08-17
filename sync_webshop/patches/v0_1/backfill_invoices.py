# -*- coding: utf-8 -*-
"""
Fill the phone and address on invoices that already exist.

The hook only runs when an invoice is saved, so it covered the four raised since
it went in and left 3,580 older ones blank — and those are the ones people
reprint. Reprinting is the whole point of the change, so they have to be filled.

Written with db_set rather than save(): these are submitted accounting
documents, and re-saving them would touch modified timestamps, fire other
hooks, and rewrite ledger-adjacent fields. Two display fields do not justify
that. db_set writes the column and nothing else.
"""
import frappe

BATCH = 200


def execute(limit=None):
	from sync_webshop.api.turbo import (
		_preferred_address, format_address, _address_from_last_order,
		_looks_like_address,
	)

	rows = frappe.db.sql(
		"""
		SELECT name, customer
		FROM `tabSales Invoice`
		WHERE docstatus < 2
		  AND IFNULL(custom_customer_phone_number, '') = ''
		  AND IFNULL(custom_address_for_customer_, '') = ''
		ORDER BY creation DESC
		""",
		as_dict=True)
	if limit:
		rows = rows[: int(limit)]

	print("فواتير محتاجة تعبئة:", len(rows))

	# One lookup per customer instead of one per invoice — a customer with
	# forty invoices was otherwise forty identical queries.
	cache = {}
	filled_phone = filled_addr = 0

	for i, row in enumerate(rows, 1):
		cust = row.customer
		if not cust:
			continue

		if cust not in cache:
			addr = format_address(_preferred_address(cust)) or _address_from_last_order(cust)
			phone = (frappe.db.get_value("Customer", cust, "mobile_no") or "").strip()
			if not phone:
				got = frappe.db.sql(
					"""
					SELECT custom_customer_phone_number AS p FROM `tabSales Order`
					WHERE customer = %s AND IFNULL(custom_customer_phone_number,'') != ''
					ORDER BY creation DESC LIMIT 1
					""",
					cust, as_dict=True)
				phone = (got[0].p or "").strip() if got else ""
			cache[cust] = (phone, addr if _looks_like_address(addr) else "")

		phone, addr = cache[cust]

		# An invoice raised from a specific order should carry that order's
		# details, not the customer's latest.
		order = frappe.db.get_value(
			"Sales Invoice Item", {"parent": row.name, "sales_order": ["!=", ""]},
			"sales_order")
		if order:
			o = frappe.db.get_value(
				"Sales Order", order,
				["custom_customer_phone_number", "custom_address_for_customer_"],
				as_dict=True) or {}
			phone = (o.get("custom_customer_phone_number") or "").strip() or phone
			cand = (o.get("custom_address_for_customer_") or "").strip()
			if _looks_like_address(cand):
				addr = cand

		if phone:
			frappe.db.set_value("Sales Invoice", row.name,
			                    "custom_customer_phone_number", phone[:60],
			                    update_modified=False)
			filled_phone += 1
		if addr:
			frappe.db.set_value("Sales Invoice", row.name,
			                    "custom_address_for_customer_", addr[:200],
			                    update_modified=False)
			filled_addr += 1

		if i % BATCH == 0:
			frappe.db.commit()
			print("   ... %d/%d" % (i, len(rows)))

	frappe.db.commit()
	print()
	print("اتملّى تليفون: %d | اتملّى عنوان: %d | من إجمالي %d"
	      % (filled_phone, filled_addr, len(rows)))
