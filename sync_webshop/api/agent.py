# -*- coding: utf-8 -*-
"""
ERP assistant.

Runs as the logged-in user. Every read goes through `frappe.get_list`, which
applies that user's permissions and any user-permission restrictions — the
assistant cannot show someone a document they could not open themselves.

Each skill maps to a named function below. Nothing is assembled from the user's
words, so there is no way to phrase a question into a different query.
"""
import re

import frappe

from sync_webshop.api import ai
from sync_webshop.api.bot import MIN_SCORE, _normalise, _tokens, _words, keyword_score

MAX_ROWS = 10


def _settings():
	return frappe.get_single("Webshop Agent Settings")


def _money(value, currency=None):
	return frappe.utils.fmt_money(value or 0, currency=currency or _currency())


def _currency():
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	return frappe.db.get_value("Company", company, "default_currency") or "EGP"


def _log(question, skill, outcome, response, channel="ERP"):
	if not _settings().get("log_conversations"):
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Webshop Agent Log",
				"asked_by": frappe.session.user,
				"question": question[:140],
				"skill": skill,
				"outcome": outcome,
				"channel": channel,
				"response": (response or "")[:500],
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		pass


# ------------------------------------------------------------------ actions
# Every one of these uses frappe.get_list, so permissions apply to the caller.


def _sales_between(start, end, label):
	rows = frappe.get_list(
		"Sales Order",
		filters={"docstatus": 1, "transaction_date": ["between", [start, end]]},
		fields=["name", "grand_total", "currency"],
		limit_page_length=0,
	)
	total = sum(float(r.grand_total or 0) for r in rows)
	if not rows:
		return f"مفيش طلبات مؤكدة {label}."
	return f"{label}: **{len(rows)}** طلب بإجمالي **{_money(total)}**."


def act_sales_today(_question):
	today = frappe.utils.nowdate()
	return _sales_between(today, today, "النهارده")


def act_sales_month(_question):
	return _sales_between(
		frappe.utils.get_first_day(frappe.utils.nowdate()),
		frappe.utils.nowdate(),
		"الشهر ده",
	)


def act_open_orders(_question):
	rows = frappe.get_list(
		"Sales Order",
		filters={"docstatus": 1, "status": ["in", ["To Deliver and Bill", "To Deliver", "To Bill"]]},
		fields=["name", "customer", "grand_total", "delivery_date", "status"],
		order_by="delivery_date asc",
		limit_page_length=MAX_ROWS,
	)
	if not rows:
		return "مفيش طلبات مفتوحة."
	total = frappe.db.count("Sales Order", {"docstatus": 1, "status": ["in", ["To Deliver and Bill", "To Deliver", "To Bill"]]})
	lines = [f"**{total}** طلب مفتوح. أقربهم تسليمًا:"]
	for r in rows:
		lines.append(f"• {r.name} — {r.customer} — {_money(r.grand_total)} — تسليم {r.delivery_date}")
	return "\n".join(lines)


def act_order_status(question):
	match = re.search(r"(SAL-ORD-[\w-]+)", question, re.IGNORECASE)
	if not match:
		return "اكتب رقم الطلب كامل، مثلاً: حالة الطلب SAL-ORD-2026-00001"

	name = match.group(1).upper()
	rows = frappe.get_list(
		"Sales Order",
		filters={"name": name},
		fields=["name", "customer", "status", "grand_total", "delivery_date", "per_delivered"],
		limit_page_length=1,
	)
	if not rows:
		return f"مالقيتش الطلب {name}، أو مش مسموحلك تشوفه."

	r = rows[0]
	return (
		f"**{r.name}**\n"
		f"• العميل: {r.customer}\n"
		f"• الحالة: {r.status}\n"
		f"• الإجمالي: {_money(r.grand_total)}\n"
		f"• التسليم: {r.delivery_date}\n"
		f"• تم تسليم: {round(r.per_delivered or 0)}%"
	)


def act_customer_orders(question):
	# Whatever is left after the trigger words is treated as the customer name.
	needle = re.sub(r"(طلبات|العميل|عميل|orders|for|customer)", " ", question, flags=re.IGNORECASE).strip()
	if len(needle) < 2:
		return "اكتب اسم العميل بعد السؤال، مثلاً: طلبات العميل أحمد"

	customers = frappe.get_list(
		"Customer",
		filters={"customer_name": ["like", f"%{needle}%"]},
		fields=["name"],
		limit_page_length=3,
	)
	if not customers:
		return f"مالقيتش عميل باسم «{needle}»."

	out = []
	for c in customers:
		rows = frappe.get_list(
			"Sales Order",
			filters={"customer": c.name, "docstatus": 1},
			fields=["name", "transaction_date", "grand_total", "status"],
			order_by="transaction_date desc",
			limit_page_length=5,
		)
		out.append(f"**{c.name}** — {len(rows)} من آخر الطلبات:")
		for r in rows:
			out.append(f"• {r.name} — {r.transaction_date} — {_money(r.grand_total)} — {r.status}")
	return "\n".join(out)


