# -*- coding: utf-8 -*-
"""
SEO titles for products, and a preview button in the Desk.

Item codes read like warehouse notes — "أكياس بن منتج تام-بندق-10" tells a
picker exactly what to grab and tells a shopper nothing. website_title already
exists on Item and the storefront prefers it, so a readable name goes there and
the code stays untouched for the warehouse.

The names are built to match how people search: what it is, its flavour, its
weight, then the brand.
"""
import re

import frappe

FLAVOURS = {
	"بندق قطع": "بندق مقطّع", "بندق": "بندق", "لوز": "لوز", "كراميل": "كراميل",
	"فانيليا": "فانيليا", "فانليا": "فانيليا", "سينابون": "سينابون",
	"شيشة تفاح": "تفاح", "شيشه تفاح": "تفاح", "شيكولاته": "شيكولاتة",
	"شيكولاتة": "شيكولاتة", "فراوله": "فراولة", "فراولة": "فراولة",
	"مانجو": "مانجو", "مانجا": "مانجو", "موز": "موز", "كريز": "كريز",
	"لوتس": "لوتس", "برتقال": "برتقال", "جوز الهند": "جوز الهند",
}
ROASTS = {"فاتح": "تحميص فاتح", "غامق": "تحميص غامق", "وسط": "تحميص وسط"}


def _weight(name):
	m = re.search(r"(\d{2,4})\s*(?:جم|جرام|g)\b", name)
	if m:
		return m.group(1) + " جم"
	if re.search(r"\bكيلو\b", name):
		return "1 كجم"
	m = re.search(r"-\s*(\d{2,4})\s*(?:$|[-\s])", name)
	return (m.group(1) + " جم") if m else ""


def seo_title(name):
	flavour = next((v for k, v in FLAVOURS.items() if k in name), None)
	roast = next((v for k, v in ROASTS.items() if k in name), None)
	weight = _weight(name)
	spiced = "محوج" in name
	plain = ("سادة" in name or "ساده" in name) and not flavour

	if flavour:
		head = "قهوة بنكهة %s" % flavour
	elif spiced:
		head = "بن محوّج بالحبهان"
	elif "اسبريسو" in name or "إسبريسو" in name:
		head = "بن إسبريسو"
	elif "تركي" in name:
		head = "بن تركي"
	elif plain:
		head = "بن سادة"
	else:
		head = "بن محمّص"

	parts = [head]
	if roast and not flavour:
		parts.append(roast)
	if weight:
		parts.append(weight)
	parts.append("دبونو")
	return " — ".join(parts)


def execute():
	price_list = frappe.get_single("Webshop API Settings").default_price_list
	items = frappe.db.sql(
		"""
		SELECT i.name, i.item_name, i.website_title
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.price_list = %s AND p.selling = 1
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE i.disabled = 0 GROUP BY i.name
		""",
		price_list, as_dict=True)

	written, kept = 0, 0
	for item in items:
		# Never overwrite a title the owner typed themselves.
		if (item.website_title or "").strip():
			kept += 1
			continue
		frappe.db.set_value("Item", item.name, "website_title",
		                    seo_title(item.item_name), update_modified=False)
		written += 1

	frappe.db.commit()
	frappe.clear_cache()
	print("أسماء اتكتبت: %d   محفوظة زي ما هي: %d" % (written, kept))
	for item in items[:8]:
		print("   %-44s → %s" % (item.item_name[:44], seo_title(item.item_name)))
