# -*- coding: utf-8 -*-
"""
Sort the shared-phone customers into merge / leave / ask.

A shared phone is not proof of a shared person. Amazon and "ali" sit on one
number because someone typed the office line on a marketplace account; طارق رجب
and اسامه عزب are two people who gave the same contact. Merging either pair
would move one person's orders onto another's ledger, and there is no undo.

So the name decides, not the number:

  merge  — the names are the same person written twice
           ("عباس صابر عباس" / "عباس صابر عباس محمد", "احمد هشام" / "احمد هشام - 1")
  ask    — the names are different people sharing a line
"""
import re

import frappe

SUFFIX = re.compile(r"\s*-\s*\d+$")


def norm_name(name):
	n = SUFFIX.sub("", str(name or "")).strip().lower()
	n = re.sub(r"[إأآا]", "ا", n)
	n = re.sub(r"[ىي]", "ي", n)
	n = n.replace("ة", "ه").replace("ـ", "")
	return re.sub(r"\s+", " ", n).strip()


def same_person(a, b):
	"""One name being the start of the other means the fuller version wins."""
	x, y = norm_name(a), norm_name(b)
	if not x or not y:
		return False
	if x == y:
		return True
	short, long_ = sorted((x, y), key=len)
	# A shared first name is not enough — "احمد" matches half the database.
	return long_.startswith(short + " ") and len(short.split()) >= 2


def activity(customer):
	so = frappe.db.count("Sales Order", {"customer": customer})
	si = frappe.db.count("Sales Invoice", {"customer": customer})
	return so, si


def execute():
	rows = frappe.db.sql(
		"""
		SELECT mobile_no, GROUP_CONCAT(name SEPARATOR '||') AS names
		FROM `tabCustomer` WHERE IFNULL(mobile_no,'') != ''
		GROUP BY mobile_no HAVING COUNT(*) > 1
		""",
		as_dict=True)

	mergeable, ask = [], []
	for row in rows:
		names = row.names.split("||")
		if len(names) != 2:
			ask.append((row.mobile_no, names))
			continue
		a, b = names
		if same_person(a, b):
			# Keep whichever carries more history.
			ranked = sorted(names, key=lambda c: sum(activity(c)), reverse=True)
			mergeable.append((row.mobile_no, ranked[0], ranked[1]))
		else:
			ask.append((row.mobile_no, names))

	print("=== يتدمجوا — نفس الاسم (%d) ===" % len(mergeable))
	for ph, keep, drop in mergeable:
		ka, kb = activity(keep)
		da, db_ = activity(drop)
		print("  %s  يفضل %-28s (%d/%d)  ←  %-24s (%d/%d)"
		      % (ph, keep[:28], ka, kb, drop[:24], da, db_))

	print()
	print("=== محتاجة قرارك — أسماء مختلفة (%d) ===" % len(ask))
	for ph, names in ask:
		parts = []
		for c in names:
			a, b = activity(c)
			parts.append("%s (%d/%d)" % (c[:22], a, b))
		print("  %s  %s" % (ph, "  ×  ".join(parts)))

	return {"mergeable": mergeable, "ask": ask}
