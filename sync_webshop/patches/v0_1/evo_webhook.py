# -*- coding: utf-8 -*-
"""
Receive incoming WhatsApp, without breaking what already listens.

Both Evolution instances already post to n8n — 1212 to a general flow and 97 to
the renewal campaign, which is live business logic answering real customers.
Evolution allows one webhook URL per instance, so pointing it here would have
silently killed the renewal replies.

Instead this endpoint logs the message and then forwards the untouched payload
to whatever n8n URL that instance was using. n8n never notices the difference.
The forward runs in the background: if n8n is slow or down, Evolution still gets
its 200 immediately and does not retry.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop WhatsApp Line": [
		{
			"fieldname": "forward_to",
			"label": "يمرّر لـ (n8n)",
			"fieldtype": "Data",
			"insert_after": "evo_instance",
			"translatable": 0,
			"description": "اللينك اللي كان مربوط قبل كده. سيبه فاضي لو مش عايز تمرير.",
		},
	],
}

API = u'''

@frappe.whitelist(allow_guest=True)
def evolution_webhook(instance=None):
	"""
	Evolution posts here when a message arrives.

	Always answers 200. An error code makes Evolution retry the same message
	repeatedly, which would multiply every log entry.
	"""
	from sync_webshop.api.utils import set_cors_headers
	set_cors_headers()

	payload = {}
	try:
		payload = frappe.request.get_json(force=True, silent=True) or {}
	except Exception:
		pass

	try:
		_handle_evolution(payload, instance)
	except Exception:
		frappe.log_error(title="Evolution webhook",
		                 message=frappe.get_traceback()[:2000])

	return {"ok": True}


def _handle_evolution(payload, instance=None):
	instance = instance or payload.get("instance") or ""
	event = (payload.get("event") or "").lower()
	data = payload.get("data") or {}

	# Evolution sends one message or a list, depending on the event.
	messages = data if isinstance(data, list) else [data]

	for msg in messages:
		if not isinstance(msg, dict):
			continue
		key = msg.get("key") or {}
		remote = key.get("remoteJid") or ""

		# Groups and status broadcasts are not customer conversations.
		if "@g.us" in remote or "status@" in remote:
			continue

		phone = remote.split("@")[0]
		if not phone:
			continue

		body = _message_text(msg.get("message") or {})
		if not body:
			continue

		from_me = bool(key.get("fromMe"))
		# SEND_MESSAGE echoes back what we sent, and the sender already logged
		# it — recording it again would double every outgoing message.
		if from_me and event == "send.message":
			continue

		log_whatsapp(phone, body, sent=from_me)

	frappe.db.commit()
	_forward(payload, instance)


def _message_text(message):
	"""The readable part of whatever kind of message arrived."""
	if not isinstance(message, dict):
		return ""
	for key in ("conversation",):
		if message.get(key):
			return str(message[key])
	for key in ("extendedTextMessage", "imageMessage", "videoMessage",
	            "documentMessage", "buttonsResponseMessage", "listResponseMessage"):
		part = message.get(key) or {}
		if isinstance(part, dict):
			text = (part.get("text") or part.get("caption")
			        or part.get("selectedDisplayText") or part.get("title"))
			if text:
				return str(text)
			if key.endswith("Message"):
				return "[%s]" % key.replace("Message", "")
	if message.get("audioMessage"):
		return "[رسالة صوتية]"
	if message.get("locationMessage"):
		loc = message["locationMessage"]
		return "[موقع] %s,%s" % (loc.get("degreesLatitude"), loc.get("degreesLongitude"))
	return ""


def _forward(payload, instance):
	"""Pass the payload on to whatever was listening before."""
	settings = frappe.get_single("Webshop Content Settings")
	url = None
	for line in settings.get("wa_lines") or []:
		if (line.evo_instance or "") == str(instance):
			url = (line.forward_to or "").strip()
			break
	if not url:
		return

	frappe.enqueue(
		"sync_webshop.api.notifications._forward_now",
		queue="short", url=url, payload=payload, enqueue_after_commit=True)


def _forward_now(url, payload):
	try:
		requests.post(url, json=payload, timeout=20)
	except Exception as exc:
		frappe.log_error(title="Evolution forward failed",
		                 message="%s\\n%s" % (url, str(exc)[:400]))
'''


def execute():
	import io

	create_custom_fields(FIELDS, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/notifications.py"
	s = io.open(p, encoding="utf-8").read()
	if "def evolution_webhook" not in s:
		io.open(p, "w", encoding="utf-8").write(s + API)
		print("notifications.py: evolution webhook")

	# Remember where each instance was posting, so the forward keeps it alive.
	settings = frappe.get_single("Webshop Content Settings")
	existing = {
		"1212": "https://n8n.dpono.com/webhook/claude-whatsapp",
		"97": "https://n8n.dpono.com/webhook/renewal-reply",
	}
	for line in settings.get("wa_lines") or []:
		if line.evo_instance in existing and not (line.forward_to or "").strip():
			line.forward_to = existing[line.evo_instance]
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	frappe.db.commit()
	frappe.clear_cache()
	print("WEBHOOK READY")
	for line in settings.get("wa_lines") or []:
		print("   %-6s instance=%-6s forwards to %s" % (
			line.line_name, line.evo_instance or "—", line.forward_to or "(مفيش)"))
