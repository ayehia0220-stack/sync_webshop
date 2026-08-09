# -*- coding: utf-8 -*-
"""
Tracking ids live in ERPNext, not in the code. Paste an id and that tool starts
working on the next page load; clear it and the script stops loading entirely.
Nothing is hard-coded and nothing loads when the fields are empty.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ANALYTICS_FIELDS = {
	"Webshop SEO Settings": [
		{
			"fieldname": "analytics_section",
			"label": "Analytics & Tracking",
			"fieldtype": "Section Break",
			"insert_after": "structured_data",
			"collapsible": 0,
		},
		{
			"fieldname": "enable_analytics",
			"label": "Enable Tracking",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "analytics_section",
			"description": "Master switch. Off means no tracking script loads at all.",
		},
		{
			"fieldname": "google_tag_manager_id",
			"label": "Google Tag Manager ID",
			"fieldtype": "Data",
			"insert_after": "enable_analytics",
			"description": "GTM-XXXXXXX. Use this if you manage tags in GTM.",
		},
		{
			"fieldname": "ga4_measurement_id",
			"label": "Google Analytics 4 ID",
			"fieldtype": "Data",
			"insert_after": "google_tag_manager_id",
			"description": "G-XXXXXXXXXX. Use this to send straight to GA4.",
		},
		{
			"fieldname": "analytics_column_break",
			"fieldtype": "Column Break",
			"insert_after": "ga4_measurement_id",
		},
		{
			"fieldname": "meta_pixel_id",
			"label": "Meta (Facebook) Pixel ID",
			"fieldtype": "Data",
			"insert_after": "analytics_column_break",
		},
		{
			"fieldname": "tiktok_pixel_id",
			"label": "TikTok Pixel ID",
			"fieldtype": "Data",
			"insert_after": "meta_pixel_id",
		},
		{
			"fieldname": "clarity_project_id",
			"label": "Microsoft Clarity ID",
			"fieldtype": "Data",
			"insert_after": "tiktok_pixel_id",
			"description": "Free session recordings and heatmaps.",
		},
		{
			"fieldname": "require_cookie_consent",
			"label": "Ask for Cookie Consent",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "clarity_project_id",
			"description": "Hold tracking until the visitor accepts. Required in the EU and UK.",
		},
	],
}


def execute():
	create_custom_fields(ANALYTICS_FIELDS, ignore_validate=True)
	frappe.db.commit()
