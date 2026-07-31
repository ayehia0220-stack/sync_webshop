import frappe
from sync_webshop.api.utils import set_cors_headers, full_url, require_catalog_access

def _get_price_list():
	settings = frappe.get_single("Webshop API Settings")
	return settings.default_price_list or "Standard Selling"

def _get_prices(item_codes, price_list):
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Item Price",
		filters={"item_code": ["in", item_codes], "price_list": price_list, "selling": 1},
		fields=["item_code", "price_list_rate", "currency"],
	)
	# last one wins if there are duplicates - fine for a single default price list
	return {row.item_code: {"rate": row.price_list_rate, "currency": row.currency} for row in rows}

def _get_price_range(price_list, item_group=None):
	"""Returns the min and max price for items in the given price list and optional item group."""
	filters = {"price_list": price_list, "selling": 1}
	if item_group:
		# Get item codes in this group
		item_codes = frappe.get_all("Item", filters={"item_group": item_group, "disabled": 0}, pluck="item_code")
		if not item_codes:
			return {"min_price": 0, "max_price": 0}
		filters["item_code"] = ["in", item_codes]
	
	result = frappe.db.sql("""
		SELECT MIN(price_list_rate) as min_price, MAX(price_list_rate) as max_price
		FROM `tabItem Price`
		WHERE price_list = %(price_list)s AND selling = 1
		{item_filter}
	""".format(
		item_filter="AND item_code IN %(item_codes)s" if item_group else ""
	), {
		"price_list": price_list,
		"item_codes": item_codes if item_group else []
	}, as_dict=True)
	
	if result and result[0]:
		return {
			"min_price": float(result[0].get("min_price") or 0),
			"max_price": float(result[0].get("max_price") or 0)
		}
	return {"min_price": 0, "max_price": 0}

@frappe.whitelist(allow_guest=True)
def get_catalog(item_group=None, search=None, page=1, page_size=20, min_price=None, max_price=None):
	"""
	Returns a page of items + their price in the configured default Price
	List. Backs the product listing page and the landing page's featured
	category sections. Supports price range filtering.
	"""
	set_cors_headers()
	require_catalog_access()
	page = int(page)
	page_size = min(int(page_size), 100)
	min_price = float(min_price) if min_price else None
	max_price = float(max_price) if max_price else None
	
	filters = {"disabled": 0}
	if item_group:
		filters["item_group"] = item_group
	or_filters = None
	if search:
		or_filters = [
			["item_name", "like", f"%{search}%"],
			["item_code", "like", f"%{search}%"],
		]
	
	price_list = _get_price_list()
	
	# If price filtering is active, we need to get eligible item codes first
	price_filtered_codes = None
	if min_price is not None or max_price is not None:
		price_filters = {"price_list": price_list, "selling": 1}
		if min_price is not None:
			price_filters["price_list_rate"] = [">=", min_price]
		if max_price is not None:
			if "price_list_rate" in price_filters:
				# Both min and max - use between
				del price_filters["price_list_rate"]
				price_filters["price_list_rate"] = ["between", [min_price, max_price]]
			else:
				price_filters["price_list_rate"] = ["<=", max_price]
		
		price_filtered_codes = frappe.get_all(
			"Item Price",
			filters=price_filters,
			pluck="item_code"
		)
		if not price_filtered_codes:
			return {
				"items": [],
				"page": page,
				"page_size": page_size,
				"total_count": 0,
				"price_list": price_list,
				"price_range": _get_price_range(price_list, item_group),
			}
		filters["item_code"] = ["in", price_filtered_codes]
	
	items = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["item_code", "item_name", "description", "image", "item_group"],
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
		order_by="item_name asc",
	)
	total_count = frappe.db.count("Item", filters=filters)
	prices = _get_prices([i.item_code for i in items], price_list)
	results = []
	for item in items:
		price = prices.get(item.item_code)
		results.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"image": full_url(item.image),
				"item_group": item.item_group,
				"price": price.get("rate") if price else None,
				"currency": price.get("currency") if price else None,
			}
		)
	return {
		"items": results,
		"page": page,
		"page_size": page_size,
		"total_count": total_count,
		"price_list": price_list,
		"price_range": _get_price_range(price_list, item_group),
	}

@frappe.whitelist(allow_guest=True)
def get_item(item_code):
	"""Returns full detail for a single item, for the product detail page."""
	set_cors_headers()
	require_catalog_access()
	if not frappe.db.exists("Item", {"item_code": item_code, "disabled": 0}):
		frappe.throw("Item not found", frappe.DoesNotExistError)
	item = frappe.get_doc("Item", item_code)
	price_list = _get_price_list()
	prices = _get_prices([item_code], price_list)
	price = prices.get(item_code)
	return {
		"item_code": item.item_code,
		"item_name": item.item_name,
		"description": item.description,
		"item_group": item.item_group,
		"image": full_url(item.image),
		"stock_uom": item.stock_uom,
		"price": price.get("rate") if price else None,
		"currency": price.get("currency") if price else None,
		"price_list": price_list,
	}

@frappe.whitelist(allow_guest=True)
def get_categories():
	set_cors_headers()
	require_catalog_access()
	groups = frappe.get_all(
		"Item Group",
		filters={"show_in_website": 1},
		fields=["name", "item_group_name", "image"]
	)
	return [
		{
			"name": g.name,
			"label": g.item_group_name,
			"image": full_url(g.image)
		}
		for g in groups
	]

@frappe.whitelist(allow_guest=True)
def get_search_suggestions(search):
	set_cors_headers()
	require_catalog_access()
	if not search or len(search) < 2:
		return []
	items = frappe.get_all(
		"Item",
		filters={"disabled": 0, "item_name": ["like", f"%{search}%"]},
		fields=["item_code", "item_name", "image"],
		limit_page_length=5
	)
	return [
		{
			"item_code": i.item_code,
			"item_name": i.item_name,
			"image": full_url(i.image)
		}
		for i in items
	]
