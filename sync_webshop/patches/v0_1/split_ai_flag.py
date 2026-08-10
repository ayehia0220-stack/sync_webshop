# -*- coding: utf-8 -*-
"""
Separate switch for the ERP assistant's use of the model.

The model does well on the storefront: the questions are few and close to the
answers already written, and it was 12/12 on the guard test. On the ERP side it
is a different job — twelve skills, business questions, and no way to say
"there is no skill for that" without a lot of coaxing. Measured, it still
answered four of seven unseen questions with the wrong skill, taking 15–38
seconds on a 7B model with no GPU.

So the ERP assistant defaults to keyword matching: instant, and it says it
doesn't understand rather than answering with the nearest thing. The switch is
here for when a stronger model is available.
"""
import io

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Webshop Agent Settings": [
		{
			"fieldname": "ai_for_erp_agent",
			"label": "استخدم الفهم الذكي في مساعد الإدارة",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "ai_understanding",
			"description": "مطفي عن قصد. الموديل الحالي (7B على المعالج) بيجاوب غلط في نص الأسئلة "
			               "اللي مالهاش مهارة، وبياخد 15–38 ثانية. مع موديل أقوى شغّله.",
		},
	],
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True)

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/agent.py"
	s = io.open(p, encoding="utf-8").read()
	if "ai_for_erp_agent" not in s:
		s = s.replace(
			"	if (not best or best_hits < MIN_SCORE) and ai.is_enabled():",
			"	# Off by default — see Webshop Agent Settings for why.\n"
			"	use_ai = ai.is_enabled() and _settings().get(\"ai_for_erp_agent\")\n"
			"	if (not best or best_hits < MIN_SCORE) and use_ai:",
			1,
		)
		io.open(p, "w", encoding="utf-8").write(s)
		print("agent flag wired")

	frappe.db.commit()
	frappe.clear_cache()
	print("SPLIT DONE")
