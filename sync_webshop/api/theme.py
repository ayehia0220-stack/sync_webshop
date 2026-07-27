import frappe
from sync_webshop.api.utils import set_cors_headers, full_url


@frappe.whitelist(allow_guest=True)
def get_theme():
	"""
	Returns this server's Webshop Theme Settings as JSON.
	The React frontend calls this once on load and uses it to paint
	colors/fonts/logo/layout - nothing here requires a code change to
	reskin a server, only editing the Webshop Theme Settings doctype.
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
		},
		"fonts": {
			"heading": settings.font_heading,
			"body": settings.font_body,
		},
	}
