import frappe
from sync_webshop.api.utils import set_cors_headers, full_url


@frappe.whitelist(allow_guest=True)
def get_content():
	"""
	Returns this server's text content: site name, taglines, about/footer
	text (English + Arabic), plus active banners, featured categories, and
	testimonials, each sorted by their sort_order field.
	"""
	set_cors_headers()
	settings = frappe.get_single("Webshop Content Settings")

	def active_sorted(rows):
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

	return {
		"site_name": settings.site_name,
		"tagline_en": settings.tagline_en,
		"tagline_ar": settings.tagline_ar,
		"hero_quote_en": settings.hero_quote_en,
		"hero_quote_ar": settings.hero_quote_ar,
		"about_text_en": settings.about_text_en,
		"about_text_ar": settings.about_text_ar,
		"footer_text_en": settings.footer_text_en,
		"footer_text_ar": settings.footer_text_ar,
		"banners": banners,
		"featured_categories": featured_categories,
		"testimonials": testimonials,
		"trust_badges": trust_badges,
	}
