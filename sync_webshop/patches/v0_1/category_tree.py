# -*- coding: utf-8 -*-
"""
فئات الموقع — a two-level list the owner fills, not one the code guesses at.

Two changes to how categories work:

  * A category can sit under another, so قهوة سادة and قهوة بنكهات live inside
    قهوة instead of competing with it.
  * A category shows even with nothing in it, because the owner is building the
    shelf before stocking it. Hiding empty ones made new categories invisible
    until a product happened to match a keyword, which looked broken.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TREE = [
	# (slug, arabic, english, icon, order, parent, keywords)
	("coffee", "قهوة", "Coffee", "☕", 10, None,
	 ["بن", "قهوة", "قهوه", "اسبريسو", "إسبريسو", "تركي", "منتج تام"]),
	("coffee-plain", "قهوة سادة", "Plain coffee", "⚫", 11, "coffee",
	 ["سادة", "ساده", "فاتح", "غامق", "وسط", "اسبريسو", "إسبريسو", "تركي"]),
	("coffee-flavoured", "قهوة بنكهات", "Flavoured coffee", "🍫", 12, "coffee",
	 ["بندق", "لوز", "كراميل", "فانيليا", "سينابون", "شيشة", "تفاح", "موز",
	  "مانجا", "برتقال", "فراولة", "جوز الهند", "نكهة", "محوج"]),
	("tea", "شاي", "Tea", "🍵", 20, None,
	 ["شاي", "شاى", "أعشاب", "اعشاب", "نعناع", "كركديه", "ينسون", "بابونج"]),
	("spices", "توابل", "Spices", "🌿", 30, None,
	 ["قرفة", "قرفه", "زنجبيل", "هيل", "حبهان", "كمون", "كركم", "بهارات", "توابل"]),
	("dried-fruit", "فواكه مجففة", "Dried fruit", "🥭", 40, None,
	 ["مجفف", "مجففة", "مجففه", "تين", "مشمش", "زبيب", "بلح", "تمر", "قراصيا"]),
	("nuts", "مكسرات", "Nuts", "🥜", 50, None,
	 ["مكسرات", "عين جمل", "سوداني", "فستق", "كاجو"]),
]


def execute():
	create_custom_fields({"Webshop Category": [
		{
			"fieldname": "parent_category",
			"label": "تحت فئة",
			"fieldtype": "Link",
			"options": "Webshop Category",
			"insert_after": "slug",
			"description": "سيبها فاضية لو الفئة رئيسية.",
		},
		{
			"fieldname": "show_when_empty",
			"label": "اعرضها حتى لو فاضية",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "is_active",
			"description": "شيل العلامة لو عايز الفئة تختفي لحد ما تحط فيها منتجات.",
		},
	]}, ignore_validate=True)

	for slug, ar, en, icon, order, parent, words in TREE:
		if frappe.db.exists("Webshop Category", slug):
			doc = frappe.get_doc("Webshop Category", slug)
		else:
			doc = frappe.new_doc("Webshop Category")
			doc.slug = slug

		doc.category_name = ar
		doc.category_name_en = en
		doc.icon = icon
		doc.sort_order = order
		doc.is_active = 1
		doc.show_when_empty = 1
		doc.set("rules", [])
		for w in words:
			doc.append("rules", {"keyword": w, "weight": 10, "is_active": 1})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.save()

	# Parents are set second, so the row being linked to already exists.
	for slug, _ar, _en, _icon, _order, parent, _w in TREE:
		frappe.db.set_value("Webshop Category", slug, "parent_category", parent or "")

	# "أخرى" was a placeholder for tea and fruit, which now have their own.
	if frappe.db.exists("Webshop Category", "other"):
		frappe.db.set_value("Webshop Category", "other", "is_active", 0)

	frappe.db.commit()
	frappe.clear_cache()
	print("CATEGORY TREE READY")
