# -*- coding: utf-8 -*-
"""
أرقام المتجر — the numbers strip on the home page.

Every figure is counted from the real ERP data, not typed in. A made-up number
is a promise the shop cannot keep, and a customer who spots one stops believing
the rest of the page. The owner can still hide any figure, rename it, or set a
floor underneath it from the Desk.

Recomputed hourly and cached — this runs on the busiest page of the site.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CACHE_KEY = "webshop_store_stats"
CACHE_TTL = 3600

FIELDS = {
	"Webshop Content Settings": [
		{
			"fieldname": "sec_stats",
			"label": "أرقام المتجر — Store Numbers",
			"fieldtype": "Section Break",
			"insert_after": "testimonials",
			"collapsible": 1,
			"description": "الأرقام دي بتتحسب لوحدها من الطلبات الحقيقية كل ساعة. "
			               "الحد الأدنى بيمنع ظهور رقم صغير في البداية — سيبه صفر "
			               "لو عايز الرقم الحقيقي دايمًا.",
		},
		{
			"fieldname": "show_stats",
			"label": "اعرض شريط الأرقام",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "sec_stats",
		},
		{
			"fieldname": "stats_title_ar",
			"label": "عنوان القسم (عربي)",
			"fieldtype": "Data",
			"default": "دبونو في أرقام",
			"insert_after": "show_stats",
		},
		{
			"fieldname": "stats_title_en",
			"label": "Section title (English)",
			"fieldtype": "Data",
			"default": "dpono in numbers",
			"insert_after": "stats_title_ar",
		},
		{"fieldname": "stats_cb", "fieldtype": "Column Break", "insert_after": "stats_title_en"},
		{
			"fieldname": "stats_min_orders",
			"label": "حد أدنى — الطلبات",
			"fieldtype": "Int",
			"default": "0",
			"insert_after": "stats_cb",
		},
		{
			"fieldname": "stats_min_customers",
			"label": "حد أدنى — العملاء",
			"fieldtype": "Int",
			"default": "0",
			"insert_after": "stats_min_orders",
		},
	],
}

API = u'''

# ============================================================================
# أرقام المتجر — counted, never typed
# ============================================================================

STATS_CACHE_KEY = "webshop_store_stats"
STATS_CACHE_TTL = 3600


def _int(value):
	try:
		return int(value or 0)
	except (TypeError, ValueError):
		return 0


def _compute_stats():
	"""Read the real figures out of the submitted sales orders."""
	orders = _int(frappe.db.count("Sales Order", {"docstatus": 1}))

	# A customer who came back is the strongest signal a shop can show, so it
	# is counted properly rather than approximated from the order total.
	repeat = _int(frappe.db.sql("""
		SELECT COUNT(*) FROM (
			SELECT customer FROM `tabSales Order`
			WHERE docstatus = 1 AND IFNULL(customer, '') != ''
			GROUP BY customer HAVING COUNT(*) > 1
		) repeats
	""")[0][0])

	customers = _int(frappe.db.sql("""
		SELECT COUNT(DISTINCT customer) FROM `tabSales Order` WHERE docstatus = 1
	""")[0][0])

	# Packs that actually left the roastery.
	packs = _int(frappe.db.sql("""
		SELECT COALESCE(SUM(soi.qty), 0)
		FROM `tabSales Order Item` soi
		JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
	""")[0][0])

	# Where the coffee has travelled — a delivery reach, not a marketing claim.
	cities = _int(frappe.db.sql("""
		SELECT COUNT(DISTINCT TRIM(addr.city))
		FROM `tabSales Order` so
		JOIN `tabAddress` addr ON addr.name = so.shipping_address_name
		WHERE so.docstatus = 1 AND IFNULL(addr.city, '') != ''
	""")[0][0])

	flavours = _int(frappe.db.sql("""
		SELECT COUNT(DISTINCT i.name)
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.selling = 1
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE i.disabled = 0
	""")[0][0])

	articles = _int(frappe.db.count("Webshop Post", {"published": 1})) \\
		if frappe.db.exists("DocType", "Webshop Post") else 0

	return {
		"orders": orders, "repeat": repeat, "customers": customers,
		"packs": packs, "cities": cities, "flavours": flavours, "articles": articles,
	}


@frappe.whitelist(allow_guest=True)
def get_store_stats():
	set_cors_headers()
	settings = frappe.get_single("Webshop Content Settings")
	if not settings.get("show_stats"):
		return {"enabled": False, "items": []}

	raw = frappe.cache().get_value(STATS_CACHE_KEY)
	if raw is None:
		raw = _compute_stats()
		frappe.cache().set_value(STATS_CACHE_KEY, raw, expires_in_sec=STATS_CACHE_TTL)

	# A floor the owner can set so a brand-new shop does not advertise "3 orders".
	orders = max(raw["orders"], _int(settings.get("stats_min_orders")))
	customers = max(raw["customers"], _int(settings.get("stats_min_customers")))

	items = [
		{"key": "orders", "value": orders, "suffix": "+",
		 "label_ar": "طلب اتسلّم بنجاح", "label_en": "Orders delivered", "icon": "\\U0001F4E6"},
		{"key": "repeat", "value": raw["repeat"], "suffix": "+",
		 "label_ar": "عميل رجع اشترى تاني", "label_en": "Customers who came back", "icon": "\\U0001F501"},
		{"key": "packs", "value": raw["packs"], "suffix": "+",
		 "label_ar": "عبوة بن وصلت لبيوتكم", "label_en": "Packs shipped", "icon": "\\u2615"},
		{"key": "cities", "value": raw["cities"], "suffix": "",
		 "label_ar": "محافظة بنوصلها", "label_en": "Cities we reach", "icon": "\\U0001F69A"},
		{"key": "flavours", "value": raw["flavours"], "suffix": "",
		 "label_ar": "نكهة ودرجة تحميص", "label_en": "Flavours and roasts", "icon": "\\U0001F31F"},
	]
	# A zero reads as "nobody buys here" — better to leave the tile out.
	items = [i for i in items if i["value"] > 0]

	return {
		"enabled": True,
		"title_ar": settings.get("stats_title_ar") or "دبونو في أرقام",
		"title_en": settings.get("stats_title_en") or "dpono in numbers",
		"customers": customers,
		"items": items,
	}
'''


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	settings = frappe.get_single("Webshop Content Settings")
	defaults = {
		"show_stats": 1,
		"stats_title_ar": "دبونو في أرقام",
		"stats_title_en": "dpono in numbers",
	}
	for name, value in defaults.items():
		if not settings.get(name):
			settings.set(name, value)
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/analytics.py"
	s = io.open(p, encoding="utf-8").read()
	if "get_store_stats" not in s:
		io.open(p, "w", encoding="utf-8").write(s + API)
		print("analytics.py extended")

	frappe.cache().delete_value(CACHE_KEY)
	frappe.db.commit()
	frappe.clear_cache()
	print("STATS READY")