def _find_item(question):
	needle = re.sub(
		r"(رصيد|المخزون|كام قطعة|متوفر كام|سعر|بكام|السعر بتاع|stock|price of|how much is)",
		" ", question, flags=re.IGNORECASE,
	).strip()
	if len(needle) < 2:
		return None, "اكتب اسم الصنف بعد السؤال."
	items = frappe.get_list(
		"Item",
		filters={"item_name": ["like", f"%{needle}%"], "disabled": 0},
		fields=["name", "item_name", "stock_uom"],
		limit_page_length=3,
	)
	if not items:
		return None, f"مالقيتش صنف اسمه «{needle}»."
	return items, None


def act_item_stock(question):
	items, error = _find_item(question)
	if error:
		return error
	lines = []
	for item in items:
		qty = frappe.db.sql("SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s", item.name)[0][0] or 0
		lines.append(f"• {item.item_name}: **{qty:g}** {item.stock_uom or ''}")
	return "\n".join(lines)


def act_item_price(question):
	items, error = _find_item(question)
	if error:
		return error
	price_list = frappe.get_single("Webshop API Settings").default_price_list
	lines = []
	for item in items:
		price = frappe.db.get_value(
			"Item Price",
			{"item_code": item.name, "price_list": price_list, "selling": 1},
			["price_list_rate", "currency"],
			as_dict=True,
		)
		lines.append(
			f"• {item.item_name}: " + (_money(price.price_list_rate, price.currency) if price else "مفيش سعر")
		)
	return "\n".join(lines)


def act_low_stock(_question):
	rows = frappe.db.sql(
		"""
		SELECT i.item_name, COALESCE(SUM(b.actual_qty), 0) AS qty
		FROM `tabItem` i
		JOIN `tabItem Group` g ON g.name = i.item_group AND g.show_in_website = 1
		LEFT JOIN `tabBin` b ON b.item_code = i.name
		WHERE i.disabled = 0
		GROUP BY i.name
		HAVING qty <= 5
		ORDER BY qty ASC
		LIMIT %s
		""",
		MAX_ROWS,
		as_dict=True,
	)
	if not rows:
		return "مفيش أصناف رصيدها قليل."
	return "أصناف رصيدها 5 أو أقل:\n" + "\n".join(f"• {r.item_name}: {r.qty:g}" for r in rows)


def _segment(segment, title):
	rows = frappe.get_list(
		"Customer",
		filters={"rfm_segment": segment},
		fields=["name", "rfm_monetary", "rfm_recency_days"],
		order_by="rfm_monetary desc",
		limit_page_length=MAX_ROWS,
	)
	if not rows:
		return f"مفيش عملاء في شريحة «{segment}» — جرّب تحدّث التقسيم."
	lines = [title]
	for r in rows:
		lines.append(f"• {r.name} — {_money(r.rfm_monetary)} — آخر طلب من {r.rfm_recency_days} يوم")
	return "\n".join(lines)


def act_top_customers(_question):
	return _segment("أبطال", "أفضل العملاء:")


def act_at_risk_customers(_question):
	return _segment("مهمين وبيضيعوا", "عملاء مهمين بعدوا ومحتاجين تواصل:")


def act_webshop_orders(_question):
	rows = frappe.get_list(
		"Sales Order",
		filters={"is_webshop_order": 1, "docstatus": 1},
		fields=["name", "customer", "grand_total", "webshop_payment_status", "transaction_date"],
		order_by="creation desc",
		limit_page_length=MAX_ROWS,
	)
	if not rows:
		return "مفيش طلبات من الموقع لحد دلوقتي."
	lines = [f"آخر {len(rows)} طلب من الموقع:"]
	for r in rows:
		lines.append(f"• {r.name} — {r.customer} — {_money(r.grand_total)} — {r.webshop_payment_status or ''}")
	return "\n".join(lines)


