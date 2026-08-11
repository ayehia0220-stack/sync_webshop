# -*- coding: utf-8 -*-
"""
Shop categories, separate from the ERP's item groups.

The Item Group tree is an accounting and stock structure — it carries the GPS
business, packaging tiers and internal grades, none of which a customer should
ever see. So the storefront gets its own list: قهوة, شاي, فواكه مجففة, توابل.
The owner edits it in the Desk, in Arabic, with a picture per category.

A product lands in a category one of two ways:
  1. The 'فئة الموقع' field on the Item itself — always wins.
  2. A rule on the category: an item group to pull in, or a word to look for in
     the product name.

Rules mean a new product usually files itself. The field is there for the ones
that don't.
"""
import frappe

CATS = [
	{"n": "قهوة", "e": "Coffee", "s": "coffee", "o": 10, "icon": "☕",
	 "kw": ["قهوة", "قهوه", "بن", "اسبريسو", "إسبريسو", "تركي", "نسكافيه", "لاتيه", "كابتشينو"]},
	{"n": "شاي", "e": "Tea", "s": "tea", "o": 20, "icon": "🍵",
	 "kw": ["شاي", "شاى", "أعشاب", "اعشاب", "نعناع", "كركديه", "ينسون", "بابونج"]},
	{"n": "فواكه مجففة", "e": "Dried Fruit", "s": "dried-fruit", "o": 30, "icon": "🥭",
	 "kw": ["مجفف", "مجففة", "مجففه", "تين", "مشمش", "زبيب", "بلح", "تمر", "قراصيا"]},
	{"n": "توابل", "e": "Spices", "s": "spices", "o": 40, "icon": "🌿",
	 "kw": ["توابل", "بهارات", "قرفة", "قرفه", "زنجبيل", "هيل", "حبهان", "كمون", "كركم", "فلفل"]},
	{"n": "مكسرات", "e": "Nuts", "s": "nuts", "o": 50, "icon": "🥜",
	 "kw": ["مكسرات", "لوز", "كاجو", "بندق", "فستق", "عين جمل", "سوداني"]},
]


def field(fieldname, label, fieldtype, idx, **kw):
	d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "idx": idx}
	d.update(kw)
	return d


def make_doctype(name, module, fields, istable=0, title_field=None, autoname=None):
	if frappe.db.exists("DocType", name):
		print("  exists: " + name)
		return
	doc = frappe.get_doc({
		"doctype": "DocType", "name": name, "module": module,
		"custom": 0, "istable": istable, "editable_grid": 1 if istable else 0,
		"autoname": autoname, "title_field": title_field,
		"track_changes": 0, "fields": fields,
		"permissions": [] if istable else [{
			"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1,
		}, {"role": "All", "read": 1}],
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	print("  created: " + name)


def execute():
	frappe.conf["developer_mode"] = 1
	frappe.flags.in_migrate = True
	try:
		make_doctype("Webshop Category Rule", "Sync Webshop", [
			field("item_group", "مجموعة أصناف من الـ ERP", "Link", 1, options="Item Group",
			      in_list_view=1, columns=4,
			      description="كل المنتجات اللي في المجموعة دي تدخل الفئة."),
			field("keyword", "أو كلمة في اسم المنتج", "Data", 2, in_list_view=1, columns=4,
			      description="مثال: بندق — أي منتج اسمه فيه الكلمة دي يدخل الفئة."),
		], istable=1)

		make_doctype("Webshop Category", "Sync Webshop", [
			field("category_name", "اسم الفئة (عربي)", "Data", 1, reqd=1, in_list_view=1),
			field("category_name_en", "Category name (English)", "Data", 2, in_list_view=1),
			field("slug", "الرابط (إنجليزي، بدون مسافات)", "Data", 3, reqd=1, unique=1,
			      description="بيظهر في العنوان: shop.dpono.com/category/coffee"),
			field("cb1", "", "Column Break", 4),
			field("is_active", "ظاهرة في الموقع", "Check", 5, default="1"),
			field("sort_order", "الترتيب", "Int", 6, default="10", in_list_view=1,
			      description="الرقم الأصغر بيظهر الأول."),
			field("icon", "أيقونة (إيموجي)", "Data", 7,
			      description="بتظهر لو مفيش صورة. مثال: ☕"),
			field("sb_img", "الصورة", "Section Break", 8),
			field("image", "صورة الفئة", "Attach Image", 9),
			field("description_ar", "وصف قصير (عربي)", "Small Text", 10),
			field("sb_rules", "قواعد ضم المنتجات", "Section Break", 11,
			      description="المنتجات بتدخل الفئة تلقائيًا حسب القواعد دي. "
			                  "ولو عايز تحط منتج بإيدك، افتح المنتج واختار 'فئة الموقع'."),
			field("rules", "القواعد", "Table", 12, options="Webshop Category Rule"),
		], title_field="category_name", autoname="field:slug")
	finally:
		frappe.conf["developer_mode"] = 0
		frappe.flags.in_migrate = False

	# --- a place to pin a single product by hand ----------------------------
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({"Item": [{
		"fieldname": "webshop_category",
		"label": "فئة الموقع",
		"fieldtype": "Link",
		"options": "Webshop Category",
		"insert_after": "item_group",
		"description": "سيبها فاضية عشان تتحدد تلقائيًا من قواعد الفئة.",
	}]}, ignore_validate=True)

	# --- seed the five so there's something to look at ----------------------
	for c in CATS:
		if frappe.db.exists("Webshop Category", c["s"]):
			continue
		doc = frappe.get_doc({
			"doctype": "Webshop Category", "category_name": c["n"],
			"category_name_en": c["e"], "slug": c["s"], "sort_order": c["o"],
			"icon": c["icon"], "is_active": 1,
			"rules": [{"keyword": k} for k in c["kw"]],
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		print("  seeded: " + c["n"])

	frappe.db.commit()
	frappe.clear_cache()
	print("CATEGORIES READY")
