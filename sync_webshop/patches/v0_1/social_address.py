# -*- coding: utf-8 -*-
"""
The shop's social pages and where the roastery actually is.

The two social rows that existed had no URL on them, so the footer rendered
links that went nowhere. All four are set here, and the address gets a map link
so a customer can open directions rather than copy text into another app.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LINKS = [
	("Facebook", "https://www.facebook.com/dpono0/"),
	("Instagram", "https://www.instagram.com/dpono0/"),
	("TikTok", "https://www.tiktok.com/@dpono0"),
	("LinkedIn", "https://www.linkedin.com/company/mercifulgroup-eg/"),
]

MAP_URL = "https://maps.app.goo.gl/i4mHLqTHTgdTG3Y99"


def execute():
	create_custom_fields({"Webshop Content Settings": [{
		"fieldname": "google_maps_url",
		"label": "رابط الموقع على خرائط جوجل",
		"fieldtype": "Data",
		"insert_after": "contact_address_ar",
		"description": "لما يتحط، العنوان في الفوتر بيبقى قابل للضغط ويفتح الاتجاهات.",
	}]}, ignore_validate=True)

	settings = frappe.get_single("Webshop Content Settings")

	existing = {(row.platform or "").strip().lower(): row for row in settings.social_links}
	added, fixed = [], []
	for platform, url in LINKS:
		row = existing.get(platform.lower())
		if row:
			if (row.link_url or "").strip() != url:
				row.link_url = url
				fixed.append(platform)
		else:
			settings.append("social_links", {"platform": platform, "link_url": url})
			added.append(platform)

	if not (settings.get("google_maps_url") or "").strip():
		settings.google_maps_url = MAP_URL

	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()
	frappe.db.commit()
	frappe.clear_cache()

	print("ADDED=%s FIXED=%s" % (added, fixed))
	print("MAP=%s" % settings.get("google_maps_url"))
