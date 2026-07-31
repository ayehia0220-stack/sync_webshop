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
		"fonts": {
			"heading": settings.font_heading,
			"body": settings.font_body,
		},
	}
