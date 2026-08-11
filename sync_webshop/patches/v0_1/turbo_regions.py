# -*- coding: utf-8 -*-
"""Take the address list from Turbo, since Turbo is who has to deliver to it."""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/regions.py"

SRC = u'''# -*- coding: utf-8 -*-
"""
المحافظات والمناطق — sourced from Turbo.

The ERP's territory tree was built from years of deliveries, but Turbo is the
one who actually has to reach the address: an area it does not recognise comes
back as "Location is uncovered" after the customer has already ordered. So the
courier's own list is what the checkout offers, and each area carries how Turbo
will serve it:

  مغطاة       → delivered to the door
  نقطة تسليم  → the customer collects from a Turbo point
  غير مغطاة   → not served; hidden from the picker

Refreshed daily and on demand. If Turbo is unreachable the last good copy keeps
serving, because an empty address picker means nobody can order at all.
"""
import json

import frappe
import requests

from sync_webshop.api.utils import set_cors_headers

CACHE_KEY = "webshop_regions_v2"
CACHE_TTL = 86400
FALLBACK_KEY = "webshop_regions_fallback"
TIMEOUT = 25

COVERED = "\\u0645\\u063a\\u0637\\u0627\\u0629"          # مغطاة
PICKUP = "\\u0646\\u0642\\u0637\\u0629 \\u062a\\u0633\\u0644\\u064a\\u0645"  # نقطة تسليم

# Turbo carries these as routing buckets, not places a shopper picks.
SKIP_GOVERNORATES = {"\\u0634\\u062d\\u0646 \\u062f\\u0648\\u0644\\u064a"}  # شحن دولي


def _settings():
	return frappe.get_single("Webshop Turbo Settings")


def _base():
	return (_settings().base_url or "https://platform.turbo.info").rstrip("/")


def _get(path):
	"""Turbo sits behind Cloudflare, which rejects the default python agent."""
	res = requests.get(
		_base() + path, timeout=TIMEOUT,
		headers={"Accept": "application/json", "User-Agent": "dpono-shop/1.0"})
	res.raise_for_status()
	return res.json()


def _shipping_zone_names():
	"""Governorates the shop prices shipping for."""
	names = set()
	for zone in frappe.get_all("Webshop Shipping Zone", pluck="name"):
		raw = frappe.db.get_value("Webshop Shipping Zone", zone, "governorates") or ""
		for sep in (",", "\\n", "/"):
			raw = raw.replace(sep, "\\u060c")
		names.update(p.strip() for p in raw.split("\\u060c") if p.strip())
	return names


def _build():
	govs = _get("/external-api/get-government").get("feed") or []
	priced = _shipping_zone_names()

	out = []
	for gov in govs:
		name = (gov.get("name") or "").strip()
		if not name or name in SKIP_GOVERNORATES:
			continue
		# No shipping zone means no price, and an order we cannot quote.
		if priced and name not in priced:
			continue

		areas = []
		try:
			feed = _get("/external-api/get-area/%s" % gov.get("id")).get("feed") or []
		except Exception:
			feed = []

		for area in feed:
			label = (area.get("name") or "").strip()
			status = (area.get("status") or "").strip()
			if not label or status not in (COVERED, PICKUP):
				continue
			areas.append({
				"id": area.get("id"),
				"name": label,
				"pickup": status == PICKUP,
			})

		areas.sort(key=lambda a: a["name"])
		out.append({"id": gov.get("id"), "governorate": name, "areas": areas})

	out.sort(key=lambda g: g["governorate"])
	return out


@frappe.whitelist(allow_guest=True)
def get_regions():
	set_cors_headers()
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	try:
		data = _build()
	except Exception as exc:
		frappe.log_error(title="Turbo regions fetch failed", message=str(exc)[:500])
		data = None

	if not data:
		# Better a slightly stale list than a checkout nobody can complete.
		stale = frappe.db.get_default(FALLBACK_KEY)
		return json.loads(stale) if stale else []

	frappe.cache().set_value(CACHE_KEY, data, expires_in_sec=CACHE_TTL)
	frappe.db.set_default(FALLBACK_KEY, json.dumps(data))
	return data


@frappe.whitelist()
def refresh_regions():
	"""Pull the list again now — for the button in Turbo Settings."""
	frappe.cache().delete_value(CACHE_KEY)
	data = get_regions()
	return {
		"governorates": len(data),
		"areas": sum(len(g["areas"]) for g in data),
		"pickup_only": sum(1 for g in data for a in g["areas"] if a["pickup"]),
	}


def clear_regions_cache(doc=None, method=None):
	frappe.cache().delete_value(CACHE_KEY)


def refresh_daily():
	"""Scheduled: keep the address list in step with Turbo's coverage."""
	try:
		clear_regions_cache()
		get_regions()
	except Exception as exc:
		frappe.log_error(title="Turbo regions daily refresh", message=str(exc)[:500])
'''


def execute():
	import frappe

	io.open(P, "w", encoding="utf-8").write(SRC)

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "regions.refresh_daily" not in s and '"daily"' in s:
		s = s.replace('"daily": [', '"daily": [\n\t\t"sync_webshop.api.regions.refresh_daily",', 1)
		io.open(h, "w", encoding="utf-8").write(s)
		print("hooks: daily refresh")

	frappe.cache().delete_value("webshop_regions")
	frappe.cache().delete_value("webshop_regions_v2")
	frappe.db.commit()
	frappe.clear_cache()
	print("TURBO REGIONS READY")
