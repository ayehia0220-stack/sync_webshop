# -*- coding: utf-8 -*-
"""
حملة تجديد الاشتراكات — كل المنطق هنا، و n8n بيبقى ساعي بس.

n8n بينده `get_due_messages` فيرجّعله رسايل جاهزة بالنص وبمدة الانتظار بينها،
يبعتها ويقول `mark_sent`. ورد العميل بيروح لـ `handle_reply` اللي بيقرر الرد
ويحرّك حالة المحادثة. يعني تغيير سعر أو نص أو حد يومي = تعديل مستند في ERPNext.

الحد اليومي والانتظار العشوائي مقصودين: الرقم بيتحظر من الإرسال المتسرّع،
مش من عدد الرسايل على المدى الطويل.
"""
import hashlib
import random
import re
from datetime import datetime

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

STATE_AWAIT_CHOICE = "مستني رده على التذكير"
STATE_AWAIT_PAYMENT = "مستني اختيار طريقة الدفع"
STATE_INTERESTED = "مهتم — اتبعتله الأسعار"
STATE_SUPPORT = "طلب خدمة العملاء"
STATE_REFUSED = "رافض التجديد"

REMINDER_DAYS = [30, 25, 20, 15, 10, 5, 4, 3, 2, 1]


def _settings():
	return frappe.get_single("Renewal Campaign Settings")


def _int(value, default=0):
	try:
		return int(value or default)
	except (TypeError, ValueError):
		return default


def todays_hour(settings=None):
	"""نفس الساعة طول اليوم، وبتتغير من يوم للتاني — مش نمط ثابت ولا عشوائي متقلب."""
	settings = settings or _settings()
	hours = [_int(h) for h in re.split(r"[,\s]+", settings.send_hours or "5,6,7") if h.strip()]
	hours = [h for h in hours if 0 <= h <= 23] or [5, 6, 7]
	seed = int(hashlib.sha256(nowdate().encode()).hexdigest(), 16)
	return hours[seed % len(hours)]


def _normalise_mobile(raw):
	digits = re.sub(r"\D", "", str(raw or ""))
	if digits.startswith("0020"):
		digits = digits[4:]
	if digits.startswith("20") and len(digits) > 10:
		digits = digits[2:]
	if digits.startswith("0"):
		digits = digits[1:]
	return f"20{digits}" if digits else ""


def _money(value):
	"""1040 مش 1,040.00 — الكسور في رسالة واتساب بتوحش الشكل."""
	value = float(value or 0)
	return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"


def _stage(days_left):
	if days_left is None:
		return None
	if days_left > 0:
		return "قبل الانتهاء"
	return "يوم الانتهاء" if days_left == 0 else "بعد الانتهاء"


def _pick_template(stage):
	"""أقل قالب استُخدم — بيوزّع النصوص بدل ما يعيد واحد."""
	rows = frappe.get_all("Renewal Message Template",
	                      filters={"enabled": 1, "stage": stage},
	                      fields=["name", "template_text", "times_used"],
	                      order_by="times_used asc")
	if not rows:
		return None
	fewest = rows[0].times_used or 0
	return random.choice([r for r in rows if (r.times_used or 0) == fewest])


def _fill(text, sub, settings):
	end = getdate(sub.get("end_date")) if sub.get("end_date") else None
	pretty = frappe.utils.formatdate(end, "d MMMM yyyy") if end else ""
	days = sub.get("days_left")
	out = (text or "")
	pairs = {
		"{الاسم}": sub.get("customer_name") or "عميلنا العزيز",
		"{السيريال}": sub.get("imei") or sub.get("name") or "",
		"{تاريخ_الانتهاء}": pretty,
		"{الأيام_المتبقية}": str(abs(days)) if days is not None else "",
		"{سعر_السنة}": _money(settings.price_yearly),
		"{سعر_مدى_الحياة}": _money(settings.price_lifetime),
		"{سنة_النهاية}": str(_int(settings.lifetime_until_year, 2099)),
	}
	for key, value in pairs.items():
		out = out.replace(key, value)
	return out.strip()


