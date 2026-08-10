# -*- coding: utf-8 -*-
"""
Settings for the understanding layer, and wiring it in as a fallback.

Keywords stay the first pass: they are instant and cover the questions people
ask every day. The model only runs when keywords come up short, so a common
question never waits on it.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop Agent Settings": [
		{
			"fieldname": "sec_ai",
			"label": "الفهم الذكي / AI Understanding",
			"fieldtype": "Section Break",
			"insert_after": "require_confirmation",
			"description": "الموديل بيختار السؤال المناسب من اللي المساعد يعرفه — عمره ما بيكتب إجابة من عنده.",
		},
		{
			"fieldname": "ai_understanding",
			"label": "شغّل الفهم الذكي",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "sec_ai",
			"description": "لما الكلمات المفتاحية ما تكفيش، الموديل بيحاول يفهم قصد السؤال.",
		},
		{
			"fieldname": "ai_model",
			"label": "الموديل",
			"fieldtype": "Data",
			"default": "iKhalid/ALLaM:7b",
			"insert_after": "ai_understanding",
		},
		{"fieldname": "ai_cb", "fieldtype": "Column Break", "insert_after": "ai_model"},
		{
			"fieldname": "ai_endpoint",
			"label": "عنوان الخدمة",
			"fieldtype": "Data",
			"default": "http://127.0.0.1:11434",
			"insert_after": "ai_cb",
		},
		{
			"fieldname": "ai_keep_alive",
			"label": "مدة إبقاء الموديل محمّلاً",
			"fieldtype": "Data",
			"default": "30m",
			"insert_after": "ai_endpoint",
			"description": "أول سؤال بعد ما الموديل ينزل من الذاكرة بياخد ~30 ثانية. المدة دي بتمنع ده.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	# --- agent: fall back to the model when keywords are not enough -----------
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/agent.py"
	s = io.open(p, encoding="utf-8").read()
	if "ai.classify" not in s:
		s = s.replace(
			"from sync_webshop.api.bot import MIN_SCORE, _normalise, _tokens, _words, keyword_score",
			"from sync_webshop.api import ai\nfrom sync_webshop.api.bot import MIN_SCORE, _normalise, _tokens, _words, keyword_score",
			1,
		)
		s = s.replace(
			'''	if not best or best_hits < MIN_SCORE:
		reply = s.get("fallback") or "مش فاهم السؤال."''',
			'''	if (not best or best_hits < MIN_SCORE) and ai.is_enabled():
		# Keywords came up short. Let the model pick from what we already do.
		options = frappe.get_all(
			"Webshop Agent Skill",
			filters={"enabled": 1},
			fields=["name", "skill_name", "action", "times_used", "example_question"],
			order_by="name",
		)
		choice = ai.classify(question, [o.example_question or o.skill_name for o in options])
		if choice:
			best, best_hits = options[choice - 1], MIN_SCORE

	if not best or best_hits < MIN_SCORE:
		reply = s.get("fallback") or "مش فاهم السؤال."''',
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)

	# --- storefront bot: same idea, but only after the blocked check ----------
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/bot.py"
	s = io.open(p, encoding="utf-8").read()
	if "ai.classify" not in s:
		s = s.replace("import frappe\n", "import frappe\n\nfrom sync_webshop.api import ai\n", 1)
		s = s.replace(
			'''	if not best or best_hits < MIN_SCORE:
		_log(question, None, "مفيش رد", lang)''',
			'''	if (not best or best_hits < MIN_SCORE) and ai.is_enabled():
		# The blocked-subject check already ran, so the model never sees a
		# question about cost or margin.
		options = frappe.get_all(
			"Webshop Bot Answer",
			filters={"enabled": 1},
			fields=["name", "question_ar", "answer_ar", "answer_en", "times_used"],
			order_by="name",
		)
		choice = ai.classify(question, [o.question_ar for o in options])
		if choice:
			best, best_hits = options[choice - 1], MIN_SCORE

	if not best or best_hits < MIN_SCORE:
		_log(question, None, "مفيش رد", lang)''',
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)

	frappe.db.commit()
	print("AI WIRED")
