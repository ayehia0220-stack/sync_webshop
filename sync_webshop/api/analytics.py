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
