# -*- coding: utf-8 -*-
"""Teach the catalog about the shop's own categories."""
import io
import sys

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/catalog.py"

APPEND = u'''

# ============================================================================
# فئات الموقع — Webshop Category
#
# A customer-facing list the owner maintains, kept apart from the Item Group
# tree so the ERP's internal structure (the GPS business, packaging tiers,
# internal grades) never leaks into the shop.
# ============================================================================

def _norm_ar(text):
	t = str(text or "").lower()
	t = re.sub(r"[\\u0625\\u0623\\u0622\\u0627]", "\\u0627", t)
	t = re.sub(r"[\\u0649\\u064a]", "\\u064a", t)
	t = t.replace("\\u0629", "\\u0647").replace("\\u0640", "")
	return re.sub(r"\\s+", " ", t).strip()


def _category_members(slug):
	"""Item codes in a category: the pinned ones, plus whatever the rules catch."""
	cat = frappe.get_doc("Webshop Category", slug)
	allowed = _website_item_groups()
	codes = set(frappe.get_all(
		"Item", filters={"webshop_category": slug, "disabled": 0}, pluck="name"))

	groups = [r.item_group for r in cat.rules if r.item_group]
	if groups:
		expanded = []
		for g in groups:
			expanded.extend(_descendants(g) or [g])
		codes.update(frappe.get_all(
			"Item", filters={"item_group": ["in", expanded], "disabled": 0}, pluck="name"))

	keywords = [k for k in (_norm_ar(r.keyword) for r in cat.rules if r.keyword) if k]
	if keywords:
		rows = frappe.get_all(
			"Item", filters={"disabled": 0, "item_group": ["in", allowed or ["__none__"]]},
			fields=["name", "item_name"])
		for row in rows:
			haystack = _norm_ar(row.item_name) + " " + _norm_ar(row.name)
			if any(k in haystack for k in keywords):
				codes.add(row.name)

	# A hand-pinned item belongs to that category only, so a rule here must not
	# also drag it in.
	claimed = set(frappe.get_all(
		"Item", filters={"webshop_category": ["not in", ["", slug]], "disabled": 0},
		pluck="name"))
	return sorted(codes - claimed)


@frappe.whitelist(allow_guest=True)
def get_webshop_categories(with_counts=1):
	set_cors_headers()
	require_catalog_access()

	cats = frappe.get_all(
		"Webshop Category", filters={"is_active": 1},
		fields=["name as slug", "category_name", "category_name_en", "image", "icon",
		        "description_ar", "sort_order"],
		order_by="sort_order asc, category_name asc")

	price_list = _get_price_list()
	for c in cats:
		c["count"] = 0
		if not int(with_counts or 0):
			continue
		codes = _category_members(c["slug"])
		if codes:
			# Only count what a shopper could actually buy.
			c["count"] = frappe.db.count("Item Price", {
				"item_code": ["in", codes], "price_list": price_list, "selling": 1})
	return cats


@frappe.whitelist(allow_guest=True)
def get_category(slug, page=1, page_size=20, sort=None, search=None):
	cat = frappe.db.get_value(
		"Webshop Category", slug,
		["category_name", "category_name_en", "image", "icon", "description_ar", "is_active"],
		as_dict=True)
	if not cat or not cat.is_active:
		frappe.throw(frappe._("Category not found"), frappe.DoesNotExistError)

	result = get_catalog(page=page, page_size=page_size, sort=sort, search=search,
	                     item_codes=_category_members(slug))
	result["category"] = dict(cat, slug=slug)
	return result
'''


def execute():
	s = io.open(P, encoding="utf-8").read()
	if "get_webshop_categories" in s:
		print("already patched")
		return

	if "import re" not in s.split("def ")[0]:
		s = s.replace("import frappe", "import re\n\nimport frappe", 1)

	# Let get_catalog take an explicit shortlist, so the category endpoint reuses
	# its pricing, sorting and paging instead of duplicating them.
	old = "def _catalog_query(groups, search, min_price, max_price, price_list):"
	new = "def _catalog_query(groups, search, min_price, max_price, price_list, item_codes=None):"
	if old not in s:
		sys.exit("!! _catalog_query signature moved")
	s = s.replace(old, new, 1)

	old = ('\t\twhere.append("i.item_group IN %(groups)s")\n'
	       '\t\tparams["groups"] = tuple(groups) if groups else ("__none__",)\n')
	new = old + (
		'\n\tif item_codes is not None:\n'
		'\t\twhere.append("i.item_code IN %(item_codes)s")\n'
		'\t\tparams["item_codes"] = tuple(item_codes) if item_codes else ("__none__",)\n')
	if old not in s:
		sys.exit("!! groups clause moved")
	s = s.replace(old, new, 1)

	old = ("\titem_group=None, search=None, page=1, page_size=20,\n"
	       "\tmin_price=None, max_price=None, sort=None,\n")
	new = ("\titem_group=None, search=None, page=1, page_size=20,\n"
	       "\tmin_price=None, max_price=None, sort=None, item_codes=None,\n")
	if old not in s:
		sys.exit("!! get_catalog signature moved")
	s = s.replace(old, new, 1)

	old = "\twhere, params = _catalog_query(groups, search, min_price, max_price, price_list)"
	new = ("\twhere, params = _catalog_query(\n"
	       "\t\tgroups, search, min_price, max_price, price_list, item_codes)")
	if old not in s:
		sys.exit("!! _catalog_query call moved")
	s = s.replace(old, new, 1)

	io.open(P, "w", encoding="utf-8").write(s + APPEND)
	print("catalog.py patched")
