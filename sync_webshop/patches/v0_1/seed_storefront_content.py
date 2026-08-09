# -*- coding: utf-8 -*-
"""
Give the storefront a complete, sensible starting point that the owner edits
from ERPNext — never from code.

Two rules:
  * Only fields still holding setup junk are touched. Anything genuinely
    written stays exactly as it is.
  * Nothing is invented that would mislead a shopper: no offers, no fake
    reviews, no claims about delivery times or guarantees. Placeholders here
    describe the shop, not promises.

Safe to run again at any time.
"""
import re

import frappe

# Values typed while clicking through setup. Matched exactly, so a real word
# can never be replaced by accident.
JUNK_EXACT = {
	"dsvds", "fffff", "sdfg", "fsdfsff", "asfcasd", "efvcac", "adsfasdf",
	"asfdcasdfc", "998877", "wtearsbhawre", "tdzyneyne", "sfdgtws",
	"safdasffasfa", "sfasfdfsaaaaaaaaaaaaaaaa", "casfcsadcf", "asdfcvasdfv",
	"safdfffaaaa", "xacadscf", "aaaaaaaa", "sadc", "ftgt", "ccc",
	"100110101001", "sdfgsdfg", "asdasd", "test", "aaa", "abc",
}

CONTENT_DEFAULTS = {
	"tagline_ar": "قهوة محمّصة على مزاجك",
	"tagline_en": "Coffee roasted your way",
	"hero_quote_ar": "اختار درجة التحميص والوزن اللي يناسبك، ووصّلها لحد باب البيت.",
	"hero_quote_en": "Pick your roast and your size, delivered to your door.",
	"top_bar_message_ar": "بن مختص، محمّص ومعبّى بعناية",
	"top_bar_message_en": "Specialty coffee, roasted and packed with care",
	"about_text_ar": "دبونو متجر بن مختص. بنحمّص ونعبّي بأوزان مختلفة — من كيس ١٠ جرام لحد عبوة الكيلو — عشان تلاقي اللي يناسب بيتك أو محلك.",
	"about_text_en": "dpono is a specialty coffee store. We roast and pack in sizes from 10g sachets to full kilos, for homes and cafés alike.",
	"footer_text_ar": "بن مختص، محمّص ومعبّى بعناية.",
	"footer_text_en": "Specialty coffee, roasted and packed with care.",
	"contact_address_ar": "مصر",
	"contact_address_en": "Egypt",
	"email_address": "orders@dpono.com",
	"seo_meta_title_ar": "دبونو | بن مختص",
	"seo_meta_title_en": "dpono | Specialty coffee",
	"seo_meta_description_ar": "بن مختص محمّص ومعبّى بأوزان مختلفة، من كيس ١٠ جرام لحد عبوة الكيلو.",
	"seo_meta_description_en": "Specialty coffee, roasted and packed in sizes from 10g sachets to full kilos.",
	"related_products_title_ar": "منتجات مشابهة",
	"related_products_title_en": "You may also like",
}

# Fields that must hold a specific shape or they are worthless.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[+\d][\d\s()\-]{7,}$")
URL_RE = re.compile(r"^(https?://|/)")

# Starting trust badges. Each states a plain fact about how the shop works —
# nothing that could turn into a promise the business has not made.
TRUST_BADGES = [
	{"label_ar": "بن مختص", "label_en": "Specialty coffee",
	 "description_ar": "محمّص ومعبّى عندنا", "description_en": "Roasted and packed in house", "icon": "Quality"},
	{"label_ar": "الدفع عند الاستلام", "label_en": "Cash on delivery",
	 "description_ar": "ادفع لما يوصلك", "description_en": "Pay when it arrives", "icon": "Payment"},
	{"label_ar": "اختار ميعاد التوصيل", "label_en": "Choose your delivery date",
	 "description_ar": "من صفحة إتمام الطلب", "description_en": "At checkout", "icon": "Schedule"},
	{"label_ar": "توصيل لباب البيت", "label_en": "Delivered to your door",
	 "description_ar": "تقدر تتبّع طلبك برقمه", "description_en": "Track it with your order number", "icon": "Delivery"},
]

