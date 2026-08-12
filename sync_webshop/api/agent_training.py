# -*- coding: utf-8 -*-
"""
One source of truth for what every assistant is allowed to say.

The owner writes `Webshop Agent Training` documents in ERPNext; this module
assembles them into the system message a bot receives. The Facebook comment
workflow, the website chat and anything added later all read from here, so a
correction is made once and applies everywhere.

Records marked for the "All" channel are always included, ahead of the
channel-specific ones, which is where shared facts belong.
"""
import frappe

ALL_CHANNEL = "الكل / All"

# What n8n and the website send -> the Select value stored on the document.
CHANNEL_ALIASES = {
	"facebook": "فيسبوك / Facebook",
	"fb": "فيسبوك / Facebook",
	"website": "الموقع / Website",
	"web": "الموقع / Website",
	"whatsapp": "واتساب / WhatsApp",
	"telegram": "تليجرام / Telegram",
	"all": ALL_CHANNEL,
}


def _resolve(channel):
	if not channel:
		return None
	key = str(channel).strip()
	return CHANNEL_ALIASES.get(key.lower(), key)


def _lines(value):
	"""Split a textarea into clean lines, dropping blanks."""
	return [line.strip(" -•\t") for line in (value or "").splitlines() if line.strip(" -•\t")]


def _documents(channel):
	wanted = [ALL_CHANNEL]
	resolved = _resolve(channel)
	if resolved and resolved != ALL_CHANNEL:
		wanted.append(resolved)

	names = frappe.get_all(
		"Webshop Agent Training",
		filters={"enabled": 1, "channel": ["in", wanted]},
		order_by="priority asc, modified asc",
		pluck="name",
	)
	# "All" first so a channel-specific document can override the shared voice.
	docs = [frappe.get_doc("Webshop Agent Training", name) for name in names]
	return sorted(docs, key=lambda d: (d.channel != ALL_CHANNEL, d.priority or 0))


def _render(docs):
	parts = []
	facts, examples, forbidden, rules, personas = [], [], [], [], []
	tone = when_unsure = output_format = None
	extra = []

	for doc in docs:
		# Personas add up: the shared voice first, then what the channel adds.
		if doc.persona and doc.persona.strip() not in personas:
			personas.append(doc.persona.strip())
		tone = doc.tone or tone
		when_unsure = doc.when_unsure or when_unsure
		output_format = doc.output_format or output_format
		rules += _lines(doc.rules)
		forbidden += _lines(doc.forbidden)
		if doc.extra_instructions:
			extra.append(doc.extra_instructions.strip())
		for row in doc.facts:
			facts.append((row.topic, row.answer))
		for row in doc.examples:
			examples.append((row.customer_says, row.public_reply, row.private_reply))

	if personas:
		parts.append("## مين أنت\n" + " ".join(personas))
	if tone:
		parts.append("## لهجتك\n" + tone)

	if rules:
		parts.append("## قواعد لازم تتبعها\n" + "\n".join(f"- {r}" for r in rules))

	if facts:
		body = "\n".join(f"- {topic}: {answer}" for topic, answer in facts)
		parts.append(
			"## المعلومات المؤكدة — دي كل اللي مسموح لك تقوله\n"
			+ body
			+ "\n\nأي رقم أو سعر أو ميعاد أو رقم تليفون مش مكتوب فوق ده: ممنوع تقوله. ممنوع تخترع."
		)

	if forbidden:
		parts.append(
			"## ممنوع تمامًا تتكلم في\n"
			+ "\n".join(f"- {f}" for f in forbidden)
			+ "\nلو العميل سأل في حاجة من دول، قوله إن حد من الفريق هيرد عليه."
		)

	if when_unsure:
		parts.append("## لو مش عارف الإجابة\n" + when_unsure.strip())

	if examples:
		block = []
		for says, public, private in examples:
			item = f"العميل: {says}"
			if public:
				item += f"\nالرد العام: {public}"
			if private:
				item += f"\nالرد الخاص: {private}"
			block.append(item)
		parts.append("## أمثلة\n\n" + "\n\n".join(block))

	if extra:
		parts.append("## تعليمات إضافية\n" + "\n\n".join(extra))

	if output_format:
		parts.append("## شكل الرد المطلوب\n" + output_format.strip())

	return "\n\n".join(parts).strip()


@frappe.whitelist()
def get_prompt(channel=None):
	"""Return the assembled system message for a channel.

	n8n calls this with ?channel=facebook; the website chat uses website.
	"""
	docs = _documents(channel)
	if not docs:
		return {
			"channel": _resolve(channel) or ALL_CHANNEL,
			"system_message": "",
			"found": 0,
			"sources": [],
			"error": "مفيش مستند تدريب مفعّل للقناة دي",
		}

	return {
		"channel": _resolve(channel) or ALL_CHANNEL,
		"system_message": _render(docs),
		"found": len(docs),
		"sources": [d.name for d in docs],
		"updated": str(max(d.modified for d in docs)),
	}


@frappe.whitelist()
def preview(channel=None):
	"""Same text as get_prompt, as plain text — for reading it in the browser."""
	return get_prompt(channel).get("system_message") or "(فاضي)"
