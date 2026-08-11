# -*- coding: utf-8 -*-
"""Serve the blog, and tell the front end which legacy paths belong to it."""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/blog.py"

SRC = u'''# -*- coding: utf-8 -*-
"""
التدوينات — the blog.

Carried over from dpono.com with the slugs unchanged, so a link someone saved
two years ago still lands on the article.
"""
import frappe

from sync_webshop.api.utils import set_cors_headers


def _card(post):
	return {
		"slug": post.name,
		"title": post.title_ar or post.title_en or post.name,
		"excerpt": post.excerpt_ar,
		"cover_image": post.cover_image,
		"published_on": post.published_on,
		"reading_minutes": post.reading_minutes or 1,
	}


@frappe.whitelist(allow_guest=True)
def list_posts(page=1, page_size=12):
	set_cors_headers()
	page = max(1, int(page or 1))
	page_size = min(max(1, int(page_size or 12)), 50)

	filters = {"published": 1}
	posts = frappe.get_all(
		"Webshop Post", filters=filters,
		fields=["name", "title_ar", "title_en", "excerpt_ar", "cover_image",
		        "published_on", "reading_minutes"],
		order_by="published_on desc, creation desc",
		start=(page - 1) * page_size, page_length=page_size)

	total = frappe.db.count("Webshop Post", filters)
	return {
		"posts": [_card(p) for p in posts],
		"total_count": total,
		"total_pages": max(1, -(-total // page_size)),
		"page": page,
	}


@frappe.whitelist(allow_guest=True)
def get_post(slug):
	set_cors_headers()
	post = frappe.db.get_value(
		"Webshop Post", slug,
		["name", "title_ar", "title_en", "content_ar", "content_en", "excerpt_ar",
		 "cover_image", "published_on", "reading_minutes", "meta_description_ar",
		 "published"],
		as_dict=True)
	if not post or not post.published:
		frappe.throw(frappe._("Post not found"), frappe.DoesNotExistError)

	# Two or three neighbours to keep a reader moving.
	more = frappe.get_all(
		"Webshop Post", filters={"published": 1, "name": ["!=", slug]},
		fields=["name", "title_ar", "title_en", "excerpt_ar", "cover_image",
		        "published_on", "reading_minutes"],
		order_by="published_on desc", page_length=3)

	return {
		"slug": post.name,
		"title": post.title_ar or post.title_en or post.name,
		"content": post.content_ar or post.content_en or "",
		"excerpt": post.excerpt_ar,
		"cover_image": post.cover_image,
		"published_on": post.published_on,
		"reading_minutes": post.reading_minutes or 1,
		"meta_description": post.meta_description_ar or post.excerpt_ar,
		"related": [_card(p) for p in more],
	}


@frappe.whitelist(allow_guest=True)
def list_slugs():
	"""
	Every path the old site owned.

	The storefront asks for this once so it can recognise a bare /<slug> that
	came from an old link or a search result, rather than showing a 404 and
	throwing away the ranking.
	"""
	set_cors_headers()
	return frappe.get_all("Webshop Post", filters={"published": 1}, pluck="name")
'''


def execute():
	io.open(P, "w", encoding="utf-8").write(SRC)
	print("blog.py written")