def _sent_today():
	return frappe.db.count("Renewal Conversation Log", {
		"direction": "صادر",
		"creation": [">=", f"{nowdate()} 00:00:00"],
	})


def _log(mobile, body, direction, sub_name=None, customer_name=None, state=None):
	doc = frappe.new_doc("Renewal Conversation Log")
	doc.mobile_number = mobile
	doc.customer_name = customer_name
	doc.body = body
	doc.direction = direction
	doc.subscription = sub_name
	doc.state_after = state
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


# ————————————————————— الإرسال —————————————————————

@frappe.whitelist()
def get_due_messages(limit=None, ignore_hour=0, preview=0):
	"""الرسايل المستحقة دلوقتي، جاهزة بالنص وبمدة الانتظار قبل كل واحدة.

	preview=1 بيتجاهل قفل الحملة والساعة — عشان تشوف الرسايل قبل ما تشغّل.
	"""
	settings = _settings()
	preview = _int(preview)
	if not settings.enabled and not preview:
		return {"send": 0, "reason": "الحملة مقفولة من الإعدادات", "messages": []}

	now = now_datetime()
	if not _int(ignore_hour) and not preview:
		if settings.skip_friday and now.weekday() == 4:
			return {"send": 0, "reason": "النهاردة جمعة", "messages": []}
		hour = todays_hour(settings)
		if now.hour != hour:
			return {"send": 0, "reason": f"ساعة النهاردة {hour} والوقت دلوقتي {now.hour}", "messages": []}

	daily_limit = _int(settings.daily_limit, 80)
	already = _sent_today()
	room = max(0, daily_limit - already)
	if limit:
		room = min(room, _int(limit))
	if not room:
		return {"send": 0, "reason": f"اتبعت {already} النهاردة والحد {daily_limit}", "messages": []}

	subs = frappe.get_all(
		"Customer Subscription",
		filters={"renewed": 0, "reminder_active": 1, "customer_refused_to_renew": 0,
		         "mobile_number": ["is", "set"], "end_date": ["is", "set"]},
		fields=["name", "customer_name", "mobile_number", "end_date", "imei",
		        "last_reminder_date", "messages_sent_count", "conversation_state"],
		order_by="end_date asc",
		limit_page_length=2000,
	)

	today = getdate(nowdate())
	min_d = _int(settings.min_delay_seconds, 45)
	max_d = max(min_d, _int(settings.max_delay_seconds, 150))
	pause_every = _int(settings.batch_pause_every, 15)
	pause_minutes = _int(settings.batch_pause_minutes, 10)
	choices = (settings.choices_text or "").strip()

	messages, seen_mobiles = [], set()
	for sub in subs:
		if len(messages) >= room:
			break
		# مستني رد العميل؟ سيبه — إلحاح على حد مستني بيخلّيه يبلّغ عن الرقم
		if sub.conversation_state in (STATE_AWAIT_CHOICE, STATE_AWAIT_PAYMENT, STATE_SUPPORT):
			continue
		# مرة واحدة في اليوم لكل رقم مهما كان عنده أجهزة
		mobile = _normalise_mobile(sub.mobile_number)
		if not mobile or mobile in seen_mobiles:
			continue
		if sub.last_reminder_date and getdate(sub.last_reminder_date) == today:
			continue

		days_left = (getdate(sub.end_date) - today).days
		if days_left > 30:
			continue
		if days_left > 0 and days_left not in REMINDER_DAYS and sub.last_reminder_date:
			continue
		# بعد الانتهاء: كل 10 أيام، مش كل يوم
		if days_left < 0 and sub.last_reminder_date:
			if (today - getdate(sub.last_reminder_date)).days < 10:
				continue

		stage = _stage(days_left)
		template = _pick_template(stage)
		if not template:
			continue

		body = _fill(template.template_text, {**sub, "days_left": days_left}, settings)
		if choices:
			body = f"{body}\n\n{choices}"

		index = len(messages)
		delay = random.randint(min_d, max_d) if index else 0
		if pause_every and index and index % pause_every == 0:
			delay += pause_minutes * 60

		messages.append({
			"subscription": sub.name,
			"customer_name": sub.customer_name,
			"mobile": mobile,
			"jid": f"+{mobile}",
			"days_left": days_left,
			"stage": stage,
			"template": template.name,
			"body": body,
			"delay_seconds": delay,
		})
		seen_mobiles.add(mobile)

	return {
		"send": len(messages),
		"sent_today": already,
		"daily_limit": daily_limit,
		"instance": settings.instance_name or "97",
		"messages": messages,
	}


