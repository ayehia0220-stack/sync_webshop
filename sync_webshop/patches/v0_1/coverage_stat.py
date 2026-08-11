# -*- coding: utf-8 -*-
"""
Count delivery coverage from the shipping zones, not from old order addresses.

The legacy ERP orders carry no shipping address, so the tile computed zero and
was hidden. The zones are the shop's actual statement of where it delivers, and
they stay current as the owner edits them.
"""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/analytics.py"

OLD = '''	# Where the coffee has travelled — a delivery reach, not a marketing claim.
	cities = _int(frappe.db.sql(
		"SELECT COUNT(DISTINCT TRIM(a.city)) FROM (%s) o "
		"JOIN `tabAddress` a ON a.name = o.shipping_address_name "
		"WHERE IFNULL(a.city,'') != ''" % shop_orders)[0][0])'''

NEW = '''	# Where the shop delivers, read from the shipping zones. Old ERP orders have
	# no shipping address attached, so counting those gave zero.
	from sync_webshop.patches.v0_1.coverage_page import count_governorates
	cities = len(count_governorates())'''


def execute():
	import frappe

	s = io.open(P, encoding="utf-8").read()
	if "count_governorates" in s:
		print("already patched")
	else:
		if OLD not in s:
			frappe.throw("cities block moved")
		io.open(P, "w", encoding="utf-8").write(s.replace(OLD, NEW, 1))
		print("analytics.py patched")

	# Let the owner state a different number than the zones imply.
	old = '''	orders = max(raw["orders"], _int(settings.get("stats_min_orders")))'''
	new = old + '''
	cities = _int(settings.get("stats_cities_override")) or raw["cities"]'''
	s = io.open(P, encoding="utf-8").read()
	if "stats_cities_override" not in s:
		if old not in s:
			frappe.throw("orders floor line moved")
		s = s.replace(old, new, 1)
		s = s.replace('"value": raw["cities"]', '"value": cities', 1)
		io.open(P, "w", encoding="utf-8").write(s)
		print("override wired")

	frappe.cache().delete_value("webshop_store_stats")
	frappe.db.commit()
	frappe.clear_cache()
	print("COVERAGE STAT READY")
