# -*- coding: utf-8 -*-
"""
Card sizes as settings.

How big the product and category cards are is a look-and-feel decision, so it
belongs with the colours in Theme Settings rather than in a stylesheet. The
numbers set the minimum card width; the grid still fills the row, so a smaller
number simply means more cards per row.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop Theme Settings": [
		{
			"fieldname": "sec_card_size",
			"label": "أحجام البطاقات — Card Sizes",
			"fieldtype": "Section Break",
			"insert_after": "tint_color_6",
			"description": "الرقم هو أقل عرض للبطاقة. رقم أصغر = منتجات أكتر في الصف.",
		},
		{
			"fieldname": "product_card_width",
			"label": "عرض بطاقة المنتج (px)",
			"fieldtype": "Int",
			"default": "210",
			"insert_after": "sec_card_size",
			"description": "الافتراضي 210. جرّب 170 لبطاقات أصغر أو 260 لأكبر.",
		},
		{
			"fieldname": "category_card_width",
			"label": "عرض بطاقة الفئة (px)",
			"fieldtype": "Int",
			"default": "150",
			"insert_after": "product_card_width",
		},
		{"fieldname": "card_size_cb", "fieldtype": "Column Break", "insert_after": "category_card_width"},
		{
			"fieldname": "product_card_width_mobile",
			"label": "بطاقات المنتج في الصف — موبايل",
			"fieldtype": "Int",
			"default": "2",
			"insert_after": "card_size_cb",
			"description": "1 أو 2. الافتراضي 2.",
		},
		{
			"fieldname": "category_card_width_mobile",
			"label": "بطاقات الفئة في الصف — موبايل",
			"fieldtype": "Int",
			"default": "3",
			"insert_after": "product_card_width_mobile",
			"description": "من 2 لـ 4. الافتراضي 3.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	theme = frappe.get_single("Webshop Theme Settings")
	defaults = {
		"product_card_width": 210,
		"category_card_width": 150,
		"product_card_width_mobile": 2,
		"category_card_width_mobile": 3,
	}
	changed = False
	for field, value in defaults.items():
		if hasattr(theme, field) and not theme.get(field):
			theme.set(field, value)
			changed = True
	if changed:
		theme.flags.ignore_permissions = True
		theme.flags.ignore_mandatory = True
		theme.save()

	# --- send them to the storefront -----------------------------------------
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/theme.py"
	s = io.open(p, encoding="utf-8").read()
	if "product_card_width" not in s:
		s = s.replace(
			'\t\t\t"tints": [',
			'\t\t\t"product_width": settings.get("product_card_width") or 210,\n'
			'\t\t\t"category_width": settings.get("category_card_width") or 150,\n'
			'\t\t\t"product_cols_mobile": settings.get("product_card_width_mobile") or 2,\n'
			'\t\t\t"category_cols_mobile": settings.get("category_card_width_mobile") or 3,\n'
			'\t\t\t"tints": [',
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)

	frappe.db.commit()
	frappe.clear_cache()
	print("SIZES READY")
