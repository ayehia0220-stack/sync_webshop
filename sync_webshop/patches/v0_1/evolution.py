# -*- coding: utf-8 -*-
"""
Send through Evolution API instead of Meta.

Evolution is already running on this server with both numbers connected and
scanned — 1212 for coffee, 97 for GPS. That is a better fit than Meta Cloud API
for this shop:

  * the numbers keep working in the normal WhatsApp app, so the team can still
    reply by hand; Meta would have taken them over
  * plain text messages, no template to submit and wait for approval
  * no business verification, and nothing per message

The trade is that Evolution rides the WhatsApp Web protocol rather than an
official API, so a number can be disconnected by WhatsApp if it is used to
blast strangers. Order updates to people who bought something are exactly the
traffic it is safe for.

The line table stays as it is — only where the message goes changes.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop Content Settings": [
		{
			"fieldname": "wa_provider",
			"label": "طريقة الإرسال",
			"fieldtype": "Select",
			"options": "evolution\nmeta",
			"default": "evolution",
			"insert_after": "wa_enabled",
			"description": "evolution = السيرفر بتاعك (مجاني) · meta = واتساب الرسمي.",
		},
		{
			"fieldname": "evo_url",
			"label": "عنوان Evolution",
			"fieldtype": "Data",
			"default": "http://127.0.0.1:8080",
			"insert_after": "wa_provider",
		},
		{
			"fieldname": "evo_api_key",
			"label": "مفتاح Evolution",
			"fieldtype": "Password",
			"insert_after": "evo_url",
		},
	],
	"Webshop WhatsApp Line": [
		{
			"fieldname": "evo_instance",
			"label": "اسم الخط في Evolution",
			"fieldtype": "Data",
			"insert_after": "phone_display",
			"translatable": 0,
			"description": "زي ما هو في Evolution — مثال: 1212 أو 97",
		},
	],
}

API = u'''

# ============================================================================
# Evolution API — الإرسال من السيرفر
# ============================================================================

def _evo():
	s = frappe.get_single("Webshop Content Settings")
	if (s.get("wa_provider") or "evolution") != "evolution":
		return None
	key = s.get_password("evo_api_key", raise_exception=False)
	if not key:
		return None
	return frappe._dict({
		"url": (s.get("evo_url") or "http://127.0.0.1:8080").rstrip("/"),
		"key": key,
	})


def send_whatsapp_text(phone, text, line=None, order_name=None, customer=None):
	"""
	One plain WhatsApp message down the right line.

	Returns (ok, detail) and never raises — a message that fails to send must
	not roll back the order it was telling someone about.
	"""
	evo = _evo()
	if not evo:
		return False, "evolution not configured"

	line = line or whatsapp_line_for(order_name=order_name, customer=customer)
	instance = (line or {}).get("evo_instance") if line else None
	if not instance:
		return False, "no line for this order"

	to = normalise_msisdn(phone)
	if not to:
		return False, "bad number: %s" % phone

	try:
		res = requests.post(
			"%s/message/sendText/%s" % (evo.url, instance),
			headers={"apikey": evo.key, "Content-Type": "application/json"},
			json={"number": to, "text": text},
			timeout=20,
		)
		ok = res.status_code < 300
		detail = res.text[:300]
	except Exception as exc:
		ok, detail = False, str(exc)[:300]

	# Logged either way — a failed send is the one worth finding later.
	log_whatsapp(to, text, sent=True, customer=customer, reference=order_name)

	if not ok:
		frappe.log_error(title="WhatsApp send failed",
		                 message="line=%s to=%s\\n%s" % (instance, to, detail))
	return ok, detail


@frappe.whitelist()
def send_test_message(phone, text=None, line_name=None):
	"""Fire one real message from the Desk, to prove the wiring."""
	settings = frappe.get_single("Webshop Content Settings")
	line = None
	for row in settings.get("wa_lines") or []:
		if not line_name or row.line_name == line_name:
			line = row
			break
	ok, detail = send_whatsapp_text(
		phone, text or "رسالة تجريبية من نظام دبونو ✅", line=line)
	return {"ok": ok, "detail": detail, "line": line.line_name if line else None}
'''


def execute():
	import io

	create_custom_fields(FIELDS, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "def send_whatsapp_text" not in s:
		io.open(p, "w", encoding="utf-8").write(s + API)
		print("notifications.py: evolution sender")

	settings = frappe.get_single("Webshop Content Settings")
	settings.wa_provider = "evolution"
	settings.evo_url = "http://127.0.0.1:8080"
	settings.wa_enabled = 1

	# Match the lines to the instances already connected in Evolution.
	for row in settings.get("wa_lines") or []:
		if row.line_name == "البن":
			row.evo_instance = "1212"
			row.phone_display = "01092301212"
		elif row.line_name == "GPS":
			row.evo_instance = "97"
			row.phone_display = "01098982797"

	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("EVOLUTION READY")
	for row in settings.get("wa_lines") or []:
		print("   %-6s → instance %-6s %s" % (
			row.line_name, row.evo_instance or "—", row.phone_display or ""))
