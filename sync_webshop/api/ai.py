# -*- coding: utf-8 -*-
"""
Understanding layer, running on the Ollama model already installed on this
server.

The model is used for one job only: given a question and a numbered list of
things the assistant already knows how to do, pick the number. It never writes
an answer, never sees business data, and never invents a fact — the reply the
user gets is still the owner's own text or the output of a named, reviewed
query.

That keeps the useful part of a language model (understanding how people
actually phrase things) without the part that would let it promise a delivery
date or quote a price nobody set.
"""
import re

import frappe
import requests

DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "iKhalid/ALLaM:7b"
TIMEOUT = 25

PROMPT = """اختر رقماً واحداً فقط من القائمة يناسب سؤال المستخدم.
لو مفيش أي خيار مناسب اكتب 0. لا تكتب أي كلام غير الرقم.

{options}

السؤال: {question}
الرقم:"""


def _settings():
	return frappe.get_single("Webshop Agent Settings")


def is_enabled():
	try:
		return bool(_settings().get("ai_understanding"))
	except Exception:
		return False


def _config():
	s = _settings()
	return (
		(s.get("ai_endpoint") or DEFAULT_ENDPOINT).rstrip("/"),
		s.get("ai_model") or DEFAULT_MODEL,
		s.get("ai_keep_alive") or "30m",
	)


def classify(question, options):
	"""
	Return the 1-based index of the option that fits, or 0.

	Any failure — model down, slow, odd reply — returns 0, so the assistant
	falls back to "I don't know" rather than guessing.
	"""
	if not options or not question:
		return 0

	endpoint, model, keep_alive = _config()
	numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(options, start=1))

	try:
		response = requests.post(
			f"{endpoint}/api/generate",
			json={
				"model": model,
				"prompt": PROMPT.format(options=numbered, question=question),
				"stream": False,
				"keep_alive": keep_alive,
				"options": {"temperature": 0, "num_predict": 6},
			},
			timeout=TIMEOUT,
		)
		reply = (response.json() or {}).get("response", "")
	except Exception:
		frappe.log_error(title="AI classify failed", message=frappe.get_traceback())
		return 0

	match = re.search(r"\d+", str(reply))
	if not match:
		return 0

	choice = int(match.group())
	return choice if 1 <= choice <= len(options) else 0


@frappe.whitelist()
def test_understanding(question="عايز اعرف بعت كام النهارده"):
	"""Quick check from the Desk that the model is reachable and sensible."""
	frappe.only_for(("System Manager", "Sales Manager"))
	skills = frappe.get_all(
		"Webshop Agent Skill",
		filters={"enabled": 1},
		fields=["name", "skill_name"],
		order_by="name",
	)
	if not skills:
		return {"error": "مفيش مهارات مفعّلة."}

	choice = classify(question, [s.skill_name for s in skills])
	return {
		"question": question,
		"picked": skills[choice - 1].skill_name if choice else "مفيش",
		"enabled": is_enabled(),
	}


CONFIRM_PROMPT = """هل الإجابة على «{option}» ترد فعلاً على سؤال المستخدم؟
اكتب نعم أو لا فقط.

سؤال المستخدم: {question}
الإجابة:"""


def confirm(question, option):
	"""
	Second opinion on the chosen skill.

	Classification alone will always pick *something*. Asking plainly whether
	that something answers the question catches the near-misses — "average
	order value" matched against a price lookup, for instance.
	"""
	endpoint, model, keep_alive = _config()
	try:
		response = requests.post(
			f"{endpoint}/api/generate",
			json={
				"model": model,
				"prompt": CONFIRM_PROMPT.format(option=option, question=question),
				"stream": False,
				"keep_alive": keep_alive,
				"options": {"temperature": 0, "num_predict": 4},
			},
			timeout=TIMEOUT,
		)
		reply = str((response.json() or {}).get("response", ""))
	except Exception:
		# If the check cannot run, do not act on an unverified guess.
		return False

	reply = reply.strip()
	if "لا" in reply and "نعم" not in reply:
		return False
	return "نعم" in reply or reply.lower().startswith("yes")