@frappe.whitelist()
def mark_sent(subscription, template=None, ok=1, body=None, error=None):
	"""n8n بينده دي بعد كل رسالة — نجحت أو فشلت."""
	sub = frappe.get_doc("Customer Subscription", subscription)
	if _int(ok, 1):
		sub.db_set("last_reminder_date", nowdate(), update_modified=False)
		sub.db_set("last_bot_message_at", now_datetime(), update_modified=False)
		sub.db_set("messages_sent_count", _int(sub.messages_sent_count) + 1, update_modified=False)
		sub.db_set("conversation_state", STATE_AWAIT_CHOICE, update_modified=False)
		if template:
			frappe.db.set_value("Renewal Message Template", template, "times_used",
			                    _int(frappe.db.get_value("Renewal Message Template", template, "times_used")) + 1,
			                    update_modified=False)
		_log(_normalise_mobile(sub.mobile_number), body or "", "صادر",
		     sub.name, sub.customer_name, STATE_AWAIT_CHOICE)
	else:
		_log(_normalise_mobile(sub.mobile_number), f"فشل الإرسال: {error}", "صادر",
		     sub.name, sub.customer_name, sub.conversation_state)
	frappe.db.commit()
	return {"ok": True}


# ————————————————————— الرد على العميل —————————————————————

def _find_subscription(mobile):
	target = _normalise_mobile(mobile)
	if not target:
		return None
	rows = frappe.get_all("Customer Subscription",
	                      filters={"mobile_number": ["is", "set"]},
	                      fields=["name", "customer_name", "mobile_number", "conversation_state",
	                              "end_date", "imei", "renewed"],
	                      order_by="modified desc", limit_page_length=4000)
	for row in rows:
		if _normalise_mobile(row.mobile_number) == target:
			return row
	return None


def _choice(text):
	"""يقرا 1 أو 2 سواء اتكتبوا بالعربي أو اللاتيني أو جوه جملة."""
	raw = str(text or "").strip()
	trans = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
	digits = re.findall(r"\d", trans)
	if digits and digits[0] in ("1", "2"):
		return digits[0]
	if re.search(r"\b(نعم|تجديد|جدد|موافق|اه|ايوه|أيوة)\b", raw):
		return "1"
	if re.search(r"\b(لا|مش عايز|الغاء|إلغاء|توقف|بلاش|كفاية)\b", raw):
		return "2"
	return None


def _make_ticket(sub, reason, mobile):
	settings = _settings()
	if not settings.create_ticket:
		return None
	todo = frappe.new_doc("ToDo")
	todo.description = (
		f"<b>عميل محتاج مكالمة — تجديد اشتراك</b><br>"
		f"الاسم: {sub.get('customer_name') or ''}<br>"
		f"الموبايل: {mobile}<br>"
		f"الجهاز: {sub.get('imei') or ''}<br>"
		f"السبب: {reason}"
	)
	todo.priority = "High"
	todo.date = nowdate()
	todo.reference_type = "Customer Subscription"
	todo.reference_name = sub.get("name")
	if settings.ticket_owner:
		todo.allocated_to = settings.ticket_owner
	todo.flags.ignore_permissions = True
	todo.insert()
	frappe.db.commit()
	return todo.name


