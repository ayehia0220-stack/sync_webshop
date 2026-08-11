# -*- coding: utf-8 -*-
"""
Split the footer's one long list into columns that read at a glance.

Eight links stacked in a single column is a wall. Navigation links and policy
pages are different things to a reader, so they get their own headings — the
owner can still rename, reorder or move any of them in the Desk afterwards.
"""
import frappe

# Anything whose URL matches one of these belongs with the policies.
POLICY = ("/page/", "about", "shipping", "return", "privacy", "terms", "faq")


def execute():
	cols = frappe.get_all("Webshop Footer Column", filters={"enabled": 1},
	                      fields=["name", "title_ar"], order_by="sort_order asc")
	source = None
	for c in cols:
		doc = frappe.get_doc("Webshop Footer Column", c.name)
		if len(doc.links) >= 6:
			source = doc
			break
	if not source:
		print("nothing to split")
		return

	if frappe.db.exists("Webshop Footer Column", {"title_en": "Information"}):
		print("already split")
		return

	stay, move = [], []
	for link in source.links:
		url = (link.link_url or "").lower()
		(move if any(k in url for k in POLICY) else stay).append(link)

	if not move:
		print("no policy links found")
		return

	new = frappe.get_doc({
		"doctype": "Webshop Footer Column",
		"title_ar": "معلومات تهمك",
		"title_en": "Information",
		"enabled": 1,
		"sort_order": (source.sort_order or 10) + 1,
		"links": [{
			"label_en": l.label_en, "label_ar": l.label_ar,
			"link_url": l.link_url, "is_external": l.is_external,
		} for l in move],
	})
	new.flags.ignore_permissions = True
	new.insert()

	source.set("links", [{
		"label_en": l.label_en, "label_ar": l.label_ar,
		"link_url": l.link_url, "is_external": l.is_external,
	} for l in stay])
	source.flags.ignore_permissions = True
	source.save()

	# Push the social column to the end so the new one sits beside its siblings.
	for c in cols:
		if c.name != source.name:
			frappe.db.set_value("Webshop Footer Column", c.name, "sort_order",
			                    (source.sort_order or 10) + 5)

	frappe.db.commit()
	frappe.clear_cache()
	print("SPLIT kept=%d moved=%d" % (len(stay), len(move)))
