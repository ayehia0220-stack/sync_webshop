# -*- coding: utf-8 -*-
import frappe

from sync_webshop.api.utils import set_cors_headers


@frappe.whitelist(allow_guest=True)
def get_analytics_settings():
	"""
	Which tracking tools the storefront should load. Only ids that are actually
	filled in come back, so an empty configuration means no scripts at all.
	"""
	set_cors_headers()

	try:
		seo = frappe.get_single("Webshop SEO Settings")
	except Exception:
		return {"enabled": False, "providers": {}, "require_consent": True}

	if not seo.get("enable_analytics"):
		return {"enabled": False, "providers": {}, "require_consent": True}

	providers = {}
	for key, field in (
		("gtm", "google_tag_manager_id"),
		("ga4", "ga4_measurement_id"),
		("meta", "meta_pixel_id"),
		("tiktok", "tiktok_pixel_id"),
		("clarity", "clarity_project_id"),
	):
		value = (seo.get(field) or "").strip()
		if value:
			providers[key] = value

	return {
		"enabled": bool(providers),
		"providers": providers,
		"require_consent": bool(seo.get("require_cookie_consent")),
	}


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


def _finished_goods_groups():
	"""Every item group under the finished-goods tree — the coffee we make."""
	root = frappe.db.get_value("Item Group", "منتج تام", ["lft", "rgt"], as_dict=True)
	if not root:
		return frappe.get_all("Item Group", filters={"show_in_website": 1}, pluck="name")
	return frappe.get_all(
		"Item Group",
		filters={"lft": [">=", root.lft], "rgt": ["<=", root.rgt]},
		pluck="name",
	)


def _sql_tuple(values):
	"""An escaped IN (...) list. Values come from the item tree, never from a request."""
	if not values:
		return "('__none__')"
	return "(%s)" % ", ".join(frappe.db.escape(v) for v in values)


def _compute_stats():
	"""Read the real figures out of the submitted sales orders."""
	settings = frappe.get_single("Webshop API Settings")
	price_list = settings.default_price_list

	# Only orders for the coffee side of the business — the ERP also carries the
	# GPS line under the same company.
	#
	# Scoped to the finished-goods tree, NOT to "show_in_website". Those figures
	# describe what the roastery has actually done over the years; narrowing the
	# shop window to one item group must not erase the history behind it.
	coffee_tree = _finished_goods_groups()

	shop_orders = """
		SELECT DISTINCT so.name, so.customer, so.shipping_address_name
		FROM `tabSales Order` so
		JOIN `tabSales Order Item` soi ON soi.parent = so.name
		JOIN `tabItem` i ON i.name = soi.item_code
		WHERE so.docstatus = 1 AND i.item_group IN %(groups)s
	""" % {"groups": _sql_tuple(coffee_tree)}

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
		WHERE so.docstatus = 1 AND i.item_group IN %(groups)s
	""" % {"groups": _sql_tuple(coffee_tree)})[0][0])

	# Where the shop delivers, read from the shipping zones. Old ERP orders have
	# no shipping address attached, so counting those gave zero.
	from sync_webshop.patches.v0_1.coverage_page import count_governorates
	cities = len(count_governorates())

	# What a visitor can actually browse and buy today. "Show in website" is
	# inherited down the group tree, so a plain join on the flag misses every
	# product sitting in a child group and reports zero.
	from sync_webshop.api.catalog import _website_item_groups
	shown = _website_item_groups()
	flavours = _int(frappe.db.sql("""
		SELECT COUNT(DISTINCT i.name)
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.price_list = %%s AND p.selling = 1
		WHERE i.disabled = 0 AND i.item_group IN %(groups)s
	""" % {"groups": _sql_tuple(shown) if shown is not None else "(SELECT name FROM `tabItem Group`)"},
		price_list)[0][0])

	articles = _int(frappe.db.count("Webshop Post", {"published": 1})) \
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
	cities = _int(settings.get("stats_cities_override")) or raw["cities"]
	customers = max(raw["customers"], _int(settings.get("stats_min_customers")))

	items = [
		{"key": "orders", "value": orders, "suffix": "+",
		 "label_ar": "طلب اتسلّم بنجاح", "label_en": "Orders delivered", "icon": "\U0001F4E6"},
		{"key": "repeat", "value": raw["repeat"], "suffix": "+",
		 "label_ar": "عميل رجع اشترى تاني", "label_en": "Customers who came back", "icon": "\U0001F501"},
		{"key": "packs", "value": raw["packs"], "suffix": "+",
		 "label_ar": "عبوة بن وصلت لبيوتكم", "label_en": "Packs shipped", "icon": "\u2615"},
		{"key": "cities", "value": cities, "suffix": "",
		 "label_ar": "محافظة بنوصلها", "label_en": "Cities we reach", "icon": "\U0001F69A"},
		{"key": "flavours", "value": raw["flavours"], "suffix": "",
		 "label_ar": "نكهة ودرجة تحميص", "label_en": "Flavours and roasts", "icon": "\U0001F31F"},
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
