import frappe
from sync_webshop.api.utils import set_cors_headers, full_url
from sync_webshop.api.catalog import _get_price_list
from sync_webshop.api.theme import get_theme

@frappe.whitelist(allow_guest=True)
def get_content():
	"""
	Returns this server's text content and settings.
	"""
	set_cors_headers()
	settings = frappe.get_single("Webshop Content Settings")
	
	def active_sorted(rows):
		if not rows: return []
		active = [r for r in rows if r.get("is_active")]
		return sorted(active, key=lambda r: r.get("sort_order") or 0)

	banners = [
		{
			"image": full_url(row.image),
			"title": row.title,
			"subtitle": row.subtitle,
			"link_url": row.link_url,
		}
		for row in active_sorted(settings.banners)
	]

	featured_categories = [
		{
			"item_group": row.item_group,
			"label_en": row.display_label_en or row.item_group,
			"label_ar": row.display_label_ar,
			"image": full_url(row.image),
		}
		for row in active_sorted(settings.featured_categories)
	]

	testimonials = [
		{
			"quote_en": row.quote_en,
			"quote_ar": row.quote_ar,
			"author": row.author,
			"author_title": row.author_title,
		}
		for row in active_sorted(settings.testimonials)
	]

	trust_badges = [
		{
			"icon": row.icon,
			"label_en": row.label_en,
			"label_ar": row.label_ar,
			"description_en": row.description_en,
			"description_ar": row.description_ar,
		}
		for row in active_sorted(settings.trust_badges)
	]

	nav_links = [
		{
			"label_en": row.label_en,
			"label_ar": row.label_ar,
			"link_url": row.link_url,
			"is_external": row.is_external
		}
		for row in settings.nav_links
	]

	social_links = [
		{
			"platform": row.platform,
			"link_url": row.link_url,
			"icon": row.icon
		}
		for row in settings.social_links
	]

	# Fetch Landing Sections
	landing_sections = []
	sections = frappe.get_all(
		"Webshop Landing Section",
		filters={"enabled": 1},
		fields=["name", "section_title_en", "section_title_ar", "section_subtitle_en", "section_subtitle_ar", "sort_order"],
		order_by="sort_order asc"
	)

	price_list = _get_price_list()
	for s in sections:
		items = frappe.get_all(
			"Webshop Landing Section Item",
			filters={"parent": s.name},
			fields=["item_code"]
		)
		section_items = []
		for item_row in items:
			item_code = item_row.item_code
			item_doc = frappe.get_doc("Item", item_code)
			# Get price
			price = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": price_list}, "price_list_rate")
			section_items.append({
				"item_code": item_code,
				"item_name": item_doc.item_name,
				"image": full_url(item_doc.image) if item_doc.image else None,
				"price": price or 0,
				"currency": frappe.db.get_value("Price List", price_list, "currency")
			})
		landing_sections.append({
			"title_en": s.section_title_en,
			"title_ar": s.section_title_ar,
			"subtitle_en": s.section_subtitle_en,
			"subtitle_ar": s.section_subtitle_ar,
			"items": section_items
		})

	# New Features Data
	footer_settings = frappe.get_single("Webshop Footer Settings")
	footer_columns = []
	if footer_settings.enabled:
		columns = frappe.get_all(
			"Webshop Footer Column",
			filters={"enabled": 1},
			fields=["name", "title_en", "title_ar", "sort_order"],
			order_by="sort_order asc"
		)
		for col in columns:
			col_doc = frappe.get_doc("Webshop Footer Column", col.name)
			footer_columns.append({
				"title_en": col.title_en,
				"title_ar": col.title_ar,
				"links": [
					{
						"label_en": l.label_en,
						"label_ar": l.label_ar,
						"link_url": l.link_url,
						"is_external": l.is_external
					} for l in col_doc.links
				]
			})

	announcement = frappe.get_single("Webshop Announcement Bar")
	announcement_data = {
		"enabled": announcement.enabled,
		"message_en": announcement.message_en,
		"message_ar": announcement.message_ar,
		"background_color": announcement.background_color,
		"text_color": announcement.text_color,
		"link_url": announcement.link_url,
		"show_close_button": announcement.show_close_button
	}

	product_settings = frappe.get_single("Webshop Product Settings")
	product_settings_data = {
		"enable_zoom": product_settings.enable_zoom,
		"show_related_products": product_settings.show_related_products,
		"related_products_title_en": product_settings.related_products_title_en,
		"related_products_title_ar": product_settings.related_products_title_ar,
		"show_sidebar": product_settings.show_sidebar
	}

	popups = frappe.get_all(
		"Webshop Popup",
		filters={"enabled": 1},
		fields=["*"]
	)
	popups_data = [
		{
			"title_en": p.title_en,
			"title_ar": p.title_ar,
			"content_en": p.content_en,
			"content_ar": p.content_ar,
			"image": full_url(p.image) if p.image else None,
			"popup_type": p.popup_type,
			"link_url": p.link_url,
			"button_text_en": p.button_text_en,
			"button_text_ar": p.button_text_ar,
			"delay_seconds": p.delay_seconds,
			"show_once_per_session": p.show_once_per_session
		} for p in popups
	]

	seo_settings = frappe.get_single("Webshop SEO Settings")
	seo_data = {
		"meta_title_en": seo_settings.meta_title_en,
		"meta_title_ar": seo_settings.meta_title_ar,
		"meta_description_en": seo_settings.meta_description_en,
		"meta_description_ar": seo_settings.meta_description_ar,
		"og_title_en": seo_settings.og_title_en,
		"og_title_ar": seo_settings.og_title_ar,
		"og_description_en": seo_settings.og_description_en,
		"og_description_ar": seo_settings.og_description_ar,
		"og_image": full_url(seo_settings.og_image) if seo_settings.og_image else None,
		"canonical_url": seo_settings.canonical_url,
		"robots_txt": seo_settings.robots_txt,
		"sitemap_enabled": seo_settings.sitemap_enabled,
		"structured_data": seo_settings.structured_data,
		"redirects": [
			{
				"source_url": r.source_url,
				"target_url": r.target_url,
				"redirect_type": r.redirect_type
			} for r in seo_settings.redirects
		]
	}

	return {
		"site_name": settings.site_name,
		"show_category_sidebar": settings.show_category_sidebar,
		"show_price_filter": settings.show_price_filter,
		"show_brand_filter": settings.show_brand_filter,
		"sidebar_width": settings.sidebar_width or 220,
		"tagline_en": settings.tagline_en,
		"tagline_ar": settings.tagline_ar,
		"hero_quote_en": settings.hero_quote_en,
		"hero_quote_ar": settings.hero_quote_ar,
		"about_text_en": settings.about_text_en,
		"about_text_ar": settings.about_text_ar,
		"footer_text_en": settings.footer_text_en,
		"footer_text_ar": settings.footer_text_ar,
		"phone_number": settings.phone_number,
		"email_address": settings.email_address,
		"contact_address_en": settings.contact_address_en,
		"contact_address_ar": settings.contact_address_ar,
		"show_top_bar": settings.show_top_bar,
		"top_bar_message_en": settings.top_bar_message_en,
		"top_bar_message_ar": settings.top_bar_message_ar,
		# SEO & Social Sharing
		"seo_meta_description_en": settings.seo_meta_description_en,
		"seo_meta_description_ar": settings.seo_meta_description_ar,
		"seo_og_image": full_url(settings.seo_og_image) if settings.seo_og_image else None,
		"seo_keywords": settings.seo_keywords,
		# Floating Action Buttons
		"show_whatsapp_button": settings.show_whatsapp_button,
		"whatsapp_number": settings.whatsapp_number,
		"whatsapp_message": settings.whatsapp_message,
		"show_back_to_top": settings.show_back_to_top,
		# Lists
		"nav_links": nav_links,
		"social_links": social_links,
		"banners": banners,
		"featured_categories": featured_categories,
		"testimonials": testimonials,
		"trust_badges": trust_badges,
		"landing_sections": landing_sections,
		"theme": get_theme(),
		# New Data
		"footer_settings": {
			"enabled": footer_settings.enabled,
			"footer_logo": full_url(footer_settings.footer_logo) if footer_settings.footer_logo else None,
			"copyright_en": footer_settings.copyright_en,
			"copyright_ar": footer_settings.copyright_ar,
			"columns": footer_columns
		},
		"announcement": announcement_data,
		"product_settings": product_settings_data,
		"popups": popups_data,
		"seo": seo_data,
		# User Auth & Wishlist Settings
		"enable_user_registration": settings.enable_user_registration,
		"enable_wishlist": settings.enable_wishlist
	}
