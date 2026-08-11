# -*- coding: utf-8 -*-
"""
Slider movement and footer shape, as settings.

Both are look-and-feel choices the owner should be able to change on a whim, so
they go in Content Settings next to the banners themselves rather than in a
stylesheet.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop Content Settings": [
		{
			"fieldname": "hero_animation",
			"label": "حركة صور الهيرو",
			"fieldtype": "Select",
			"options": "slide\nfade\nzoom",
			"default": "fade",
			"insert_after": "banners",
			"description": "slide = انزلاق جانبي · fade = تلاشي ناعم · zoom = تلاشي مع تكبير بطيء. "
			               "الكلام اللي فوق الصور بيفضل ثابت في كل الأحوال.",
		},
		{
			"fieldname": "footer_columns",
			"label": "عدد أعمدة الفوتر",
			"fieldtype": "Int",
			"default": "3",
			"insert_after": "hero_animation",
			"description": "3 أو 4 — غير عمود اللوجو. لو الروابط كتيرة خليها 4.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	settings = frappe.get_single("Webshop Content Settings")
	for field, value in (("hero_animation", "fade"), ("footer_columns", 3)):
		# Custom Field defaults only reach new documents, and this single
		# already exists — so seed it here.
		if not settings.get(field):
			settings.set(field, value)
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	# --- hand them to the storefront ---------------------------------------
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/content.py"
	s = io.open(p, encoding="utf-8").read()
	if "hero_animation" not in s:
		# The real payload, not the empty fallback dict higher up the file.
		anchor = '"banners": banners,'
		if anchor not in s:
			frappe.throw("content.py: banners payload key not found")
		s = s.replace(
			anchor,
			'"hero_animation": settings.get("hero_animation") or "fade",\n'
			'\t\t"footer_columns": settings.get("footer_columns") or 3,\n\t\t' + anchor,
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)
		print("content.py patched")

	frappe.db.commit()
	frappe.clear_cache()
	print("HERO SETTINGS READY")