@frappe.whitelist()
def handle_reply(mobile, text=None):
	"""بيقرر الرد على رسالة واردة ويحرّك حالة المحادثة."""
	settings = _settings()
	sub = _find_subscription(mobile)
	body = str(text or "").strip()
	clean_mobile = _normalise_mobile(mobile)

	if not sub:
		_log(clean_mobile, body, "وارد", state="مش لاقي اشتراك")
		frappe.db.commit()
		return {"reply": None, "action": "unknown_number"}

	_log(clean_mobile, body, "وارد", sub.name, sub.customer_name, sub.conversation_state)
	choice = _choice(body)
	state = sub.conversation_state
	result = {"subscription": sub.name, "customer_name": sub.customer_name, "reply": None,
	          "send_image": None, "action": None}

	# ——— رفض التجديد: مقبول في أي وقت ———
	if choice == "2" and state != STATE_AWAIT_PAYMENT:
		doc = frappe.get_doc("Customer Subscription", sub.name)
		doc.db_set("customer_refused_to_renew", 1, update_modified=False)
		doc.db_set("reminder_active", 0, update_modified=False)
		doc.db_set("conversation_state", STATE_REFUSED, update_modified=False)
		doc.db_set("customer_feedback", "رفض التجديد عبر الواتساب", update_modified=False)
		result.update(reply=settings.optout_reply, action="opted_out")

	# ——— مهتم: نبعت الأسعار ———
	elif choice == "1" and state in (STATE_AWAIT_CHOICE, None, ""):
		text_out = _fill(settings.prices_text, {**sub, "days_left": None}, settings)
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_AWAIT_PAYMENT, update_modified=False)
		result.update(reply=text_out, action="prices_sent")

	# ——— طلب طرق الدفع ———
	elif choice == "1" and state == STATE_AWAIT_PAYMENT:
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_INTERESTED, update_modified=False)
		_make_ticket(sub, "طلب طرق الدفع — متابعة التحصيل", clean_mobile)
		result.update(reply=settings.payment_text, send_image=settings.payment_image,
		              action="payment_sent")

	# ——— عايز يتكلم مع خدمة العملاء ———
	elif choice == "2" and state == STATE_AWAIT_PAYMENT:
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_SUPPORT, update_modified=False)
		_make_ticket(sub, "طلب مكالمة من خدمة العملاء", clean_mobile)
		result.update(reply=settings.support_reply, action="support_requested")

	# ——— أي كلام تاني: تذكرة، ومنبعتش رد آلي ———
	else:
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_SUPPORT, update_modified=False)
		_make_ticket(sub, f"رد بكلام محتاج رد بشري: {body[:120]}", clean_mobile)
		result.update(reply=None, action="handover")

	if result["reply"]:
		_log(clean_mobile, result["reply"], "صادر", sub.name, sub.customer_name, result["action"])
	frappe.db.commit()
	return result


# ————————————————————— لما يدفع —————————————————————

