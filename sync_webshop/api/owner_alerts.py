# -*- coding: utf-8 -*-
"""
إشعار المالك على الواتساب لما طلب جديد يتسجل من الموقع.

بيمشي على Evolution مباشرة (نفس الرقم اللي بيرد على العملاء) بدل ما يعدّي
على n8n — خطوة أقل تقع. أي فشل في الإرسال بيتسجّل ومبيرجعش على الطلب،
لأن رسالة مش واصلة أهون من طلب مش متسجّل.
"""
import json

import frappe
import requests

TIMEOUT = 12


def _settings():
	return frappe.get_single("Webshop Content Settings")


def _normalise(phone):
	digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
	if digits.startswith("00"):
		digits = digits[2:]
	if digits.startswith("0") and len(digits) == 11:
		digits = "20" + digits[1:]
	elif len(digits) == 10 and digits.startswith("1"):
		digits = "20" + digits
	return digits if digits.startswith("20") and len(digits) == 12 else None


def _recipients(settings):
	raw = settings.get("owner_alert_numbers") or ""
	out = []
	for part in raw.replace("\n", ",").split(","):
		num = _normalise(part)
		if num and num not in out:
			out.append(num)
	return out


def _send(settings, number, text):
	url = (settings.get("evolution_url") or "http://localhost:8080").rstrip("/")
	instance = settings.get("evolution_instance") or "1212"
	key = settings.get_password("evolution_api_key", raise_exception=False)
	if not key:
		return False, "مفيش مفتاح Evolution في الإعدادات"
	try:
		r = requests.post(
			f"{url}/message/sendText/{instance}",
			headers={"apikey": key, "Content-Type": "application/json"},
			data=json.dumps({"number": number, "text": text}, ensure_ascii=False).encode("utf-8"),
			timeout=TIMEOUT,
		)
		ok = r.status_code < 300
		return ok, (r.text or "")[:200]
	except Exception as exc:
		return False, str(exc)[:200]


def _body(so, customer_label, payment_method=None):
	lines = [
		"🛒 *طلب جديد من الموقع*",
		"",
		f"رقم الطلب: {so.name}",
		f"العميل: {customer_label}",
	]
	phone = frappe.db.get_value("Customer", so.customer, "custom_mobile_phone")
	if phone:
		lines.append(f"الموبايل: {phone}")
	lines.append("")
	for item in so.items[:8]:
		name = frappe.db.get_value("Item", item.item_code, "website_title") or item.item_name or item.item_code
		lines.append(f"• {name} × {item.qty:g}")
	if len(so.items) > 8:
		lines.append(f"• … و{len(so.items) - 8} صنف تاني")
	lines.append("")
	total = round(float(so.grand_total or 0), 2)
	pretty = f"{total:,.0f}" if total == int(total) else f"{total:,.2f}"
	lines.append(f"الإجمالي: {pretty} جنيه")
	if payment_method:
		lines.append(f"طريقة الدفع: {payment_method}")
	lines.append("")
	lines.append(f"https://erp1.dpono.com/app/sales-order/{so.name}")
	return "\n".join(lines)


def notify_owner_new_order(sales_order, payment_method=None):
	"""بتتندَه بعد ما الطلب يتسجّل. مبترميش استثناء للنداء أبدًا."""
	try:
		settings = _settings()
		if not settings.get("owner_alert_enabled"):
			return {"sent": 0, "reason": "الإشعارات مقفولة من الإعدادات"}

		numbers = _recipients(settings)
		if not numbers:
			return {"sent": 0, "reason": "مفيش أرقام في الإعدادات"}

		so = sales_order if hasattr(sales_order, "items") else frappe.get_doc("Sales Order", sales_order)
		label = frappe.db.get_value("Customer", so.customer, "customer_name") or so.customer
		text = _body(so, label, payment_method)

		sent, errors = 0, []
		for number in numbers:
			ok, detail = _send(settings, number, text)
			if ok:
				sent += 1
			else:
				errors.append(f"{number}: {detail}")
		if errors:
			frappe.log_error("\n".join(errors), f"إشعار طلب جديد {so.name}")
		return {"sent": sent, "of": len(numbers), "errors": errors}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "notify_owner_new_order")
		return {"sent": 0, "reason": "خطأ — اتسجّل في سجل الأخطاء"}


@frappe.whitelist()
def send_test_alert():
	"""زرار تجربة: بيبعت آخر طلب على أرقام الإشعارات."""
	last = frappe.get_all("Sales Order", order_by="creation desc", limit=1, pluck="name")
	if not last:
		return {"sent": 0, "reason": "مفيش أوامر بيع"}
	return notify_owner_new_order(last[0], payment_method="(تجربة)")
