# -*- coding: utf-8 -*-
"""
المحافظات والمناطق — the address picker's options.

The ERP already holds 4,383 territories under the governorates, built up from
years of real deliveries, so the shop reads that rather than keeping a second
list that would drift out of date.

Two filters make it usable at checkout:
  * only governorates the shop actually ships to — the tree also carries
    "شحن دولي" and one-off entries that would confuse a customer
  * areas that are clearly operational noise (bare numbers, plot references)
    are left out; a shopper choosing their district should not see "44656"
"""
import re

import frappe

from sync_webshop.api.utils import set_cors_headers

CACHE_KEY = "webshop_regions"
CACHE_TTL = 21600  # six hours; the tree changes rarely

SEPARATORS = ("\u060c", ",", "\n", "/")

# An entry that is mostly digits, or a bare plot reference, is warehouse
# bookkeeping rather than somewhere a person says they live.
NOISE = re.compile(r"^[\d\s/\-\.]+$")


def _shipping_governorates():
	"""The governorates the shop delivers to, taken from the shipping zones."""
	names = set()
	for zone in frappe.get_all("Webshop Shipping Zone", pluck="name"):
		raw = frappe.db.get_value("Webshop Shipping Zone", zone, "governorates") or ""
		for sep in SEPARATORS[1:]:
			raw = raw.replace(sep, SEPARATORS[0])
		names.update(p.strip() for p in raw.split(SEPARATORS[0]) if p.strip())
	return names


def _build():
	covered = _shipping_governorates()
	tops = frappe.get_all(
		"Territory", filters={"parent_territory": "All Territories"},
		fields=["name"], order_by="name")

	out = []
	for top in tops:
		if top.name not in covered:
			continue
		areas = frappe.get_all(
			"Territory", filters={"parent_territory": top.name}, pluck="name",
			order_by="name")
		clean = sorted({
			a.strip() for a in areas
			if a and a.strip() and not NOISE.match(a.strip()) and len(a.strip()) > 1
		})
		out.append({"governorate": top.name, "areas": clean})

	# Any covered governorate missing from the tree still has to be selectable,
	# otherwise a customer there simply cannot order.
	for name in sorted(covered - {o["governorate"] for o in out}):
		out.append({"governorate": name, "areas": []})

	out.sort(key=lambda o: o["governorate"])
	return out


@frappe.whitelist(allow_guest=True)
def get_regions():
	set_cors_headers()
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached is None:
		cached = _build()
		frappe.cache().set_value(CACHE_KEY, cached, expires_in_sec=CACHE_TTL)
	return cached


def clear_regions_cache(doc=None, method=None):
	frappe.cache().delete_value(CACHE_KEY)
