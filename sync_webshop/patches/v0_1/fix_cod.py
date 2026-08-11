# -*- coding: utf-8 -*-
"""
Tell Turbo what is still owed, not what the order was worth.

A customer who paid in advance was still going to be charged again at the door:
the amount sent to Turbo was grand_total, and the only "already paid" check
looked at webshop_payment_status — a field that is empty on every order the team
types into the ERP by hand.

Order SAL-ORD-2026-00871 (أحمد طارق) is the case in point: 1,040 EGP grand
total, 1,040 EGP already received, and the courier would have been asked to
collect 1,040 EGP a second time.

What Turbo is told now is the outstanding balance — the order total, minus
whatever has been received against it, floored at zero. Shipping stays inside
that figure because it is part of grand_total, so the courier collects the
goods and the delivery in one number.
"""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"

HELPER = u'''

def amount_still_owed(order):
	"""
	What the courier should collect at the door.

	Counts money received three ways, because the shop uses all three: an
	advance recorded on the order, payments allocated to it, and payments
	against an invoice raised from it. Anything already in hand must not be
	asked for twice.
	"""
	total = float(order.grand_total or 0)

	# 1. Marked paid by the storefront (card, wallet).
	if str(order.get("webshop_payment_status") or "").strip().lower() in ("paid", "\\u0645\\u062f\\u0641\\u0648\\u0639"):
		return 0.0

	# 2. ERPNext keeps advances against the order here.
	received = float(order.get("advance_paid") or 0)

	# 3. Payments settled against invoices raised from this order.
	invoiced = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(si.grand_total - si.outstanding_amount), 0)
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND sii.sales_order = %s
		""",
		order.name,
	)[0][0]

	owed = total - received - float(invoiced or 0)
	# Never negative, and never a stray fraction of a piastre.
	return round(max(owed, 0.0), 2)
'''


def execute():
	import frappe

	s = io.open(P, encoding="utf-8").read()

	old = '''		"amount_to_be_collected": (
			0 if str(order.get("webshop_payment_status") or "").strip().lower()
			     in ("paid", "مدفوع")
			else float(order.grand_total or 0)),'''
	new = '''		# The balance, not the order value — see amount_still_owed.
		"amount_to_be_collected": amount_still_owed(order),'''

	if "amount_still_owed" not in s:
		if old not in s:
			frappe.throw("amount_to_be_collected block not found")
		s = s.replace(old, new, 1) + HELPER
		io.open(P, "w", encoding="utf-8").write(s)
		print("turbo.py: collects the balance")

	frappe.db.commit()
	frappe.clear_cache()

	# --- prove it on the order that exposed the bug --------------------------
	from sync_webshop.api.turbo import amount_still_owed
	for name in ("SAL-ORD-2026-00871", "SAL-ORD-2026-00887"):
		if not frappe.db.exists("Sales Order", name):
			continue
		o = frappe.get_doc("Sales Order", name)
		print("  %s  total=%.2f  advance=%.2f  -> Turbo collects %.2f" % (
			name, o.grand_total or 0, o.advance_paid or 0, amount_still_owed(o)))
