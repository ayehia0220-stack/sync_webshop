# -*- coding: utf-8 -*-
"""
Keep the old product addresses alive.

dpono.com sold at /product/<slug>/. Those pages have inbound links and search
rankings, and the slug is the Arabic product name — which is not what the ERP
calls the same coffee ("قهوة بندق" there, "أكياس بن منتج تام-بندق-10" here).

So each WooCommerce slug is matched to an item by flavour, the same way the
product photos were, and the pairing is stored on the item where the owner can
see and correct it. A slug nobody can place sends the visitor to the shop rather
than to a dead end — better than losing them.
"""
import base64
import re
import subprocess
import unicodedata
from urllib.parse import unquote

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

NOISE = {
	"بن", "قهوه", "قهوة", "منتج", "تام", "اكياس", "أكياس", "كيس", "عبوه", "عبوة",
	"عبوات", "جم", "كجم", "جرام", "كيلو", "ايزي", "أوبن", "اوبن", "جردل", "جرادل",
	"كرتونه", "كرتونة", "كراتين", "علبه", "علبة", "x", "y", "z", "سادة", "ساده",
}


def norm(text):
	t = str(text or "").lower()
	t = re.sub(r"[إأآا]", "ا", t)
	t = re.sub(r"[ىي]", "ي", t)
	t = t.replace("ة", "ه").replace("ـ", "")
	t = re.sub(r"[^\w\s؀-ۿ]", " ", t)
	return re.sub(r"\s+", " ", t).strip()


def flavour(text):
	words = [w for w in norm(text).split() if w and not w.isdigit()]
	drop = {norm(n) for n in NOISE}
	return " ".join(w for w in words if w not in drop).strip()


def wp(query):
	out = subprocess.run(
		["docker", "exec", "-e", "Q=" + query, "wp_db", "sh", "-c",
		 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 '
		 '-N --raw -e "$Q" wordpress'],
		capture_output=True, text=True)
	return out.stdout.strip()


def execute():
	create_custom_fields({"Item": [{
		"fieldname": "legacy_slug",
		"label": "الرابط القديم على dpono.com",
		"fieldtype": "Data",
		"insert_after": "webshop_category",
		"description": "dpono.com/product/<الرابط>. اتحدد تلقائيًا — عدّله لو غلط.",
	}]}, ignore_validate=True)

	rows = wp("SELECT CONCAT(REPLACE(TO_BASE64(post_name), CHAR(10), ''), '|', "
	          "REPLACE(TO_BASE64(post_title), CHAR(10), '')) FROM wp_posts "
	          "WHERE post_type='product' AND post_status='publish';")

	woo = []
	for line in rows.split("\n"):
		if "|" not in line:
			continue
		b_slug, b_title = line.strip().split("|", 1)
		try:
			slug = unicodedata.normalize(
				"NFC", unquote(base64.b64decode(b_slug).decode("utf-8"))).strip()
			title = base64.b64decode(b_title).decode("utf-8").strip()
		except Exception:
			continue
		key = flavour(title)
		if slug and key:
			woo.append({"slug": slug, "title": title, "key": key})

	# Longest flavour first, so "بندق قطع" is preferred over plain "بندق".
	woo.sort(key=lambda w: -len(w["key"]))

	# Only items a shopper can actually reach: priced, and in a website group.
	# Matching against raw materials would redirect an old link to a page that
	# does not sell anything.
	price_list = frappe.get_single("Webshop API Settings").default_price_list
	items = frappe.db.sql(
		"""
		SELECT i.name, i.item_name
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.price_list = %s AND p.selling = 1
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE i.disabled = 0
		GROUP BY i.name
		""",
		price_list,
		as_dict=True,
	)
	taken, matched, orphan = set(), 0, []

	for w in woo:
		hit = None
		for item in items:
			if item.name in taken:
				continue
			if re.search(r"(^|\s)" + re.escape(w["key"]) + r"(\s|$)", flavour(item.item_name)):
				hit = item
				break
		if not hit:
			orphan.append(w["slug"])
			continue
		if not frappe.db.get_value("Item", hit.name, "legacy_slug"):
			frappe.db.set_value("Item", hit.name, "legacy_slug", w["slug"],
			                    update_modified=False)
			taken.add(hit.name)
			matched += 1

	frappe.db.commit()
	frappe.clear_cache()
	print("MATCHED=%d ORPHAN=%d of %d" % (matched, len(orphan), len(woo)))
	for s in orphan[:10]:
		print("  ? " + s)
