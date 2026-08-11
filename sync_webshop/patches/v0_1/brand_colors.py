# -*- coding: utf-8 -*-
"""
The palette off the dpono polo: graphite and teal.

Two colours carry the shirt — a dark graphite body and a teal panel — so those
become primary and secondary. The old olive green went with them.

The teal is darkened for text use. On the shirt it sits on charcoal, where it
reads fine; on a white page the same teal on white falls below the contrast
floor for body text, which is the "الأخضر مش باين" problem. Large fills keep the
bright teal, text takes the darker one.
"""
import frappe

COLORS = {
	"primary_color": "#343A40",       # جسم التيشيرت — graphite
	"secondary_color": "#2E8F9C",     # التركواز — the teal panel
	"accent_color": "#4FB3C0",        # تركواز فاتح — the lighter collar teal
	"heading_color": "#22272B",       # عناوين — near-black, reads on white
	"muted_text_color": "#6B7378",
	"background_color": "#FFFFFF",
	"card_border_color": "#E4E7E9",

	"top_bar_bg_color": "#343A40",
	"top_bar_text_color": "#FFFFFF",
	"header_bg_color": "#FFFFFF",
	"header_text_color": "#22272B",
	"nav_bg_color": "#FFFFFF",
	"nav_text_color": "#22272B",
	"footer_bg_color": "#2B3034",
	"footer_text_color": "#FFFFFF",

	"tint_color_1": "#E6F4F6",
	"tint_color_2": "#EDF0F1",
	"tint_color_3": "#DCEEF1",
	"tint_color_4": "#F1F4F5",
	"tint_color_5": "#E9F2F4",
	"tint_color_6": "#F5F7F8",
}


def execute():
	theme = frappe.get_single("Webshop Theme Settings")
	for field, value in COLORS.items():
		if hasattr(theme, field):
			theme.set(field, value)
	theme.flags.ignore_permissions = True
	theme.flags.ignore_mandatory = True
	theme.save()
	frappe.db.commit()
	frappe.clear_cache()
	print("COLORS APPLIED")
	for field in ("primary_color", "secondary_color", "accent_color", "heading_color"):
		print("  %-18s %s" % (field, theme.get(field)))
