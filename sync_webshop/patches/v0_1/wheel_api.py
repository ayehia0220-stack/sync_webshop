# -*- coding: utf-8 -*-
"""The spin endpoint. Writes sync_webshop/api/wheel.py."""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/wheel.py"

SRC = u'''# -*- coding: utf-8 -*-
"""
عجلة الحظ — the draw happens here, never in the browser.

The page asks to spin and is told which slice it landed on. It cannot choose,
retry for a better result, or read the odds before committing, because the
coupon is already written to the database by the time the answer is sent.

One prize per email per cooldown. Email rather than a cookie, because a cookie
is cleared in two clicks and the shop would give the same person a discount
every visit.
"""
import random
import re
import string
from datetime import timedelta

import frappe
from frappe.utils import add_days, now_datetime

from sync_webshop.api.utils import set_cors_headers

EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[A-Za-z]{2,}$")


def _settings():
	return frappe.get_single("Webshop Wheel Settings")


def _active_prizes(settings):
	return [p for p in settings.prizes if p.is_active and (p.weight or 0) > 0]


@frappe.whitelist(allow_guest=True)
def get_wheel():
	"""
	The slices to draw, without the odds.

	Weights are deliberately left out — publishing them turns a bit of fun into
	a table a visitor can audit, and they are none of the browser's business.
	"""
	set_cors_headers()
	settings = _settings()
	if not settings.enabled:
		return {"enabled": False}

	prizes = _active_prizes(settings)
	if len(prizes) < 2:
		return {"enabled": False}

	return {
		"enabled": True,
		"title": settings.title_ar,
		"subtitle": settings.subtitle_ar,
		"segments": [
			{"label": p.label, "color": p.color or "#2E8F9C"} for p in prizes
		],
	}


def _make_code():
	body = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
	return "SPIN" + body


def _issue_coupon(prize, settings):
	"""A real Coupon Code backed by a Pricing Rule, so checkout honours it."""
	percent = int(prize.discount_percent or 0)
	if percent <= 0 and not prize.free_shipping:
		return None

	code = _make_code()
	while frappe.db.exists("Coupon Code", {"coupon_code": code}):
		code = _make_code()

	valid_days = int(settings.coupon_valid_days or 7)
	valid_upto = add_days(now_datetime().date(), valid_days)

	rule = frappe.get_doc({
		"doctype": "Pricing Rule",
		"title": "Wheel %s" % code,
		"apply_on": "Transaction",
		"price_or_product_discount": "Price",
		"rate_or_discount": "Discount Percentage",
		"discount_percentage": percent,
		"selling": 1,
		"coupon_code_based": 1,
		"applicable_for": "",
		"valid_from": now_datetime().date(),
		"valid_upto": valid_upto,
		"min_amt": float(settings.min_order_amount or 0),
	})
	rule.flags.ignore_permissions = True
	rule.flags.ignore_mandatory = True
	rule.insert()

	coupon = frappe.get_doc({
		"doctype": "Coupon Code",
		"coupon_name": "Wheel %s" % code,
		"coupon_code": code,
		"coupon_type": "Promotional",
		"pricing_rule": rule.name,
		"valid_from": now_datetime().date(),
		"valid_upto": valid_upto,
		"maximum_use": 1,
	})
	coupon.flags.ignore_permissions = True
	coupon.flags.ignore_mandatory = True
	coupon.insert()
	return code


@frappe.whitelist(allow_guest=True)
def spin(email):
	set_cors_headers()
	settings = _settings()
	if not settings.enabled:
		frappe.throw(frappe._("العجلة مقفولة دلوقتي."))

	email = (email or "").strip().lower()
	if not EMAIL_RE.match(email):
		frappe.throw(frappe._("اكتب إيميل صحيح."))

	cooldown = int(settings.cooldown_days or 30)
	since = now_datetime() - timedelta(days=cooldown)
	previous = frappe.db.get_value(
		"Webshop Wheel Spin",
		{"email": email, "spun_on": [">", since]},
		["prize_label", "coupon_code", "spun_on"],
		as_dict=True,
	)
	if previous:
		return {
			"already": True,
			"label": previous.prize_label,
			"coupon_code": previous.coupon_code,
			"message": frappe._("لفّيت قبل كده. الجايزة بتاعتك لسه هنا."),
		}

	prizes = _active_prizes(settings)
	if len(prizes) < 2:
		frappe.throw(frappe._("العجلة مش مظبوطة."))

	# The draw. random.choices weights the pick; the index it returns is the
	# slice the animation must land on.
	index = random.choices(
		range(len(prizes)), weights=[int(p.weight or 1) for p in prizes], k=1)[0]
	prize = prizes[index]

	code = _issue_coupon(prize, settings)

	frappe.get_doc({
		"doctype": "Webshop Wheel Spin",
		"email": email,
		"prize_label": prize.label,
		"coupon_code": code or "",
		"discount_percent": int(prize.discount_percent or 0),
		"spun_on": now_datetime(),
	}).insert(ignore_permissions=True)

	frappe.db.commit()

	return {
		"already": False,
		"index": index,
		"label": prize.label,
		"coupon_code": code,
		"valid_days": int(settings.coupon_valid_days or 7),
	}
'''


def execute():
	io.open(P, "w", encoding="utf-8").write(SRC)
	print("wheel.py written")
