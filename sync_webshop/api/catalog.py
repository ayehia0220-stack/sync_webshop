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


@frappe.whitelist(allow_guest=True)
def get_catalog(item_group=None, search=None, page=1, page_size=20):
	"""
	Returns a page of items + their price in the configured default Price
	List. Backs the product listing page and the landing page's featured
	category sections.
	"""
	set_cors_headers()
	require_catalog_access()

	page = int(page)
	page_size = min(int(page_size), 100)

	filters = {"disabled": 0}
	if item_group:
		filters["item_group"] = item_group

	or_filters = None
	if search:
		or_filters = [
			["item_name", "like", f"%{search}%"],
			["item_code", "like", f"%{search}%"],
		]

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

	price_list = _get_price_list()
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
