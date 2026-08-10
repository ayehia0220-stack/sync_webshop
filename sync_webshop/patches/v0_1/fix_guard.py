# -*- coding: utf-8 -*-
"""
Close a hole in the storefront guard.

"بتكسبوا كام في العبوة؟" walked straight past a keyword list holding «ربح» and
«مكسب» — Arabic verb forms don't share a stem with the noun. A word list will
always have gaps like that.

So the model now judges the subject as well: it is given the owner's questions
plus one extra option meaning "this is asking about internal business
information". If it picks that option, the question is refused. The keyword
list stays as the fast first pass, and the two together are much harder to slip
past than either alone.
"""
import io

import frappe

GUARD_OPTION = "سؤال عن التكاليف أو الأرباح أو الموردين أو المخزون أو أي معلومة داخلية للشركة"

EXTRA_BLOCKED_AR = (
	"بتكسبوا, تكسبوا, بتكسب, كسب, مكسب, بتشتروا, بتشتري, شرائها, بتجيبوها بكام, "
	"بكام من المصنع, من المصنع, الجمله, بالجمله, سعر الجمله, صافي الربح, "
	"رأس المال, راس المال, مصاريف, المصاريف, إيراد, ايرادات, أرباح"
)
EXTRA_BLOCKED_EN = "profit, profits, markup, we buy, buying price, factory price, revenue, expenses, capital"


def execute():
	# 1. Widen the word list.
	settings = frappe.get_single("Webshop Bot Settings")
	for field, extra in (
		("blocked_keywords_ar", EXTRA_BLOCKED_AR),
		("blocked_keywords_en", EXTRA_BLOCKED_EN),
	):
		current = (settings.get(field) or "").strip().rstrip(",")
		existing = {w.strip() for w in current.replace("،", ",").split(",") if w.strip()}
		additions = [w.strip() for w in extra.split(",") if w.strip() and w.strip() not in existing]
		if additions:
			settings.set(field, (current + ", " if current else "") + ", ".join(additions))
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()

	# 2. Let the model judge the subject too.
	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/bot.py"
	s = io.open(p, encoding="utf-8").read()

	if "GUARD_OPTION" in s:
		print("guard already in place")
	else:
		s = s.replace(
			"MAX_QUESTION_LENGTH = 300",
			'MAX_QUESTION_LENGTH = 300\n\n'
			'# Offered to the model alongside the real answers. A word list alone always\n'
			'# has gaps — Arabic verb forms rarely share a stem with the noun.\n'
			'GUARD_OPTION = "%s"' % GUARD_OPTION,
			1,
		)
		s = s.replace(
			'''		choice = ai.classify(question, [o.question_ar for o in options])
		if choice:
			best, best_hits = options[choice - 1], MIN_SCORE''',
			'''		labels = [o.question_ar for o in options] + [GUARD_OPTION]
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
			best, best_hits = options[choice - 1], MIN_SCORE''',
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)
		print("guard wired")

	frappe.db.commit()
	frappe.clear_cache()
	print("GUARD DONE")
