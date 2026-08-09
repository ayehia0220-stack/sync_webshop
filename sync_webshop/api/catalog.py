import frappe

from sync_webshop.api.utils import set_cors_headers, full_url, require_catalog_access

# Sorting is user supplied, so it is mapped through this whitelist and never
# interpolated from the request.
SORT_OPTIONS = {
	"name_asc": "i.item_name ASC",
	"name_desc": "i.item_name DESC",
	"price_asc": "price IS NULL, price ASC",
	"price_desc": "price IS NULL, price DESC",
	"newest": "i.creation DESC",
}
DEFAULT_SORT = "name_asc"

MAX_PAGE_SIZE = 100


def _get_price_list():
	settings = frappe.get_single("Webshop API Settings")
	return settings.default_price_list or "Standard Selling"


def _descendants(item_group):
	"""An item group plus every group beneath it in the tree."""
	row = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not row:
		return []
	return frappe.get_all(
		"Item Group",
		filters={"lft": [">=", row.lft], "rgt": ["<=", row.rgt]},
		pluck="name",
	)


def _website_item_groups():
	"""
	Every item group the storefront may show: the groups ticked "Show in Website"
	plus everything beneath them. This is what keeps the coffee shop from
	listing the GPS side of the business — the owner controls it from ERPNext,
	no code change needed.
	Returns None when nothing is ticked, meaning "no restriction".
	"""
	roots = frappe.get_all("Item Group", filters={"show_in_website": 1}, fields=["name", "lft", "rgt"])
	if not roots:
		return None
	names = set()
	for root in roots:
		names.update(
			frappe.get_all(
				"Item Group",
				filters={"lft": [">=", root.lft], "rgt": ["<=", root.rgt]},
				pluck="name",
			)
		)
	return sorted(names)


def _allowed_groups(item_group=None):
	"""Resolve the requested category against what the storefront is allowed to show."""
	allowed = _website_item_groups()
	if not item_group:
		return allowed
	requested = _descendants(item_group)
	if allowed is None:
		return requested or [item_group]
	scoped = [g for g in requested if g in allowed]
	# An out-of-scope category must return nothing rather than silently widening.
	return scoped or ["__none__"]


def _catalog_query(groups, search, min_price, max_price, price_list):
	"""Shared WHERE clause + params for the listing and its count."""
	where = ["i.disabled = 0", "i.price IS NOT NULL"]
	params = {"price_list": price_list}

	if groups is not None:
		where.append("i.item_group IN %(groups)s")
		params["groups"] = tuple(groups) if groups else ("__none__",)

	if search:
		where.append("(i.item_name LIKE %(search)s OR i.item_code LIKE %(search)s)")
		params["search"] = f"%{search}%"

	if min_price is not None:
		where.append("i.price >= %(min_price)s")
		params["min_price"] = min_price

	if max_price is not None:
		where.append("i.price <= %(max_price)s")
		params["max_price"] = max_price

	return " AND ".join(where), params


BASE_FROM = """
	FROM (
		SELECT
			it.name AS item_code,
			COALESCE(NULLIF(it.website_title, ''), it.item_name) AS item_name,
			COALESCE(NULLIF(it.website_short_description, ''), it.description) AS description,
			it.image,
			it.item_group, it.stock_uom, it.creation, it.disabled,
			ip.price_list_rate AS price, ip.currency,
			COALESCE(bin.qty, 0) AS stock_qty
		FROM `tabItem` it
		LEFT JOIN `tabItem Price` ip
			ON ip.item_code = it.name AND ip.price_list = %(price_list)s AND ip.selling = 1
		LEFT JOIN (
			SELECT item_code, SUM(actual_qty) AS qty FROM `tabBin` GROUP BY item_code
		) bin ON bin.item_code = it.name
	) i
"""


