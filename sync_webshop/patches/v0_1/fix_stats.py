# -*- coding: utf-8 -*-
"""
Count only what the shop actually sells.

The ERP carries more than the coffee business, and every sales order sits under
the same company, so a plain count would put another line of business's orders
on the coffee shop's home page. Scoping to orders that contain a website product
is the honest figure — and the flavour count now uses the same price list the
storefront sells from, so it matches what a visitor can actually browse.
"""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/analytics.py"

NEW = '''def _compute_stats():
	"""Read the real figures out of the submitted sales orders."""
	settings = frappe.get_single("Webshop API Settings")
	price_list = settings.default_price_list

	# Only orders that contain something the storefront sells. The ERP also
	# carries other lines of business under the same company.
	shop_orders = """
		SELECT DISTINCT so.name, so.customer, so.shipping_address_name
		FROM `tabSales Order` so
		JOIN `tabSales Order Item` soi ON soi.parent = so.name
		JOIN `tabItem` i ON i.name = soi.item_code
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE so.docstatus = 1
	"""

	orders = _int(frappe.db.sql(
		"SELECT COUNT(*) FROM (%s) o" % shop_orders)[0][0])

	# A customer who came back is the strongest signal a shop can show, so it
	# is counted properly rather than approximated from the order total.
	repeat = _int(frappe.db.sql(
		"SELECT COUNT(*) FROM ("
		"  SELECT customer FROM (%s) o WHERE IFNULL(customer,'') != ''"
		"  GROUP BY customer HAVING COUNT(*) > 1"
		") r" % shop_orders)[0][0])

	customers = _int(frappe.db.sql(
		"SELECT COUNT(DISTINCT customer) FROM (%s) o" % shop_orders)[0][0])

	# Packs that actually left the roastery.
	packs = _int(frappe.db.sql("""
		SELECT COALESCE(SUM(soi.qty), 0)
		FROM `tabSales Order Item` soi
		JOIN `tabSales Order` so ON so.name = soi.parent
		JOIN `tabItem` i ON i.name = soi.item_code
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE so.docstatus = 1
	""")[0][0])

	# Where the coffee has travelled — a delivery reach, not a marketing claim.
	cities = _int(frappe.db.sql(
		"SELECT COUNT(DISTINCT TRIM(a.city)) FROM (%s) o "
		"JOIN `tabAddress` a ON a.name = o.shipping_address_name "
		"WHERE IFNULL(a.city,'') != ''" % shop_orders)[0][0])

	# What a visitor can actually browse and buy today.
	flavours = _int(frappe.db.sql("""
		SELECT COUNT(DISTINCT i.name)
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.price_list = %s AND p.selling = 1
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE i.disabled = 0
	""", price_list)[0][0])

	articles = _int(frappe.db.count("Webshop Post", {"published": 1})) \\
		if frappe.db.exists("DocType", "Webshop Post") else 0

	return {
		"orders": orders, "repeat": repeat, "customers": customers,
		"packs": packs, "cities": cities, "flavours": flavours, "articles": articles,
	}
'''


def execute():
	import frappe

	s = io.open(P, encoding="utf-8").read()
	start = s.index("def _compute_stats():")
	end = s.index("@frappe.whitelist(allow_guest=True)\ndef get_store_stats", start)
	io.open(P, "w", encoding="utf-8").write(s[:start] + NEW + "\n\n" + s[end:])
	frappe.cache().delete_value("webshop_store_stats")
	frappe.db.commit()
	print("stats scoped to shop products")
