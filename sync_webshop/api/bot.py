# -*- coding: utf-8 -*-
"""
Storefront assistant.

The bot never composes an answer. It matches the shopper's words against
answers the owner wrote, and if nothing matches it says so and offers a human.
That is deliberate: a shop assistant that improvises can promise a delivery
date or a refund the business never agreed to.

Blocked subjects are checked first, before any matching, so no phrasing can
route a question about cost or margin into an answer.
"""
import re

import frappe

from sync_webshop.api.utils import set_cors_headers

MAX_QUESTION_LENGTH = 300


def _settings():
	return frappe.get_single("Webshop Bot Settings")


def _words(raw):
	if not raw:
		return []
	return [w.strip().lower() for w in str(raw).replace("،", ",").split(",") if w.strip()]


def _normalise(text):
	"""Fold Arabic spelling variants so 'إزاى' matches 'ازاي'."""
	text = str(text or "").lower().strip()
	text = re.sub(r"[إأآا]", "ا", text)
	text = re.sub(r"[ىي]", "ي", text)
	text = re.sub(r"[ؤئ]", "ء", text)
	text = text.replace("ة", "ه")
	text = re.sub(r"[ً-ٟـ]", "", text)  # harakat and tatweel
	return re.sub(r"\s+", " ", text)


# Arabic glues short particles onto the front of words, so a bare substring
# search makes "وصل" (arrived) match inside "بتوصلوا" (do you deliver) and
# answer the wrong question. Matching works on whole words instead.
PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال", "و", "ب", "ف", "ل", "ك")


def _strip_prefix(word):
	for prefix in PREFIXES:
		if len(word) > len(prefix) + 2 and word.startswith(prefix):
			return word[len(prefix):]
	return word


def _tokens(text):
	raw = re.split(r"[^\w؀-ۿ]+", text)
	words = [w for w in raw if w]
	return set(words) | {_strip_prefix(w) for w in words}


def _matches(keyword, question_words):
	"""A keyword counts when it is one of the words, not merely inside one."""
	if not keyword:
		return False
	parts = keyword.split()
	if len(parts) > 1:
		# A multi-word phrase still matches on the whole phrase.
		return all(_matches(p, question_words) for p in parts)
	if keyword in question_words:
		return True
	# Long keywords may appear with a suffix, e.g. "طلبات" inside "طلباتي".
	if len(keyword) >= 5:
		return any(w.startswith(keyword) for w in question_words)
	return False


def _log(question, answer_name, outcome, lang):
	if not _settings().get("log_questions"):
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Webshop Bot Log",
				"question": question[:140],
				"matched_answer": answer_name,
				"outcome": outcome,
				"language": lang,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		pass  # the log must never break a reply


@frappe.whitelist(allow_guest=True)
def get_bot_config():
	"""What the widget needs to render. No blocked list, no answers."""
	set_cors_headers()
	s = _settings()
	if not s.get("enabled"):
		return {"enabled": False}

	whatsapp = None
	if s.get("handover_whatsapp"):
		number = (frappe.get_single("Webshop Content Settings").get("whatsapp_number") or "").strip()
		digits = "".join(c for c in number if c.isdigit())
		if digits:
			whatsapp = f"https://wa.me/{digits}"

	return {
		"enabled": True,
		"name_ar": s.get("bot_name_ar") or "المساعد",
		"name_en": s.get("bot_name_en") or "Assistant",
		"greeting_ar": s.get("greeting_ar"),
		"greeting_en": s.get("greeting_en"),
		"handover_url": whatsapp,
		"handover_label_ar": s.get("handover_label_ar"),
		"handover_label_en": s.get("handover_label_en"),
		"suggestions": frappe.get_all(
			"Webshop Bot Answer",
			filters={"enabled": 1},
			fields=["question_ar", "question_en"],
			order_by="times_used desc, modified desc",
			limit=4,
		),
	}


@frappe.whitelist(allow_guest=True)
def ask(question, lang="ar"):
	"""Answer a shopper's question, or hand over."""
	set_cors_headers()
	s = _settings()
	if not s.get("enabled"):
		frappe.throw(frappe._("المساعد مش شغّال دلوقتي."))

	question = str(question or "").strip()[:MAX_QUESTION_LENGTH]
	if len(question) < 2:
		frappe.throw(frappe._("اكتب سؤالك."))

	needle = _normalise(question)
	is_ar = lang == "ar"

	# 1. Blocked subjects come first. Nothing can bypass this.
	blocked = _words(s.get("blocked_keywords_ar")) + _words(s.get("blocked_keywords_en"))
	for word in blocked:
		if _normalise(word) and _normalise(word) in needle:
			_log(question, None, "ممنوع", lang)
			return {
				"answered": False,
				"blocked": True,
				"reply": (s.get("blocked_reply_ar") if is_ar else s.get("blocked_reply_en"))
				or "ده استفسار داخلي مش بقدر أرد عليه.",
				"handover": True,
			}

	# 2. Match the owner's answers, best overlap wins.
	question_words = _tokens(needle)
	best, best_hits = None, 0
	for row in frappe.get_all(
		"Webshop Bot Answer",
		filters={"enabled": 1},
		fields=["name", "keywords_ar", "keywords_en", "answer_ar", "answer_en", "times_used"],
	):
		hits = 0
		for word in _words(row.keywords_ar) + _words(row.keywords_en):
			if _matches(_normalise(word), question_words):
				hits += 1
		if hits > best_hits:
			best, best_hits = row, hits

	if not best:
		_log(question, None, "مفيش رد", lang)
		return {
			"answered": False,
			"blocked": False,
			"reply": (s.get("fallback_ar") if is_ar else s.get("fallback_en"))
			or "مش عندي إجابة للسؤال ده.",
			"handover": True,
		}

	frappe.db.set_value("Webshop Bot Answer", best.name, "times_used",
	                    (best.times_used or 0) + 1, update_modified=False)
	frappe.db.commit()
	_log(question, best.name, "أجاب", lang)

	answer = (best.answer_ar if is_ar else best.answer_en) or best.answer_ar
	return {"answered": True, "blocked": False, "reply": answer, "handover": False}
