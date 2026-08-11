# -*- coding: utf-8 -*-
"""
Search-engine plumbing generated from the live catalogue, so a new product is
discoverable without anyone remembering to update a file.
"""
from urllib.parse import quote

import frappe

from sync_webshop.api.catalog import _get_price_list, _website_item_groups
from sync_webshop.api.utils import set_cors_headers

DEFAULT_STORE_URL = "https://shop.dpono.com"


def _store_url():
	"""The public address of the storefront, taken from the allowed origins."""
	try:
		raw = frappe.get_single("Webshop API Settings").allowed_origins or ""
	except Exception:
		raw = ""
	for part in raw.replace(",", "\n").splitlines():
		part = part.strip().rstrip("/")
		if part.startswith("http"):
			return part
	return DEFAULT_STORE_URL


def _xml_escape(text):
	return (
		str(text or "")
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def _sellable_items():
	price_list = _get_price_list()
	groups = _website_item_groups()
	conditions = ["i.disabled = 0", "ip.price_list_rate IS NOT NULL"]
	params = {"price_list": price_list}
	if groups is not None:
		conditions.append("i.item_group IN %(groups)s")
		params["groups"] = tuple(groups) if groups else ("__none__",)

	return frappe.db.sql(
		f"""
		SELECT i.name AS item_code, i.modified
		FROM `tabItem` i
		JOIN `tabItem Price` ip
			ON ip.item_code = i.name AND ip.price_list = %(price_list)s AND ip.selling = 1
		WHERE {' AND '.join(conditions)}
		GROUP BY i.name
		ORDER BY i.modified DESC
		""",
		params,
		as_dict=True,
	)


def _urls():
	base = _store_url()
	urls = [
		{"loc": f"{base}/", "changefreq": "daily", "priority": "1.0"},
		{"loc": f"{base}/products", "changefreq": "daily", "priority": "0.9"},
	]

	urls.append({"loc": f"{base}/blog", "changefreq": "weekly", "priority": "0.8"})

	# The articles carried over from dpono.com. Only the canonical /blog/<slug>
	# goes in — the root path still answers, but listing both would ask Google
	# to index the same article twice.
	for post in frappe.get_all(
		"Webshop Post", filters={"published": 1}, fields=["name", "modified"]
	):
		urls.append(
			{
				"loc": f"{base}/blog/{quote(post.name, safe='')}",
				"lastmod": str(post.modified)[:10],
				"changefreq": "monthly",
				"priority": "0.7",
			}
		)

	for group in frappe.get_all(
		"Webshop Category", filters={"is_active": 1}, fields=["name", "modified"]
	):
		urls.append(
			{
				"loc": f"{base}/products?wcat={quote(group.name, safe='')}",
				"lastmod": str(group.modified)[:10],
				"changefreq": "weekly",
				"priority": "0.75",
			}
		)

	for group in frappe.get_all(
		"Item Group", filters={"show_in_website": 1}, fields=["name", "modified"]
	):
		urls.append(
			{
				"loc": f"{base}/products?category={quote(group.name, safe='')}",
				"lastmod": str(group.modified)[:10],
				"changefreq": "weekly",
				"priority": "0.7",
			}
		)

	for item in _sellable_items():
		urls.append(
			{
				"loc": f"{base}/products/{quote(item.item_code, safe='')}",
				"lastmod": str(item.modified)[:10],
				"changefreq": "weekly",
				"priority": "0.8",
			}
		)

	return urls


def _xml_response(body, filename="sitemap.xml", content_type="application/xml; charset=utf-8"):
	# Frappe's binary responder needs a filename; 'inline' keeps the browser
	# and crawlers from treating it as a download.
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = body.encode("utf-8")
	frappe.local.response.type = "binary"
	frappe.local.response.display_content_as = "inline"
	frappe.local.response.headers = frappe.local.response.get("headers") or {}
	frappe.local.response.headers["Content-Type"] = content_type
	frappe.local.response.headers["Cache-Control"] = "public, max-age=3600"


@frappe.whitelist(allow_guest=True)
def sitemap():
	"""Every page worth indexing: home, listing, each category, each sellable product."""
	rows = []
	for url in _urls():
		parts = [f"<loc>{_xml_escape(url['loc'])}</loc>"]
		if url.get("lastmod"):
			parts.append(f"<lastmod>{url['lastmod']}</lastmod>")
		parts.append(f"<changefreq>{url['changefreq']}</changefreq>")
		parts.append(f"<priority>{url['priority']}</priority>")
		rows.append("  <url>" + "".join(parts) + "</url>")

	body = (
		'<?xml version="1.0" encoding="UTF-8"?>\n'
		'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
		+ "\n".join(rows)
		+ "\n</urlset>\n"
	)
	_xml_response(body, "sitemap.xml")


@frappe.whitelist(allow_guest=True)
def robots():
	"""
	Cart and checkout are private to a shopper and hold no content worth
	indexing, so they stay out of the crawl.
	"""
	base = _store_url()
	custom = ""
	try:
		custom = (frappe.get_single("Webshop SEO Settings").robots_txt or "").strip()
	except Exception:
		custom = ""

	body = custom or (
		"User-agent: *\n"
		"Allow: /\n"
		"Disallow: /cart\n"
		"Disallow: /checkout\n"
		"Disallow: /dashboard\n"
		"Disallow: /track\n"
		"Disallow: /*?*sort=\n"
		"Disallow: /*?*min=\n"
		"Disallow: /*?*max=\n"
		f"\nSitemap: {base}/sitemap.xml\n"
	)
	_xml_response(body, "robots.txt", "text/plain; charset=utf-8")


@frappe.whitelist(allow_guest=True)
def get_site_schema():
	"""Organization and WebSite structured data, built from the store's own settings."""
	set_cors_headers()
	base = _store_url()

	content = frappe.get_single("Webshop Content Settings")
	theme = frappe.get_single("Webshop Theme Settings")
	name = content.get("site_name") or "dpono"

	organisation = {
		"@context": "https://schema.org",
		"@type": "Organization",
		"name": name,
		"url": base,
	}
	logo = theme.get("logo")
	if logo:
		organisation["logo"] = frappe.utils.get_url(logo)

	contact = {}
	if content.get("phone_number"):
		contact["telephone"] = content.get("phone_number")
	if content.get("email_address"):
		contact["email"] = content.get("email_address")
	if contact:
		organisation["contactPoint"] = {"@type": "ContactPoint", "contactType": "customer service", **contact}

	socials = [
		row.link_url for row in content.get("social_links", [])
		if row.link_url and str(row.link_url).startswith("http")
	]
	if socials:
		organisation["sameAs"] = socials

	website = {
		"@context": "https://schema.org",
		"@type": "WebSite",
		"name": name,
		"url": base,
		"potentialAction": {
			"@type": "SearchAction",
			"target": {"@type": "EntryPoint", "urlTemplate": f"{base}/products?search={{search_term_string}}"},
			"query-input": "required name=search_term_string",
		},
	}

	return {"organization": organisation, "website": website}