NAV_LINKS = [
	{"label_ar": "كل المنتجات", "label_en": "All products", "link_url": "/products", "is_external": 0},
	{"label_ar": "تتبّع الطلب", "label_en": "Track order", "link_url": "/track", "is_external": 0},
]


def is_junk(value, field=""):
	if value is None:
		return True
	text = re.sub(r"<[^>]*>", "", str(value)).strip()
	if len(text) < 2:
		return True
	if text.lower() in JUNK_EXACT:
		return True
	if field == "email_address":
		return not EMAIL_RE.match(text)
	if field in ("phone_number", "whatsapp_number"):
		return not PHONE_RE.match(text)
	if field.endswith("_ar") and not re.search(r"[؀-ۿ]", text):
		return True
	return False


def _seed_content_fields(doc):
	changed = []
	for field, value in CONTENT_DEFAULTS.items():
		if not hasattr(doc, field):
			continue
		if is_junk(doc.get(field), field):
			doc.set(field, value)
			changed.append(field)

	# A junk phone number is worse than none — it sends customers nowhere.
	for field in ("phone_number", "whatsapp_number"):
		if hasattr(doc, field) and doc.get(field) and is_junk(doc.get(field), field):
			doc.set(field, None)
			changed.append(field + " (cleared)")

	return changed


def _tidy_child_tables(doc):
	"""
	These lists live inside Webshop Content Settings, so they are edited on the
	parent document. Junk rows go; genuine rows stay untouched.
	"""
	report = {}

	# Trust badges
	kept = [r for r in doc.get("trust_badges", []) if not (is_junk(r.label_en) and is_junk(r.label_ar))]
	report["badges_removed"] = len(doc.get("trust_badges", [])) - len(kept)
	doc.set("trust_badges", kept)
	if not kept:
		for idx, badge in enumerate(TRUST_BADGES, start=1):
			doc.append("trust_badges", {**badge, "is_active": 1, "sort_order": idx})
		report["badges_added"] = len(TRUST_BADGES)

	# Navigation
	kept = [
		r for r in doc.get("nav_links", [])
		if not is_junk(r.label_en) and URL_RE.match(str(r.link_url or ""))
	]
	report["nav_removed"] = len(doc.get("nav_links", [])) - len(kept)
	doc.set("nav_links", kept)
	if not kept:
		for link in NAV_LINKS:
			doc.append("nav_links", link)
		report["nav_added"] = len(NAV_LINKS)

	# Social links pointing nowhere are worse than no icon at all.
	kept = [r for r in doc.get("social_links", []) if URL_RE.match(str(r.link_url or ""))]
	report["social_removed"] = len(doc.get("social_links", [])) - len(kept)
	doc.set("social_links", kept)

	# A made-up review is worse than no reviews at all.
	kept = [r for r in doc.get("testimonials", []) if not (is_junk(r.quote_en) and is_junk(r.quote_ar))]
	report["testimonials_removed"] = len(doc.get("testimonials", [])) - len(kept)
	doc.set("testimonials", kept)

	# Featured categories that point at nothing, or carry setup labels.
	kept = []
	for r in doc.get("featured_categories", []):
		if not r.item_group or not frappe.db.exists("Item Group", r.item_group):
			continue
		if is_junk(r.display_label_en) and is_junk(r.display_label_ar):
			# The group has a perfectly good name — use it instead of dropping the row.
			r.display_label_en = r.item_group
			r.display_label_ar = frappe.db.get_value("Item Group", r.item_group, "item_group_name")
		kept.append(r)
	report["featured_removed"] = len(doc.get("featured_categories", [])) - len(kept)
	doc.set("featured_categories", kept)

	return report


def execute():
	doc = frappe.get_single("Webshop Content Settings")
	report = {"content": _seed_content_fields(doc)}
	report.update(_tidy_child_tables(doc))

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("SEEDED=" + str(report))
