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

from sync_webshop.api import ai

from sync_webshop.api.utils import set_cors_headers

MAX_QUESTION_LENGTH = 300

# Offered to the model alongside the real answers. A word list alone always
# has gaps — Arabic verb forms rarely share a stem with the noun.
GUARD_OPTION = "سؤال عن التكاليف أو الأرباح أو الموردين أو المخزون أو أي معلومة داخلية للشركة"


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
SUFFIXES = ("هما", "كما", "هم", "هن", "كم", "كن", "نا", "ها", "ات", "ين", "ون", "ية", "ه", "ي", "ك")


def _strip_prefix(word):
	for prefix in PREFIXES:
		if len(word) > len(prefix) + 2 and word.startswith(prefix):
			return word[len(prefix):]
	return word


def _strip_suffix(word):
	for suffix in SUFFIXES:
		if len(word) > len(suffix) + 2 and word.endswith(suffix):
			return word[: -len(suffix)]
	return word


def _stem(word):
	return _strip_suffix(_strip_prefix(word))


def _tokens(text):
	raw = [w for w in re.split(r"[^\w]+", text) if w]
	forms = set(raw)
	forms |= {_strip_prefix(w) for w in raw}
	forms |= {_stem(w) for w in raw}
	return {f for f in forms if len(f) >= 2}


def _word_score(word, question_words):
	"""2 for the word itself, 1 for an inflected form, 0 for nothing."""
	if not word or len(word) < 2:
		return 0
	if word in question_words:
		return 2
	if _stem(word) in question_words:
		return 1
	if len(word) >= 5 and any(
		w.startswith(word) or word.startswith(w) for w in question_words if len(w) >= 4
	):
		return 1
	return 0


def keyword_score(keyword, question_words):
	"""
	A whole phrase scores well; a single word from a phrase scores nothing, so
	"طلب" on its own can't pull in the skill keyed on "طلبات مفتوحة".
	"""
	if not keyword:
		return 0
	parts = [p for p in keyword.split() if len(p) >= 2]
	if not parts:
		return 0
	if len(parts) > 1:
		scores = [_word_score(p, question_words) for p in parts]
		return 3 if all(scores) else 0
	return _word_score(parts[0], question_words)


def _matches(keyword, question_words):
	"""Kept for callers that only need a yes/no."""
	return keyword_score(keyword, question_words) > 0


# A single inflected match is too weak to act on.
MIN_SCORE = 2


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
		hits = max(
			(keyword_score(_normalise(w), question_words)
			 for w in _words(row.keywords_ar) + _words(row.keywords_en)),
			default=0,
		)
		if hits > best_hits:
			best, best_hits = row, hits

	if (not best or best_hits < MIN_SCORE) and ai.is_enabled():
		# The blocked-subject check already ran, so the model never sees a
		# question about cost or margin.
		options = frappe.get_all(
			"Webshop Bot Answer",
			filters={"enabled": 1},
			fields=["name", "question_ar", "answer_ar", "answer_en", "times_used"],
			order_by="name",
		)
		labels = [o.question_ar for o in options] + [GUARD_OPTION]
		choice = ai.classify(question, labels)
		if choice == len(labels):
			# The model read this as an internal question.
			_log(question, None, "ممنوع", lang)
			return {
				"answered": False,
				"blocked": True,
				"reply": (s.get("blocked_reply_ar") if is_ar else s.get("blocked_reply_en"))
				or "ده استفسار داخلي مش بقدر أرد عليه.",
				"handover": True,
			}
		if choice:
			best, best_hits = options[choice - 1], MIN_SCORE

	if not best or best_hits < MIN_SCORE:
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
