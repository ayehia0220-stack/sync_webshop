# -*- coding: utf-8 -*-
"""
إشعارات واتساب — order messages over the WhatsApp Cloud API.

Everything the integration needs lives in the Desk: the token, the phone id, and
the template names. Meta requires a pre-approved template for any message the
shop starts, so the template *names* are settings rather than the message text —
the wording itself lives in Meta's console and cannot be changed from here.

Sends are logged with whatever Meta answered. A notification channel that fails
silently is worse than none, because the shop believes the customer was told.
"""
import json

import frappe
import requests
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TIMEOUT = 15

FIELDS = {
	"Webshop Content Settings": [
		{
			"fieldname": "sec_whatsapp_api",
			"label": "واتساب — الإشعارات التلقائية",
			"fieldtype": "Section Break",
			"insert_after": "whatsapp_message",
			"collapsible": 1,
			"description": "ده غير زرار الواتساب العادي. ده بيبعت تأكيد الطلب "
			               "أوتوماتيك من WhatsApp Cloud API بتاع ميتا.",
		},
		{
			"fieldname": "wa_enabled",
			"label": "فعّل إشعارات واتساب",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "sec_whatsapp_api",
		},
		{
			"fieldname": "wa_phone_number_id",
			"label": "Phone Number ID",
			"fieldtype": "Data",
			"insert_after": "wa_enabled",
			"description": "من لوحة ميتا ← WhatsApp ← API Setup.",
		},
		{
			"fieldname": "wa_token",
			"label": "Access Token",
			"fieldtype": "Password",
			"insert_after": "wa_phone_number_id",
			"description": "توكن دائم (Permanent). متحطش التوكن المؤقت — بيقع بعد يوم.",
		},
		{"fieldname": "wa_cb", "fieldtype": "Column Break", "insert_after": "wa_token"},
		{
			"fieldname": "wa_template_confirm",
			"label": "اسم قالب تأكيد الطلب",
			"fieldtype": "Data",
			"insert_after": "wa_cb",
			"description": "الاسم زي ما هو في ميتا، مثال: order_confirmed",
		},
		{
			"fieldname": "wa_template_shipped",
			"label": "اسم قالب الشحن",
			"fieldtype": "Data",
			"insert_after": "wa_template_confirm",
		},
		{
			"fieldname": "wa_language",
			"label": "لغة القالب",
			"fieldtype": "Data",
			"default": "ar",
			"insert_after": "wa_template_shipped",
			"description": "زي ما مسجّلة في ميتا: ar أو ar_EG أو en.",
		},
	],
}

API = u'''

# ============================================================================
# واتساب — WhatsApp Cloud API
# ============================================================================

def _wa_settings():
	s = frappe.get_single("Webshop Content Settings")
	if not s.get("wa_enabled"):
		return None
	token = s.get_password("wa_token", raise_exception=False)
	phone_id = (s.get("wa_phone_number_id") or "").strip()
	if not token or not phone_id:
		return None
	return frappe._dict({
		"token": token,
		"phone_id": phone_id,
		"language": (s.get("wa_language") or "ar").strip(),
		"confirm": (s.get("wa_template_confirm") or "").strip(),
		"shipped": (s.get("wa_template_shipped") or "").strip(),
	})


def normalise_msisdn(phone):
	"""
	An Egyptian mobile in the form Meta expects: 20 then ten digits, no plus.

	Customers type 01012345678, +201012345678, 0020..., or with spaces. Sending
	any of those verbatim gets silently dropped by Meta.
	"""
	digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
	if digits.startswith("00"):
		digits = digits[2:]
	if digits.startswith("0") and len(digits) == 11:
		digits = "20" + digits[1:]
	elif len(digits) == 10 and digits.startswith("1"):
		digits = "20" + digits
	return digits if digits.startswith("20") and len(digits) == 12 else None


def send_whatsapp_template(phone, template, params=None):
	"""
	One templated message. Returns (ok, detail) — never raises into the caller,
	because a messaging failure must not roll back an order that was placed.
	"""
	settings = _wa_settings()
	if not settings or not template:
		return False, "whatsapp not configured"

	to = normalise_msisdn(phone)
	if not to:
		return False, "bad number: %s" % phone

	body = {
		"messaging_product": "whatsapp",
		"to": to,
		"type": "template",
		"template": {
			"name": template,
			"language": {"code": settings.language},
		},
	}
	if params:
		body["template"]["components"] = [{
			"type": "body",
			"parameters": [{"type": "text", "text": str(p)} for p in params],
		}]

	try:
		res = requests.post(
			"https://graph.facebook.com/v21.0/%s/messages" % settings.phone_id,
			headers={
				"Authorization": "Bearer %s" % settings.token,
				"Content-Type": "application/json",
			},
			data=json.dumps(body),
			timeout=TIMEOUT,
		)
		ok = res.status_code < 300
		detail = res.text[:400]
	except Exception as exc:
		ok, detail = False, str(exc)[:400]

	if not ok:
		# Logged, not swallowed — the shop needs to know a customer went untold.
		frappe.log_error(
			title="WhatsApp send failed",
			message="to=%s template=%s\\n%s" % (to, template, detail),
		)
	return ok, detail


@frappe.whitelist()
def send_test(phone):
	"""Fire one message from the Desk so the setup can be proven before launch."""
	settings = _wa_settings()
	if not settings:
		frappe.throw(frappe._("فعّل واتساب وحط التوكن و Phone Number ID الأول."))
	if not settings.confirm:
		frappe.throw(frappe._("اكتب اسم قالب تأكيد الطلب."))
	ok, detail = send_whatsapp_template(phone, settings.confirm, ["اختبار", "0"])
	return {"ok": ok, "detail": detail}
'''


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	import io
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "send_whatsapp_template" not in s:
		if "import requests" not in s:
			s = s.replace("import frappe", "import requests\n\nimport frappe", 1)
		io.open(p, "w", encoding="utf-8").write(s + API)
		print("notifications.py extended")

	frappe.db.commit()
	frappe.clear_cache()
	print("WHATSAPP READY (disabled until credentials are added)")
