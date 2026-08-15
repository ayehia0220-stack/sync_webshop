# -*- coding: utf-8 -*-
"""
A drop folder for product photographs.

Name a file after the product and it gets attached — no clicking through
ERPNext for sixty items. Run it again whenever new photos are added; files
already imported are moved aside rather than processed twice.

Matching is exact-ish on purpose: the filename has to identify one product, or
the file is left alone and reported. A photo on the wrong product is worse than
no photo.
"""
import json
import os
import re
import shutil

import frappe

INBOX = "/home/webshop/product-images"
DONE = INBOX + "/_imported"
FAILED = INBOX + "/_unmatched"
BASE = "/home/frappe/frappe-bench-15/sites/erp1.dpono.com/public"
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def norm(text):
	t = str(text or "").lower()
	t = re.sub(r"[إأآا]", "ا", t)
	t = re.sub(r"[ىي]", "ي", t)
	t = t.replace("ة", "ه").replace("ـ", "")
	t = re.sub(r"[^\w\s؀-ۿ]", " ", t)
	return re.sub(r"\s+", " ", t).strip()


def execute():
	for folder in (INBOX, DONE, FAILED):
		os.makedirs(folder, exist_ok=True)

	# Every name a photo might reasonably be filed under: the factory code, the
	# ERP name, the shop title, and the URL slug. Naming a file after what the
	# customer sees should work as well as naming it after the item code.
	items = frappe.get_all(
		"Item", filters={"disabled": 0},
		fields=["name", "item_name", "website_title", "web_slug"])
	by_name = {}
	for item in items:
		for label in (item.item_name, item.name, item.website_title, item.web_slug):
			if not label:
				continue
			by_name.setdefault(norm(label), []).append(item.name)
			# Shop titles carry a "| brand 125 جم" tail that a filename usually drops.
			head = str(label).split("|")[0]
			if head != label:
				by_name.setdefault(norm(head), []).append(item.name)

	imported, unmatched, ambiguous = [], [], []

	for filename in sorted(os.listdir(INBOX)):
		path = os.path.join(INBOX, filename)
		if not os.path.isfile(path) or not filename.lower().endswith(EXTS):
			continue

		stem = norm(os.path.splitext(filename)[0])
		candidates = by_name.get(stem)

		if not candidates:
			# Allow the filename to be a clear prefix of exactly one product.
			hits = [n for key, names in by_name.items() if key.startswith(stem) and len(stem) >= 4
			        for n in names]
			candidates = list(dict.fromkeys(hits))

		if not candidates:
			unmatched.append(filename)
			shutil.move(path, os.path.join(FAILED, filename))
			continue
		if len(set(candidates)) > 1:
			ambiguous.append({"file": filename, "matches": len(set(candidates))})
			shutil.move(path, os.path.join(FAILED, filename))
			continue

		item_code = candidates[0]
		safe = re.sub(r"\s+", "-", filename)
		target = os.path.join(BASE, "files", safe)
		shutil.copyfile(path, target)

		# Frappe renames the File when the name is already taken, so the record
		# can end up pointing somewhere other than the path written above. Use
		# whatever URL it settled on — otherwise the item carries two copies of
		# the same photo and the gallery shows it twice.
		existing = frappe.db.get_value(
			"File", {"file_name": safe, "attached_to_name": item_code}, "file_url")
		if existing:
			file_url = existing
		else:
			doc = frappe.get_doc({
				"doctype": "File", "file_name": safe, "file_url": "/files/" + safe,
				"is_private": 0, "file_size": os.path.getsize(target),
				"attached_to_doctype": "Item", "attached_to_name": item_code,
			}).insert(ignore_permissions=True)
			file_url = doc.file_url
			if file_url != "/files/" + safe and os.path.exists(target):
				os.remove(target)

		frappe.db.set_value("Item", item_code, "image", file_url, update_modified=False)
		imported.append({"file": filename, "item": item_code})
		shutil.move(path, os.path.join(DONE, filename))

	frappe.db.commit()
	frappe.clear_cache()

	print("INBOX=" + json.dumps({
		"imported": len(imported), "unmatched": len(unmatched), "ambiguous": len(ambiguous),
		"sample": imported[:5], "unmatched_sample": unmatched[:5],
	}, ensure_ascii=False))
