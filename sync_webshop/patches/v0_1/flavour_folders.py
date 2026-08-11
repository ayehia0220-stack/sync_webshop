# -*- coding: utf-8 -*-
"""
Attach photos from the flavour folders the owner sorted by hand.

One folder per flavour — بندق, كراميل, سينابون — and every product whose name
carries that flavour gets the first usable picture from it. Sorting by flavour
rather than by product was the right call: the shop sells the same coffee in
six pack sizes, and photographing each one separately would have been wasted
work.

The largest file in a folder is preferred, on the assumption it is the least
compressed. A product that already has a working image is left alone.
"""
import os
import re
import shutil

import frappe

SRC = "/home/webshop/product-images/flavours"
BASE = "/home/frappe/frappe-bench-15/sites/erp1.dpono.com/public"
EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Folder name → the spellings that appear in product names.
ALIASES = {
	"ساده": ["سادة", "ساده"],
	"فانليا": ["فانيليا", "فانليا", "فانيلا"],
	"فروله": ["فراولة", "فروله", "فراوله"],
	"مانجه": ["مانجا", "مانجه", "مانجو"],
	"شيشه تفاح": ["شيشة تفاح", "شيشه تفاح", "تفاح"],
	"شيكولاته": ["شيكولاتة", "شيكولاته", "شوكولاتة"],
	"فواكه مجففه": ["فواكه مجففة", "فواكه مجففه", "مجفف"],
	"علبه ساشيت 15 ظرف": ["ساشيت", "15 ظرف"],
	"بندق قطع": ["بندق قطع"],
}

# Folders that are not a product flavour.
SKIP = {"عروض"}


def norm(text):
	t = str(text or "").lower()
	t = re.sub(r"[إأآا]", "ا", t)
	t = re.sub(r"[ىي]", "ي", t)
	t = t.replace("ة", "ه").replace("ـ", "")
	return re.sub(r"\s+", " ", t).strip()


def best_photo(folder):
	files = [f for f in os.listdir(folder)
	         if f.lower().endswith(EXTS) and os.path.isfile(os.path.join(folder, f))]
	if not files:
		return None
	# Biggest file, as a rough stand-in for best quality.
	return max(files, key=lambda f: os.path.getsize(os.path.join(folder, f)))


def execute():
	if not os.path.isdir(SRC):
		print("لم يتم رفع المجلدات بعد: " + SRC)
		return

	price_list = frappe.get_single("Webshop API Settings").default_price_list
	items = frappe.db.sql(
		"""
		SELECT i.name, i.item_name, i.image
		FROM `tabItem` i
		JOIN `tabItem Price` p ON p.item_code = i.name AND p.price_list = %s AND p.selling = 1
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		WHERE i.disabled = 0 GROUP BY i.name
		""",
		price_list, as_dict=True)

	needs = [i for i in items
	         if not i.image or not os.path.exists(BASE + (i.image or ""))]
	print("منتجات محتاجة صورة: %d من %d" % (len(needs), len(items)))

	# Longest flavour first, so "بندق قطع" wins over plain "بندق".
	folders = sorted(
		(d for d in os.listdir(SRC)
		 if os.path.isdir(os.path.join(SRC, d)) and d not in SKIP),
		key=lambda d: -max(len(a) for a in ALIASES.get(d, [d])))

	cache, attached, missed = {}, [], []

	for item in needs:
		haystack = norm(item.item_name)
		hit = None
		for folder in folders:
			if any(norm(a) in haystack for a in ALIASES.get(folder, [folder])):
				hit = folder
				break
		if not hit:
			missed.append(item.item_name[:46])
			continue

		if hit not in cache:
			photo = best_photo(os.path.join(SRC, hit))
			if not photo:
				missed.append(item.item_name[:46])
				continue
			safe = "fl-" + re.sub(r"[^\w.\-]", "-", hit) + os.path.splitext(photo)[1].lower()
			target = os.path.join(BASE, "files", safe)
			shutil.copyfile(os.path.join(SRC, hit, photo), target)
			if not frappe.db.exists("File", {"file_name": safe}):
				frappe.get_doc({
					"doctype": "File", "file_name": safe, "file_url": "/files/" + safe,
					"is_private": 0, "file_size": os.path.getsize(target),
				}).insert(ignore_permissions=True)
			cache[hit] = "/files/" + safe

		frappe.db.set_value("Item", item.name, "image", cache[hit], update_modified=False)
		attached.append((item.item_name[:40], hit))

	frappe.db.commit()
	frappe.clear_cache()

	print("اترّبطت: %d   لسه من غير صورة: %d" % (len(attached), len(missed)))
	for name, folder in attached[:10]:
		print("   %-42s ← %s" % (name, folder))
	if missed:
		print("   بدون:", " · ".join(missed[:6]))
