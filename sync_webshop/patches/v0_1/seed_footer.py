# -*- coding: utf-8 -*-
"""
Give the footer real columns instead of the hardcoded fallback.

Until now no Webshop Footer Column existed, so the storefront fell back to a
built-in list — eight links in one stack, and nothing the owner could change.
These are the same links, grouped the way a reader scans them, and every one is
now editable in the Desk.

Content pages are read from what actually exists, so a policy page that hasn't
been written yet doesn't leave a dead link in the footer.
"""
import frappe

NAV = [
	("الصفحة الرئيسية", "Home", "/"),
	("كل المنتجات", "All products", "/products"),
	("تتبع الطلب", "Track order", "/track"),
	("حسابي", "My account", "/dashboard"),
	("السلة", "Cart", "/cart"),
]

# Preferred order for the policy column; only the ones that exist get used.
POLICY_ORDER = ["about", "shipping-policy", "shipping", "return-policy", "returns",
                "privacy-policy", "privacy", "terms", "faq"]


def execute():
	if frappe.get_all("Webshop Footer Column", limit=1):
		print("columns already exist")
		return

	pages = {
		p.slug: p for p in frappe.get_all(
			"Webshop Content Page", filters={"is_published": 1},
			fields=["name", "slug", "title_ar", "title_en"])
	} if frappe.db.exists("DocType", "Webshop Content Page") else {}

	policy_links = []
	for slug in POLICY_ORDER:
		page = pages.get(slug)
		if not page:
			continue
		policy_links.append({
			"label_ar": page.title_ar or page.title_en or slug,
			"label_en": page.title_en or page.title_ar or slug,
			"link_url": "/page/" + slug,
			"is_external": 0,
		})
	# Anything published that didn't match the preferred order still belongs here.
	for slug, page in pages.items():
		if slug in POLICY_ORDER:
			continue
		policy_links.append({
			"label_ar": page.title_ar or page.title_en or slug,
			"label_en": page.title_en or page.title_ar or slug,
			"link_url": "/page/" + slug,
			"is_external": 0,
		})

	columns = [
		("روابط سريعة", "Quick links", 10,
		 [{"label_ar": a, "label_en": e, "link_url": u, "is_external": 0} for a, e, u in NAV]),
	]
	if policy_links:
		columns.append(("معلومات تهمك", "Information", 20, policy_links))

	for title_ar, title_en, order, links in columns:
		doc = frappe.get_doc({
			"doctype": "Webshop Footer Column",
			"title_ar": title_ar, "title_en": title_en,
			"enabled": 1, "sort_order": order, "links": links,
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		print("  %s — %d link(s)" % (title_ar, len(links)))

	frappe.db.commit()
	frappe.clear_cache()
	print("FOOTER COLUMNS READY")
