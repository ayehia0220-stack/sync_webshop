# -*- coding: utf-8 -*-
"""
Rebuild the shop categories around what is actually on the shelf.

The catalogue is 68 products and every one of them is coffee. The earlier
"مكسرات" category was matching بندق and لوز inside names like
"أكياس بن منتج تام-بندق-10" — that is hazelnut-flavoured coffee, not a bag of
hazelnuts. It read as 11 products the shop does not sell.

So: قهوة for everything today, توابل and أخرى standing ready and hidden until
they hold something. Empty categories do not render, so an owner can add tea
next month and it appears on its own.

Coffee is split by flavour, because that is the choice a customer is actually
making — "سادة ولا بنكهة" — not by pack size, which is already on the product.
"""
import frappe

PLAIN = ["سادة", "ساده", "فاتح", "غامق", "وسط", "اسبريسو", "إسبريسو", "تركي", "محوج"]

CATEGORIES = [
	{
		"slug": "coffee", "ar": "قهوة", "en": "Coffee", "icon": "☕", "order": 10,
		"desc": "بن محمّص على دفعات صغيرة — سادة وبنكهات.",
		"rules": ["بن", "قهوة", "قهوه", "اسبريسو", "إسبريسو", "تركي", "عبوة منتج تام",
		          "أكياس بن", "اكياس بن", "منتج تام"],
	},
	{
		"slug": "spices", "ar": "توابل", "en": "Spices", "icon": "🌿", "order": 20,
		"desc": "قرفة، زنجبيل، هيل وحبهان.",
		"rules": ["قرفة", "قرفه", "زنجبيل", "هيل", "حبهان", "كمون", "كركم",
		          "بهارات", "توابل"],
	},
	{
		"slug": "other", "ar": "أخرى", "en": "Other", "icon": "🍵", "order": 30,
		"desc": "شاي، أعشاب، ومنتجات تانية.",
		"rules": ["شاي", "شاى", "أعشاب", "اعشاب", "نعناع", "كركديه", "ينسون",
		          "بابونج", "مجفف", "مجففة", "تين", "مشمش", "زبيب", "تمر"],
	},
]

RETIRE = ["tea", "dried-fruit", "nuts"]


def execute():
	# The retired ones were either duplicates of "أخرى" or, in the case of
	# nuts, plain wrong. Disabled rather than deleted so nothing that linked to
	# them breaks.
	for slug in RETIRE:
		if frappe.db.exists("Webshop Category", slug):
			frappe.db.set_value("Webshop Category", slug, "is_active", 0)
			print("  retired:", slug)

	for spec in CATEGORIES:
		if frappe.db.exists("Webshop Category", spec["slug"]):
			doc = frappe.get_doc("Webshop Category", spec["slug"])
		else:
			doc = frappe.new_doc("Webshop Category")
			doc.slug = spec["slug"]

		doc.category_name = spec["ar"]
		doc.category_name_en = spec["en"]
		doc.icon = spec["icon"]
		doc.sort_order = spec["order"]
		doc.description_ar = spec["desc"]
		doc.is_active = 1
		doc.set("rules", [])
		for word in spec["rules"]:
			doc.append("rules", {"keyword": word, "weight": 10, "is_active": 1})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.save()
		print("  saved:", spec["ar"])

	frappe.db.commit()
	frappe.clear_cache()

	# --- what a shopper will actually see ------------------------------------
	from sync_webshop.api.catalog import _category_members
	price_list = frappe.get_single("Webshop API Settings").default_price_list
	print()
	print("النتيجة على الموقع:")
	for spec in CATEGORIES:
		codes = _category_members(spec["slug"])
		count = frappe.db.count("Item Price", {
			"item_code": ["in", codes or ["__none__"]],
			"price_list": price_list, "selling": 1}) if codes else 0
		state = "يظهر" if count else "مخفي (فاضي)"
		print("   %s %-8s %3d منتج   %s" % (spec["icon"], spec["ar"], count, state))