@frappe.whitelist()
def record_payment(subscription, plan="yearly", amount=None, paid=0):
	"""أمر بيع (وقيد دفع لو مفعّل) لما العميل يجدد."""
	settings = _settings()
	sub = frappe.get_doc("Customer Subscription", subscription)

	if not settings.auto_sales_order:
		return {"ok": False, "reason": "أمر البيع التلقائي مقفول من الإعدادات"}

	lifetime = plan == "lifetime"
	rows = settings.lifetime_items if lifetime else settings.yearly_items
	if not rows:
		label = "مدى الحياة" if lifetime else "السنة"
		return {"ok": False, "reason": f"لازم تحدد أصناف خطة {label} في الإعدادات الأول"}

	customer = getattr(sub, "customer", None) or frappe.db.get_value(
		"Customer", {"customer_name": sub.customer_name}, "name")
	if not customer:
		return {"ok": False, "reason": f"مالقيتش عميل باسم {sub.customer_name}"}

	so = frappe.new_doc("Sales Order")
	so.customer = customer
	so.transaction_date = nowdate()
	so.delivery_date = add_days(nowdate(), 1)
	# الافتراضية في إعدادات البيع («مبيعات اوت دور») معطّلة وبتكسر الحفظ،
	# وأسعار أصناف التجديد أصلاً في «ويب سايت».
	price_list = settings.get("price_list") or "ويب سايت"
	if frappe.db.get_value("Price List", price_list, "enabled"):
		so.selling_price_list = price_list
	# حقول إجبارية على أوامر البيع عند دبونو
	for field in ("sales_partner", "cost_center"):
		if settings.get(field):
			so.set(field, settings.get(field))
	if settings.get("sales_person"):
		so.append("sales_team", {"sales_person": settings.get("sales_person"),
		                         "allocated_percentage": 100})
	note = f"تجديد اشتراك {sub.imei or sub.name} — " + ("مدى الحياة" if lifetime else "سنة")
	for row in rows:
		so.append("items", {
			"item_code": row.item_code,
			"qty": row.qty or 1,
			"rate": row.rate if row.rate else None,
			"delivery_date": add_days(nowdate(), 1),
			"description": note,
		})
	so.flags.ignore_permissions = True
	so.insert()

	# لو المالك كتب مبلغ مختلف، نوزّعه على البنود بنفس نسبها
	if amount:
		wanted = float(amount)
		current = float(so.total or 0)
		if current and abs(wanted - current) > 0.01:
			for item in so.items:
				item.rate = round(float(item.rate) * wanted / current, 2)
			so.calculate_taxes_and_totals()
			so.save()

	so.submit()
	out = {"ok": True, "sales_order": so.name, "amount": float(so.grand_total),
	       "items": [i.item_code for i in so.items]}

	if _int(paid) and settings.auto_payment_entry and settings.payment_account:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		pe = get_payment_entry("Sales Order", so.name)
		pe.paid_to = settings.payment_account
		pe.reference_no = f"تجديد-{sub.name}"
		pe.reference_date = nowdate()
		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
		out["payment_entry"] = pe.name

	years = 100 if plan == "lifetime" else 1
	base = getdate(sub.end_date) if sub.end_date and getdate(sub.end_date) > getdate(nowdate()) else getdate(nowdate())
	sub.db_set("renewed", 1, update_modified=False)
	sub.db_set("renewed_date", nowdate(), update_modified=False)
	sub.db_set("end_date", add_days(base, 365 * years), update_modified=False)
	sub.db_set("conversation_state", "", update_modified=False)
	frappe.db.commit()
	return out


def preview_messages(count=4):
	"""يطبع الرسايل اللي هتتبعت — للتشغيل من bench execute قبل ما تفعّل الحملة."""
	out = get_due_messages(limit=count, preview=1)
	print(f"مستحق دلوقتي: {out['send']} | اتبعت النهاردة: {out.get('sent_today')} "
	      f"| الحد اليومي: {out.get('daily_limit')} | الرقم: {out.get('instance')}")
	if out.get("reason"):
		print("السبب:", out["reason"])
	for m in out["messages"]:
		print("\n" + "=" * 60)
		print(f"{m['customer_name']} | {m['jid']} | متبقي {m['days_left']} يوم "
		      f"| انتظار {m['delay_seconds']} ثانية | {m['stage']}")
		print("-" * 60)
		print(m["body"])
	return out["send"]


@frappe.whitelist()
def status():
	"""لقطة سريعة لحالة الحملة."""
	settings = _settings()
	return {
		"enabled": bool(settings.enabled),
		"instance": settings.instance_name,
		"todays_hour": todays_hour(settings),
		"sent_today": _sent_today(),
		"daily_limit": _int(settings.daily_limit, 80),
		"templates": frappe.db.count("Renewal Message Template", {"enabled": 1}),
		"pending_subscriptions": frappe.db.count("Customer Subscription", {
			"renewed": 0, "reminder_active": 1, "customer_refused_to_renew": 0}),
		"opted_out": frappe.db.count("Customer Subscription", {"customer_refused_to_renew": 1}),
		"awaiting_reply": frappe.db.count("Customer Subscription", {
			"conversation_state": ["in", [STATE_AWAIT_CHOICE, STATE_AWAIT_PAYMENT]]}),
	}
