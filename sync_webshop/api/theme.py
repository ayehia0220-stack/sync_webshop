import frappe
from sync_webshop.api.utils import set_cors_headers, full_url

@frappe.whitelist(allow_guest=True)
def get_theme():
	"""
	Returns this server's Webshop Theme Settings as JSON.
	"""
	set_cors_headers()
	settings = frappe.get_single("Webshop Theme Settings")
	return {
		"logo": full_url(settings.logo),
		"favicon": full_url(settings.favicon),
		"layout_style": settings.layout_style,
		"hero_background_image": full_url(settings.hero_background_image),
		"colors": {
			"primary": settings.primary_color,
			"secondary": settings.secondary_color,
			"accent": settings.accent_color,
			"background": settings.background_color,
			"top_bar_bg": settings.top_bar_bg_color,
			"top_bar_text": settings.top_bar_text_color,
			"header_bg": settings.header_bg_color,
			"header_text": settings.header_text_color,
			"nav_bg": settings.nav_bg_color,
			"nav_text": settings.nav_text_color,
			"footer_bg": settings.footer_bg_color,
			"footer_text": settings.footer_text_color,
		},
"card": {
			"radius": settings.get("card_radius") or 15,
			"border": settings.get("card_border_color") or "#ECECEC",
			"heading": settings.get("heading_color") or "#253D4E",
			"muted": settings.get("muted_text_color") or "#7E7E7E",
			"product_width": settings.get("product_card_width") or 210,
			"category_width": settings.get("category_card_width") or 150,
			"product_cols_mobile": settings.get("product_card_width_mobile") or 2,
			"category_cols_mobile": settings.get("category_card_width_mobile") or 3,
			"tints": [
				settings.get("tint_color_1") or "#DEF9EC",
				settings.get("tint_color_2") or "#FEEFEA",
				settings.get("tint_color_3") or "#F2FCE4",
				settings.get("tint_color_4") or "#FFF3EB",
				settings.get("tint_color_5") or "#F2F6FF",
				settings.get("tint_color_6") or "#FFF3FF",
			],
		},
		"fonts": {
				"heading": settings.font_heading,
				"body": settings.font_body,
			},
			"dimensions": {
				"header_max_width": settings.header_max_width or 1200,
				"header_height": settings.header_height or 80,
				"header_padding_vertical": settings.header_padding_vertical or 15,
				"header_padding_horizontal": settings.header_padding_horizontal or 15,
				"logo_height": settings.logo_height or 45,
				"logo_width": settings.logo_width or 0,
				"search_bar_max_width": settings.search_bar_max_width or 600,
				"search_bar_height": settings.search_bar_height or 45,
				"nav_bar_height": settings.nav_bar_height or 50,
				"hero_height": settings.hero_height or 400,
				"hero_width": settings.hero_width or 1200,
			},
	}