@frappe.whitelist(allow_guest=True)
def get_catalog(
	item_group=None, search=None, page=1, page_size=20,
	min_price=None, max_price=None, sort=None,
):
	"""
	A page of sellable items. Items without a price in the configured price list
	are left out — a shopper cannot buy them, so listing them only adds noise.
	"""
	set_cors_headers()
	require_catalog_access()

	page = max(1, int(page or 1))
	page_size = min(max(1, int(page_size or 20)), MAX_PAGE_SIZE)
	min_price = float(min_price) if min_price not in (None, "") else None
	max_price = float(max_price) if max_price not in (None, "") else None
	order_by = SORT_OPTIONS.get(sort or DEFAULT_SORT, SORT_OPTIONS[DEFAULT_SORT])

	price_list = _get_price_list()
	groups = _allowed_groups(item_group)
	where, params = _catalog_query(groups, search, min_price, max_price, price_list)
	params.update({"limit": page_size, "offset": (page - 1) * page_size})

	rows = frappe.db.sql(
		f"""
		SELECT i.item_code, i.item_name, i.description, i.image, i.item_group,
		       i.stock_uom, i.price, i.currency, i.stock_qty
		{BASE_FROM}
		WHERE {where}
		ORDER BY {order_by}
		LIMIT %(limit)s OFFSET %(offset)s
		""",
		params,
		as_dict=True,
	)

	total_count = frappe.db.sql(
		f"SELECT COUNT(*) {BASE_FROM} WHERE {where}", params
	)[0][0]

	items = [
		{
			"item_code": r.item_code,
			"item_name": r.item_name,
			"description": r.description,
			"image": full_url(r.image),
			"item_group": r.item_group,
			"stock_uom": r.stock_uom,
			"price": float(r.price) if r.price is not None else None,
			"currency": r.currency,
			"in_stock": (r.stock_qty or 0) > 0,
		}
		for r in rows
	]

	return {
		"items": items,
		"page": page,
		"page_size": page_size,
		"total_count": total_count,
		"total_pages": max(1, -(-total_count // page_size)),
		"price_list": price_list,
		# The resolved key, never the raw input.
		"sort": sort if sort in SORT_OPTIONS else DEFAULT_SORT,
		"sort_options": list(SORT_OPTIONS.keys()),
		"price_range": _get_price_range(price_list, item_group),
	}


def _get_price_range(price_list, item_group=None):
	"""Cheapest and dearest sellable item, used to seed the price filter."""
	groups = _allowed_groups(item_group)
	where, params = _catalog_query(groups, None, None, None, price_list)
	row = frappe.db.sql(
		f"SELECT MIN(i.price) AS min_price, MAX(i.price) AS max_price {BASE_FROM} WHERE {where}",
		params,
		as_dict=True,
	)
	if row and row[0].get("max_price") is not None:
		return {
			"min_price": float(row[0]["min_price"] or 0),
			"max_price": float(row[0]["max_price"] or 0),
		}
	return {"min_price": 0, "max_price": 0}


@frappe.whitelist(allow_guest=True)
def get_item(item_code):
	"""Full detail for a single item, for the product detail page."""
	set_cors_headers()
	require_catalog_access()

	allowed = _website_item_groups()
	item = frappe.db.get_value(
		"Item",
		{"name": item_code, "disabled": 0},
		["name", "item_name", "website_title", "description", "website_short_description",
		 "item_group", "image", "stock_uom", "brand"],
		as_dict=True,
	)
	if not item or (allowed is not None and item.item_group not in allowed):
		frappe.throw("Item not found", frappe.DoesNotExistError)

	price_list = _get_price_list()
	price = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list, "selling": 1},
		["price_list_rate", "currency"],
		as_dict=True,
	)
	stock_qty = frappe.db.sql(
		"SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s", item_code
	)[0][0]

	crumbs = []
	group = frappe.db.get_value("Item Group", item.item_group, ["lft", "rgt"], as_dict=True)
	if group:
		ancestors = frappe.get_all(
			"Item Group",
			filters={"lft": ["<=", group.lft], "rgt": [">=", group.rgt], "show_in_website": 1},
			fields=["name", "item_group_name", "website_title"],
			order_by="lft",
		)
		crumbs = [{"name": a.name, "label": a.website_title or a.item_group_name} for a in ancestors]

	return {
		"item_code": item.name,
		"item_name": item.website_title or item.item_name,
		"description": item.website_short_description or item.description,
		"item_group": item.item_group,
		"brand": item.brand,
		"image": full_url(item.image),
		"images": _item_images(item_code, item.image),
		"stock_uom": item.stock_uom,
		"price": float(price.price_list_rate) if price else None,
		"currency": price.currency if price else None,
		"in_stock": (stock_qty or 0) > 0,
		"stock_qty": float(stock_qty or 0),
		"price_list": price_list,
		"breadcrumbs": crumbs,
	}


