# -*- coding: utf-8 -*-
"""
Replace the placeholder contact details with the real ones published on
dpono.com — the owner's own site, so this is their data, not invented.

Anything already filled in by hand is left alone.
"""
import frappe

# Taken from the live dpono.com pages.
REAL = {
	"phone_number": "01092301212",
	"email_address": "info@dpono.com",
	"whatsapp_number": "201100952413",
}

SOCIAL = [
	{"platform": "Instagram", "link_url": "https://www.instagram.com/dpono013"},
	{"platform": "LinkedIn", "link_url": "https://linkedin.com/company/merciful-group-4450b92b7"},
]

PLACEHOLDERS = {"+20 100 000 0000", "orders@dpono.com", "998877", "wtearsbhawre"}


def execute():
	doc = frappe.get_single("Webshop Content Settings")
	changed = []

	for field, value in REAL.items():
		current = (doc.get(field) or "").strip()
		if not current or current in PLACEHOLDERS:
			doc.set(field, value)
			changed.append(field)

	existing_urls = {(r.link_url or "").rstrip("/") for r in doc.get("social_links", [])}
	for row in SOCIAL:
		if row["link_url"].rstrip("/") not in existing_urls:
			doc.append("social_links", row)
			changed.append("social:" + row["platform"])

	if changed:
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.save()
		frappe.db.commit()
		frappe.clear_cache()

	print("APPLIED=" + (", ".join(changed) if changed else "nothing changed"))
