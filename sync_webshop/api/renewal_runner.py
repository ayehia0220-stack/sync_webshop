# -*- coding: utf-8 -*-
"""
حملة التجديد بتشتغل من جوّه الـ ERP — إرسالًا وردًا.

كانت ورك فلوتين في n8n، والاتنين مجرد أنابيب: واحدة بتنده
`get_due_messages` كل ساعة وتنام بين الرسالة والتانية وتبعت، وواحدة
بتستقبل الرد وتنده `handle_incoming` وترجّع رده.

**الفرق الوحيد في المنطق**: n8n كانت بتاخد كل رسايل الساعة مرة واحدة
وتنام 45-150 ثانية بين كل واحدة. هنا بنشتغل كل 5 دقايق ونبعت **رسالة
واحدة**. النتيجة نفس العدد اليومي بالظبط (نصيب الساعة هو اللي بيحكم)،
بس التوزيع أهدى، ومفيش عامل بيفضل نايم ربع ساعة مشغول.
"""

import frappe
from frappe.utils import cint

from sync_webshop.api import renewal


def _campaign_line(settings):
	"""خط الواتساب بتاع الحملة — رقم الـ GPS."""
	instance = str(settings.instance_name or "97")
	content = frappe.get_single("Webshop Content Settings")
	for row in content.get("wa_lines") or []:
		if (row.evo_instance or "") == instance:
			return row, instance
	return None, instance


# ————————————————————————————— الإرسال —————————————————————————————

def run_campaign():
	"""
	بتنده كل 5 دقايق من المجدول.

	`get_due_messages` هي اللي بتقرر: مقفولة؟ برّه ساعات الشغل؟ خلص
	نصيب الساعة؟ الرقم مفصول؟ — كل ده متجرَّب وشغّال، فمابنكررش المنطق
	هنا، بنطلب رسالة واحدة وبس.
	"""
	from sync_webshop.api.notifications import send_whatsapp_text

	settings = renewal._settings()
	if not settings.enabled:
		return {"sent": 0, "reason": "الحملة مقفولة"}

	due = renewal.get_due_messages(limit=1) or {}
	if not cint(due.get("send")):
		return {"sent": 0, "reason": due.get("reason") or "مفيش مستحق دلوقتي"}

	msg = (due.get("messages") or [None])[0]
	if not msg:
		return {"sent": 0, "reason": "مفيش رسالة"}

	line, instance = _campaign_line(settings)
	ok, detail = send_whatsapp_text(msg["mobile"], msg["body"], line=line)
	renewal.mark_sent(msg["subscription"], template=msg.get("template"),
	                  ok=1 if ok else 0, body=msg["body"],
	                  error=None if ok else str(detail)[:300])
	return {"sent": 1 if ok else 0, "instance": instance,
	        "to": msg["mobile"], "stage": msg.get("stage"),
	        "error": None if ok else str(detail)[:200]}


# ————————————————————————————— الردود —————————————————————————————

def _extract(msg):
	"""الرقم والنص من رسالة Evolution — والصورة معناها إيصال تحويل."""
	key = msg.get("key") or {}
	if key.get("fromMe"):
		return None
	jid = str(key.get("remoteJid") or "")
	if not jid.endswith("@s.whatsapp.net"):     # مش جروبات ولا حالات
		return None

	body = msg.get("message") or {}
	image = body.get("imageMessage") or body.get("documentMessage")
	text = (body.get("conversation")
	        or (body.get("extendedTextMessage") or {}).get("text")
	        or (body.get("buttonsResponseMessage") or {}).get("selectedDisplayText")
	        or (body.get("listResponseMessage") or {}).get("title")
	        or (image or {}).get("caption")
	        or "")
	text = str(text).strip()
	if not image and not text:
		return None

	return frappe._dict({
		"mobile": jid.split("@")[0], "text": text,
		"is_image": 1 if image else 0,
		"event_id": str(key.get("id") or ""),
	})


def handle_reply(payload, instance):
	"""
	بينده من `notifications._handle_evolution` لرقم الحملة.

	بيرجّع True لو الرسالة بتاعتنا — ساعتها مافيش تمرير لـ n8n.
	"""
	settings = renewal._settings()
	if str(instance) != str(settings.instance_name or "97"):
		return False
	# الردود بتشتغل حتى لو الإرسال متوقّف: عميل بعت رسالة يستاهل رد،
	# سواء الحملة شغّالة أو المالك وقّفها.

	from sync_webshop.api.notifications import send_whatsapp_text
	line, _inst = _campaign_line(settings)

	data = payload.get("data") or {}
	messages = data if isinstance(data, list) else [data]
	touched = False

	for raw in messages:
		if not isinstance(raw, dict):
			continue
		item = _extract(raw)
		if not item:
			continue
		touched = True

		try:
			out = renewal.handle_incoming(item.mobile, item.text,
			                              is_image=item.is_image) or {}
		except Exception:
			frappe.log_error(title="Renewal reply",
			                 message=frappe.get_traceback()[:2000])
			continue

		# «محوّل لموظف» معناه مفيش رد آلي عن قصد — عشان العميل ما
		# يحسّش إنه بيكلم روبوت وهو مستني بني آدم
		reply = (out.get("reply") or "").strip()
		if reply:
			send_whatsapp_text("+" + item.mobile, reply, line=line)

		if out.get("send_image"):
			try:
				renewal.send_payment_image(item.mobile)
			except Exception:
				frappe.log_error(title="Renewal payment image",
				                 message=frappe.get_traceback()[:1500])
		if cint(out.get("send_prices_image")):
			try:
				renewal.send_prices_image(item.mobile)
			except Exception:
				frappe.log_error(title="Renewal prices image",
				                 message=frappe.get_traceback()[:1500])

	return touched


# ————————————————————————————— للفحص —————————————————————————————

@frappe.whitelist()
def preview_next():
	"""إيه اللي هيتبعت في النداء الجاي — من غير ما يتبعت."""
	frappe.only_for("System Manager")
	due = renewal.get_due_messages(limit=1) or {}
	msg = (due.get("messages") or [None])[0]
	if not msg:
		return {"send": 0, "reason": due.get("reason")}
	return {"send": 1, "to": msg["mobile"], "stage": msg.get("stage"),
	        "customer": msg.get("customer_name"), "body": msg["body"]}
