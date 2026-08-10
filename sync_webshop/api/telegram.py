# -*- coding: utf-8 -*-
"""
Telegram front end for the ERP assistant.

A Telegram bot is a door into business data that anyone on the internet can
knock on, so the rules are strict:

  * Only chat ids registered against an ERP user get an answer. Everyone else
    is told they are not registered — no data, no hint about what exists.
  * The assistant then runs **as that ERP user**, so Telegram grants nobody a
    single permission they don't already have in the Desk.
  * Telegram signs its calls with a secret token we generate; a request without
    it is dropped before anything is read.

Same skills, same read-only limit as the Desk assistant.
"""
import json

import frappe
import requests

from sync_webshop.api.agent import answer

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 15


def _settings():
	return frappe.get_single("Webshop Agent Settings")


def _token():
	return (_settings().get_password("telegram_bot_token", raise_exception=False) or "").strip()


def _call(method, payload):
	token = _token()
	if not token:
		return None
	try:
		return requests.post(API.format(token=token, method=method), json=payload, timeout=TIMEOUT).json()
	except Exception:
		frappe.log_error(title="Telegram call failed: " + method, message=frappe.get_traceback())
		return None


def _send(chat_id, text):
	_call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


def _user_for_chat(chat_id):
	"""Which ERP user this Telegram account speaks as, if any."""
	return frappe.db.get_value(
		"Webshop Telegram User",
		{"chat_id": str(chat_id), "enabled": 1},
		"erp_user",
	)


@frappe.whitelist(allow_guest=True)
def webhook():
	"""
	Telegram posts every message here.

	Always answers 200 — Telegram retries anything else, and a retry storm on a
	live ERP is worse than a dropped message.
	"""
	try:
		_handle_update()
	except Exception:
		frappe.log_error(title="Telegram webhook", message=frappe.get_traceback())
	return {"ok": True}


def _handle_update():
	settings = _settings()
	if not settings.get("telegram_enabled"):
		return

	# Telegram echoes this header back on every call; without it the request
	# did not come from Telegram.
	expected = settings.get_password("telegram_webhook_secret", raise_exception=False)
	if expected and frappe.get_request_header("X-Telegram-Bot-Api-Secret-Token") != expected:
		return

	data = frappe.request.get_json(silent=True) or {}
	message = data.get("message") or data.get("edited_message") or {}
	chat_id = (message.get("chat") or {}).get("id")
	text = (message.get("text") or "").strip()
	if not chat_id or not text:
		return

	erp_user = _user_for_chat(chat_id)
	if not erp_user:
		_send(
			chat_id,
			"مش مسجّل. ابعت الرقم ده لمدير النظام عشان يضيفك:\n`%s`" % chat_id,
		)
		return

	if text.startswith("/start"):
		_send(chat_id, settings.get("greeting") or "أهلاً. اسألني عن المبيعات أو الطلبات أو المخزون.")
		return

	# Everything from here runs with that user's permissions, not ours.
	frappe.set_user(erp_user)
	try:
		result = answer(text, channel="Telegram")
		_send(chat_id, result.get("reply") or "مفيش رد.")
	finally:
		frappe.set_user("Administrator")


@frappe.whitelist()
def register_webhook():
	"""
	Point Telegram at this site. Run once after saving the bot token, and again
	if the address changes.
	"""
	frappe.only_for("System Manager")
	settings = _settings()

	if not _token():
		frappe.throw(frappe._("احفظ توكن البوت الأول في إعدادات المساعد."))

	secret = settings.get_password("telegram_webhook_secret", raise_exception=False)
	if not secret:
		secret = frappe.generate_hash(length=32)
		settings.telegram_webhook_secret = secret
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()
		frappe.db.commit()

	url = frappe.utils.get_url("/api/method/sync_webshop.api.telegram.webhook")
	result = _call(
		"setWebhook",
		{
			"url": url,
			"secret_token": secret,
			"allowed_updates": ["message"],
			"drop_pending_updates": True,
		},
	)
	return {"url": url, "telegram": result}


@frappe.whitelist()
def bot_info():
	"""Confirm the token works and show which bot it belongs to."""
	frappe.only_for("System Manager")
	if not _token():
		frappe.throw(frappe._("مفيش توكن محفوظ."))
	return _call("getMe", {})


@frappe.whitelist()
def send_test(chat_id, message="اختبار من دبونو ✅"):
	frappe.only_for("System Manager")
	_send(chat_id, message)
	return {"sent": True}