def _item_images(item_code, main_image):
	"""Main image first, then any other images attached to the item."""
	urls = []
	if main_image:
		urls.append(full_url(main_image))
	attached = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Item", "attached_to_name": item_code, "is_folder": 0},
		fields=["file_url"],
		order_by="creation asc",
		limit_page_length=10,
	)
	for f in attached:
		url = full_url(f.file_url)
		if url and url not in urls and any(
			f.file_url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
		):
			urls.append(url)
	return urls


@frappe.whitelist(allow_guest=True)
def get_categories():
	"""
	Browsable categories: the website-enabled groups that actually have something
	to sell, with a count and a depth so the storefront can indent them.
	"""
	set_cors_headers()
	require_catalog_access()

	price_list = _get_price_list()
	groups = frappe.get_all(
		"Item Group",
		filters={"show_in_website": 1},
		fields=["name", "item_group_name", "website_title", "image", "parent_item_group", "lft", "rgt"],
		order_by="lft asc",
	)
	if not groups:
		return []

	counts = dict(
		frappe.db.sql(
			"""
			SELECT it.item_group, COUNT(*)
			FROM `tabItem` it
			JOIN `tabItem Price` ip
				ON ip.item_code = it.name AND ip.price_list = %(price_list)s AND ip.selling = 1
			WHERE it.disabled = 0
			GROUP BY it.item_group
			""",
			{"price_list": price_list},
		)
	)

	by_name = {g.name: g for g in groups}
	depths = {}
	for g in groups:
		depth, parent = 0, g.parent_item_group
		while parent in by_name:
			depth += 1
			parent = by_name[parent].parent_item_group
		depths[g.name] = depth

	results = []
	for g in groups:
		# Roll a parent group's total up from everything beneath it.
		total = sum(c for name, c in counts.items() if name in _subtree_names(groups, g))
		if not total:
			continue
		results.append(
			{
				"name": g.name,
				"label": g.website_title or g.item_group_name,
				"image": full_url(g.image),
				"parent": g.parent_item_group if g.parent_item_group in by_name else None,
				"depth": depths[g.name],
				"count": total,
			}
		)
	return results


def _subtree_names(groups, group):
	return {g.name for g in groups if group.lft <= g.lft and g.rgt <= group.rgt}


@frappe.whitelist(allow_guest=True)
def get_search_suggestions(search):
	set_cors_headers()
	require_catalog_access()
	if not search or len(search) < 2:
		return []

	allowed = _website_item_groups()
	results = []

	categories = frappe.get_all(
		"Item Group",
		filters={"show_in_website": 1, "item_group_name": ["like", f"%{search}%"]},
		fields=["name", "item_group_name", "website_title", "image"],
		limit_page_length=3,
	)
	for cat in categories:
		results.append(
			{
				"type": "category",
				"id": cat.name,
				"name": cat.website_title or cat.item_group_name,
				"image": full_url(cat.image) if cat.image else None,
			}
		)

	item_filters = {"disabled": 0, "item_name": ["like", f"%{search}%"]}
	if allowed is not None:
		item_filters["item_group"] = ["in", allowed]
	items = frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name as item_code", "item_name", "website_title", "image", "item_group"],
		limit_page_length=5,
	)
	for i in items:
		results.append(
			{
				"type": "item",
				"id": i.item_code,
				"name": i.website_title or i.item_name,
				"image": full_url(i.image) if i.image else None,
				"category": i.item_group,
			}
		)

	return results
