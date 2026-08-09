# -*- coding: utf-8 -*-
"""
Move the storefront's wording, layout numbers and design tokens out of the code
and into ERPNext, so the shop can be reworded and restyled without a developer.

Naming matters here: every label field is `label_<key>_ar` / `label_<key>_en`.
The API collects them by that pattern, so adding a new label later is one custom
field and no code change at all.

Leave any field empty and the built-in wording is used, which is why this is
safe to run on a live store.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# (key, Arabic default, English default, where it appears)
LABELS = [
	# الصفحة الرئيسية
	("home_categories_title", "تسوّق حسب النوع", "Shop by type", "عنوان قسم الفئات"),
	("home_new_title", "وصل حديثًا", "New arrivals", "عنوان قسم المنتجات"),
	("home_view_all", "شوف الكل ←", "View all →", "رابط عرض كل المنتجات"),
	("home_shop_now", "تسوّق دلوقتي", "Shop now", "زر الهيرو الأساسي"),
	("home_track_cta", "تتبّع طلبك", "Track your order", "زر الهيرو الثانوي"),
	("home_eyebrow", "بن مختص", "Specialty coffee", "السطر الصغير فوق عنوان الهيرو"),
	# قائمة المنتجات
	("products_all", "كل المنتجات", "All products", "عنوان صفحة كل المنتجات"),
	("products_sort", "ترتيب حسب", "Sort by", "تسمية قائمة الترتيب"),
	("products_categories", "الفئات", "Categories", "عنوان الفئات في الشريط الجانبي"),
	("products_price", "السعر", "Price", "عنوان فلتر السعر"),
	("products_empty", "مفيش منتجات في الفئة دي.", "No products in this category.", "رسالة القائمة الفارغة"),
	# صفحة المنتج
	("product_add", "أضف إلى السلة", "Add to cart", "زر الشراء الكبير"),
	("product_add_short", "أضف", "Add", "زر الشراء في بطاقة المنتج"),
	("product_in_stock", "✓ متوفر", "✓ In stock", "حالة التوفّر"),
	("product_out_stock", "غير متوفر", "Out of stock", "حالة النفاد"),
	("product_delivery", "التوصيل المتوقع", "Estimated delivery", "بادئة موعد التوصيل"),
	("product_recent", "شوفته قبل كده", "Recently viewed", "عنوان قسم آخر ما شوهد"),
	# السلة والدفع
	("checkout_title", "إتمام الطلب", "Checkout", "عنوان صفحة الدفع"),
	("checkout_submit", "أكّد الطلب", "Place order", "زر تأكيد الطلب"),
	("checkout_coupon", "عندك كوبون خصم؟", "Have a coupon?", "دعوة إدخال الكوبون"),
	("checkout_consent", "أوافق على شروط البيع وسياسة الخصوصية.",
	 "I agree to the terms of sale and privacy policy.", "نص الموافقة"),
	("checkout_success", "تم استلام طلبك", "Order received", "عنوان صفحة النجاح"),
	("checkout_success_hint", "احتفظ برقم الطلب — هتحتاجه علشان تتابع الشحنة.",
	 "Keep the order number — you will need it to track your delivery.", "ملاحظة بعد الطلب"),
	# التتبّع والحساب
	("track_title", "تتبّع الطلب", "Track order", "عنوان صفحة التتبّع"),
	("orders_title", "طلباتي", "My orders", "عنوان صفحة الطلبات"),
	# الكوكيز
	("cookie_text", "بنستخدم كوكيز عشان نفهم إزاي بتستخدم الموقع ونحسّنه. تقدر ترفض عادي.",
	 "We use cookies to understand how the store is used. You can decline.", "نص شريط الكوكيز"),
]

DISPLAY_NUMBERS = [
	("products_per_page", "Products per Page", 20, "عدد المنتجات في صفحة القائمة"),
	("home_products_count", "Products on Home Page", 8, "عدد المنتجات في قسم «وصل حديثًا»"),
	("home_categories_count", "Categories on Home Page", 6, "عدد الفئات على الرئيسية"),
	("related_products_count", "Related Products", 4, "عدد المنتجات المشابهة في صفحة المنتج"),
]

DESIGN_TOKENS = [
	("card_radius", "Card Corner Radius (px)", "Int", 15, "استدارة حواف البطاقات"),
	("card_border_color", "Card Border Colour", "Color", "#ECECEC", "لون حدود البطاقات"),
	("heading_color", "Heading Colour", "Color", "#253D4E", "لون العناوين"),
	("muted_text_color", "Muted Text Colour", "Color", "#7E7E7E", "لون النص الثانوي"),
	("tint_color_1", "Category Tint 1", "Color", "#DEF9EC", "خلفية بطاقة الفئة — لون 1"),
	("tint_color_2", "Category Tint 2", "Color", "#FEEFEA", "خلفية بطاقة الفئة — لون 2"),
	("tint_color_3", "Category Tint 3", "Color", "#F2FCE4", "خلفية بطاقة الفئة — لون 3"),
	("tint_color_4", "Category Tint 4", "Color", "#FFF3EB", "خلفية بطاقة الفئة — لون 4"),
	("tint_color_5", "Category Tint 5", "Color", "#F2F6FF", "خلفية بطاقة الفئة — لون 5"),
	("tint_color_6", "Category Tint 6", "Color", "#FFF3FF", "خلفية بطاقة الفئة — لون 6"),
]


def _label_fields():
	fields = [
		{
			"fieldname": "labels_section",
			"label": "نصوص الموقع — Storefront Wording",
			"fieldtype": "Section Break",
			"insert_after": "footer_text_en",
			"collapsible": 1,
			"description": "سيب أي خانة فاضية وهيظهر النص الافتراضي.",
		}
	]
	previous = "labels_section"
	for key, ar, en, hint in LABELS:
		fields.append(
			{
				"fieldname": f"label_{key}_ar",
				"label": f"{hint} (عربي)",
				"fieldtype": "Data",
				"insert_after": previous,
				"default": ar,
			}
		)
		fields.append(
			{
				"fieldname": f"label_{key}_en",
				"label": f"{hint} (English)",
				"fieldtype": "Data",
				"insert_after": f"label_{key}_ar",
				"default": en,
			}
		)
		previous = f"label_{key}_en"
	return fields


def _number_fields():
	fields = [
		{
			"fieldname": "display_counts_section",
			"label": "أعداد العرض — How Many to Show",
			"fieldtype": "Section Break",
			"insert_after": "related_products_title_ar",
			"collapsible": 0,
		}
	]
	previous = "display_counts_section"
	for fieldname, label, default, hint in DISPLAY_NUMBERS:
		fields.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": "Int",
				"default": str(default),
				"insert_after": previous,
				"description": hint,
			}
		)
		previous = fieldname
	return fields


def _token_fields():
	fields = [
		{
			"fieldname": "card_design_section",
			"label": "تصميم البطاقات — Card Design",
			"fieldtype": "Section Break",
			"insert_after": "layout_style",
			"collapsible": 1,
		}
	]
	previous = "card_design_section"
	for fieldname, label, fieldtype, default, hint in DESIGN_TOKENS:
		fields.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": fieldtype,
				"default": str(default),
				"insert_after": previous,
				"description": hint,
			}
		)
		previous = fieldname
	return fields


def execute():
	create_custom_fields(
		{
			"Webshop Content Settings": _label_fields(),
			"Webshop Product Settings": _number_fields(),
			"Webshop Theme Settings": _token_fields(),
		},
		ignore_validate=True,
	)

	# Seed the defaults so the settings screens open with real values rather
	# than blanks, which makes it obvious what each one controls.
	content = frappe.get_single("Webshop Content Settings")
	changed = False
	for key, ar, en, _hint in LABELS:
		for suffix, value in (("ar", ar), ("en", en)):
			field = f"label_{key}_{suffix}"
			if hasattr(content, field) and not content.get(field):
				content.set(field, value)
				changed = True
	if changed:
		content.flags.ignore_permissions = True
		content.flags.ignore_mandatory = True
		content.save()

	product = frappe.get_single("Webshop Product Settings")
	changed = False
	for fieldname, _label, default, _hint in DISPLAY_NUMBERS:
		if hasattr(product, fieldname) and not product.get(fieldname):
			product.set(fieldname, default)
			changed = True
	if changed:
		product.flags.ignore_permissions = True
		product.flags.ignore_mandatory = True
		product.save()

	theme = frappe.get_single("Webshop Theme Settings")
	changed = False
	for fieldname, _label, _ft, default, _hint in DESIGN_TOKENS:
		if hasattr(theme, fieldname) and not theme.get(fieldname):
			theme.set(fieldname, default)
			changed = True
	if changed:
		theme.flags.ignore_permissions = True
		theme.flags.ignore_mandatory = True
		theme.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("LABELS=%d NUMBERS=%d TOKENS=%d" % (len(LABELS), len(DISPLAY_NUMBERS), len(DESIGN_TOKENS)))
