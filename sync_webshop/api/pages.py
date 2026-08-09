# -*- coding: utf-8 -*-
import frappe

from sync_webshop.api.utils import set_cors_headers


@frappe.whitelist(allow_guest=True)
def list_pages():
	"""Published pages, for the footer. Unpublished drafts never leave the Desk."""
	set_cors_headers()
	rows = frappe.get_all(
		"Webshop Page",
		filters={"published": 1, "show_in_footer": 1},
		fields=["slug", "title_ar", "title_en", "sort_order"],
		order_by="sort_order asc, title_ar asc",
	)
	return [
		{
			"slug": r.slug,
			"title_ar": r.title_ar,
			"title_en": r.title_en or r.title_ar,
		}
		for r in rows
	]


@frappe.whitelist(allow_guest=True)
def get_page(slug):
	"""A single published page."""
	set_cors_headers()
	page = frappe.db.get_value(
		"Webshop Page",
		{"slug": slug, "published": 1},
		[
			"slug", "title_ar", "title_en", "content_ar", "content_en",
			"meta_description_ar", "meta_description_en", "modified",
		],
		as_dict=True,
	)
	if not page:
		frappe.throw(frappe._("الصفحة دي مش موجودة."), frappe.DoesNotExistError)
	return page