def act_help(_question):
	skills = frappe.get_all(
		"Webshop Agent Skill",
		filters={"enabled": 1, "action": ["!=", "help"]},
		fields=["skill_name", "example_question"],
		order_by="skill_name",
	)
	lines = ["أقدر أجاوبك على:"]
	for s in skills:
		lines.append(f"• {s.skill_name}" + (f" — مثال: «{s.example_question}»" if s.example_question else ""))
	lines.append("\nبشوف اللي مسموحلك تشوفه في ERPNext بس، ومش بنفّذ أي تعديل.")
	return "\n".join(lines)


ACTIONS = {
	"sales_today": act_sales_today,
	"sales_month": act_sales_month,
	"open_orders": act_open_orders,
	"order_status": act_order_status,
	"customer_orders": act_customer_orders,
	"item_stock": act_item_stock,
	"item_price": act_item_price,
	"low_stock": act_low_stock,
	"top_customers": act_top_customers,
	"at_risk_customers": act_at_risk_customers,
	"webshop_orders": act_webshop_orders,
	"help": act_help,
}


# ------------------------------------------------------------------ entry


def answer(question, channel="ERP"):
	"""Shared by the Desk and Telegram. Assumes the session user is already set."""
	s = _settings()
	if not s.get("enabled"):
		return {"ok": False, "reply": "المساعد مش شغّال دلوقتي."}

	question = str(question or "").strip()[:300]
	if len(question) < 2:
		return {"ok": False, "reply": "اكتب سؤالك."}

	words = _tokens(_normalise(question))
	best, best_hits = None, 0
	for skill in frappe.get_all(
		"Webshop Agent Skill",
		filters={"enabled": 1},
		fields=["name", "action", "keywords_ar", "keywords_en", "times_used"],
	):
		hits = max(
			(keyword_score(_normalise(w), words)
			 for w in _words(skill.keywords_ar) + _words(skill.keywords_en)),
			default=0,
		)
		if hits > best_hits:
			best, best_hits = skill, hits

	# Off by default — see Webshop Agent Settings for why.
	use_ai = ai.is_enabled() and _settings().get("ai_for_erp_agent")
	if (not best or best_hits < MIN_SCORE) and use_ai:
		# Keywords came up short. Let the model pick from what we already do.
		options = frappe.get_all(
			"Webshop Agent Skill",
			filters={"enabled": 1},
			fields=["name", "skill_name", "action", "times_used", "example_question"],
			order_by="name",
		)
		labels = [o.example_question or o.skill_name for o in options]
		labels.append("مش موجود في القائمة")
		choice = ai.classify(question, labels)
		# The last option is the escape hatch; picking it means "I don't know".
		if choice and choice < len(labels):
			picked = options[choice - 1]
			if ai.confirm(question, picked.example_question or picked.skill_name):
				best, best_hits = picked, MIN_SCORE

	if not best or best_hits < MIN_SCORE:
		reply = s.get("fallback") or "مش فاهم السؤال."
		_log(question, None, "مفيش مهارة", reply, channel)
		return {"ok": False, "reply": reply}

	handler = ACTIONS.get(best.action)
	if not handler:
		_log(question, best.name, "خطأ", "action not implemented", channel)
		return {"ok": False, "reply": "المهارة دي مش متاحة."}

	try:
		reply = handler(question)
		outcome = "نجح"
	except frappe.PermissionError:
		reply = "مش مسموحلك تشوف البيانات دي."
		outcome = "ممنوع"
	except Exception:
		frappe.log_error(title="Agent skill failed: " + best.action, message=frappe.get_traceback())
		reply = "حصل خطأ وأنا بجيب البيانات. جرّب تاني."
		outcome = "خطأ"

	frappe.db.set_value("Webshop Agent Skill", best.name, "times_used",
	                    (best.times_used or 0) + 1, update_modified=False)
	_log(question, best.name, outcome, reply, channel)
	return {"ok": outcome == "نجح", "skill": best.name, "reply": reply}


@frappe.whitelist()
def ask(question):
	"""Called from the Desk. Never allow_guest — this reads business data."""
	return answer(question, channel="ERP")


@frappe.whitelist()
def get_agent_config():
	s = _settings()
	return {
		"enabled": bool(s.get("enabled")),
		"name": s.get("agent_name") or "المساعد",
		"greeting": s.get("greeting"),
		"can_write": bool(s.get("allow_write")),
		"examples": frappe.get_all(
			"Webshop Agent Skill",
			filters={"enabled": 1, "example_question": ["!=", ""]},
			fields=["example_question"],
			order_by="times_used desc",
			limit=5,
		),
	}
