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
STATE_ASK_REASON = "مستني سبب الإيقاف"
STATE_PAID = "قال إنه دفع"

REMINDER_DAYS = [15, 10, 3, 2, 1, 0]
AFTER_EXPIRY_EVERY = 3
MAX_SEND_FAILURES = 3   # بعد كام فشل نوقف الرقم ونحوّله لمراجعة
MULTI_STAGE = "أجهزة متعددة"   # بعد الانتهاء بيتبعت كل كام يوم


def _settings():
	return frappe.get_single("Renewal Campaign Settings")


def _int(value, default=0):
	try:
		return int(value or default)
	except (TypeError, ValueError):
		return default


SYSTEM_ERRORS = (
	"connection closed", "connection refused", "econnreset", "timeout",
	"timed out", "socket", "internal server error", "500", "502", "503",
	"bad gateway", "instance not connected", "close",
)


def _our_fault(error):
	"""الفشل ده عطل عندنا ولا الرقم نفسه وحش؟

	انقطاع Evolution بيجي أرقام مختلفة كل مرة — لو عددناه على العملاء
	هنوقف أرقام سليمة. الرقم الوحش بيفشل هو بالذات كل مرة.
	"""
	text = str(error or "").lower()
	return any(sign in text for sign in SYSTEM_ERRORS)


def _truthy(value, default=True):
	"""قراءة صريحة لقيمة نجاح/فشل جاية من n8n (ممكن تكون 0 أو "0" أو False).

	متستخدمش `_int(value, 1)` هنا: هي بتعمل `int(value or 1)` فالصفر
	بيتحوّل لواحد — يعني الفشل يتقرا نجاح.
	"""
	if value is None or value == "":
		return default
	if isinstance(value, str):
		return value.strip().lower() not in ("0", "false", "no", "none", "لا")
	return bool(value)


def send_hours(settings=None):
	"""ساعات الشغل المسموح فيها الإرسال. بتقبل "7-23" أو "7,8,9"."""
	settings = settings or _settings()
	raw = (settings.send_hours or "7-23").strip()
	hours = set()
	for part in re.split(r"[,\s]+", raw):
		if not part:
			continue
		if "-" in part:
			try:
				a, b = [_int(x) for x in part.split("-", 1)]
			except ValueError:
				continue
			hours.update(range(min(a, b), max(a, b) + 1))
		else:
			hours.add(_int(part))
	hours = sorted(h for h in hours if 0 <= h <= 23)
	return hours or list(range(7, 24))


def todays_hour(settings=None):
	"""متسابة للتوافق — بترجّع أول ساعة شغل."""
	return send_hours(settings)[0]


def hourly_quota(settings=None):
	"""الباقي من الحد اليومي موزّع على ساعات الشغل الباقية.

	القسمة الصحيحة (50 // 17 = 2) كانت بتضيّع الباقي فالحد اليومي
	ما كانش بيتحقق أبدًا. دلوقتي بنحسب الباقي فعليًا على الساعات
	الفاضلة، فلو فاتت ساعة بتتعوّض في اللي بعدها.
	"""
	import math
	settings = settings or _settings()
	hours = send_hours(settings)
	daily = _int(settings.daily_limit, 50)
	current = now_datetime().hour
	left = [h for h in hours if h >= current]
	remaining = max(0, daily - _sent_today())
	if not left or not remaining:
		return 0 if not remaining else max(1, daily // max(1, len(hours))), len(hours)
	return max(1, math.ceil(remaining / len(left))), len(hours)


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


# كل توقيت له نبرة مختلفة — التدرّج ده هو اللي بيخلي الرسايل مش مكررة
STAGE_BY_DAYS = {
	15: "قبل 15 يوم",
	10: "قبل 10 أيام",
	3: "قبل 3 أيام",
	2: "قبل يومين",
	1: "آخر يوم",
	0: "يوم الانتهاء",
}


def _stage(days_left):
	if days_left is None:
		return None
	if days_left in STAGE_BY_DAYS:
		return STAGE_BY_DAYS[days_left]
	if days_left > 0:
		# مش نقطة تذكير بالظبط — ناخد أقرب مرحلة أكبر منها
		nearest = min((d for d in STAGE_BY_DAYS if d >= days_left), default=15)
		return STAGE_BY_DAYS[nearest]
	return "بعد الانتهاء"


def _pick_template(stage, used=None):
	"""أقل قالب استُخدم — بيوزّع النصوص بدل ما يعيد واحد."""
	rows = frappe.get_all("Renewal Message Template",
	                      filters={"enabled": 1, "stage": stage},
	                      fields=["name", "template_text", "times_used"],
	                      order_by="times_used asc")
	if not rows:
		return None
	# داخل الدفعة الواحدة العدّاد لسه ما اتحدّثش، فبنستبعد اللي اتاخد في نفس
	# الدفعة — من غير كده الدفعة كلها بتطلع بنفس النص.
	fresh = [r for r in rows if r.name not in (used or set())]
	pool = fresh or rows
	fewest = pool[0].times_used or 0
	return random.choice([r for r in pool if (r.times_used or 0) == fewest])


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
		"{عدد_الأجهزة}": str(sub.get("device_count") or 1),
	}
	for key, value in pairs.items():
		out = out.replace(key, value)
	return out.strip()


def _sent_today():
	return frappe.db.count("Renewal Conversation Log", {
		"direction": "صادر",
		"creation": [">=", f"{nowdate()} 00:00:00"],
	})


def _sent_this_hour():
	"""الساعة نفسها (من :00)، مش آخر 60 دقيقة.

	النافذة المتحركة كانت بتتعارض مع جدولة n8n على الدقيقة :05 —
	رسايل 7:05 تفضل محسوبة لحد 8:05، فالساعة اللي بعدها تتسكّر.
	"""
	start = now_datetime().replace(minute=0, second=0, microsecond=0)
	return frappe.db.count("Renewal Conversation Log", {
		"direction": "صادر",
		"creation": [">=", start],
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
def instance_health(instance=None, alert=1):
	"""هل رقم الحملة قادر يبعت فعلاً؟

	`connectionState` بيكدب: فضل يقول `open` والجلسة ميتة وكل محاولة
	إرسال بتموت بـ Connection Closed. الفحص الحقيقي هو استعلام
	`whatsappNumbers` — لو رجع 200 يبقى الاتصال حي فعلاً.
	"""
	import json
	import requests
	settings = _settings()
	name = str(instance or settings.instance_name or "97")
	content = frappe.get_single("Webshop Content Settings")
	url = (content.get("evolution_url") or "http://localhost:8080").rstrip("/")
	key = content.get_password("evolution_api_key", raise_exception=False) or ""

	try:
		r = requests.post(f"{url}/chat/whatsappNumbers/{name}",
		                  headers={"apikey": key, "Content-Type": "application/json"},
		                  data=json.dumps({"numbers": ["201114021275"]}),
		                  timeout=25)
		ok = r.status_code == 200
		reason = "" if ok else f"HTTP {r.status_code}: {r.text[:120]}"
	except Exception as exc:
		ok, reason = False, str(exc)[:150]

	if not ok and _int(alert, 1):
		_alert_instance_down(name, reason, url, key)
	return {"instance": name, "ok": 1 if ok else 0, "reason": reason}


def _alert_instance_down(name, reason, url, key):
	"""تنبيه المالك — من رقم تاني، لأن الرقم الواقع مش هيبعت لنفسه.

	وبنبعت مرة كل ساعة بس عشان ما نغرقش الموبايل بتنبيهات.
	"""
	import json
	import requests
	stamp = frappe.utils.now_datetime().strftime("%Y-%m-%d %H")
	flag = f"alert_down_{name}"
	if frappe.db.get_default(flag) == stamp:
		return False
	frappe.db.set_default(flag, stamp)

	settings = _settings()
	targets = []
	for raw in str(settings.get("owner_alert_numbers") or "").split(","):
		n = _normalise_mobile(raw)
		if n and n not in targets:
			targets.append(n)
	if not targets:
		return False

	# رقم تاني شغال يبعت منه — الرقم الواقع مش هينفع
	sender = None
	try:
		r = requests.get(f"{url}/instance/fetchInstances",
		                 headers={"apikey": key}, timeout=20)
		for row in (r.json() if isinstance(r.json(), list) else [r.json()]):
			inst = row.get("instance", row)
			nm = str(inst.get("instanceName") or inst.get("name") or "")
			state = inst.get("connectionStatus") or inst.get("state")
			if nm and nm != name and state == "open":
				sender = nm
				break
	except Exception:
		pass
	if not sender:
		frappe.log_error(f"الرقم {name} واقع ومفيش رقم تاني يبعت منه", "instance_down")
		return False

	text = (f"🚨 *رقم الحملة {name} مش قادر يبعت*\n\n"
	        f"السبب: {reason}\n\n"
	        f"الحملة اتوقفت مؤقتًا عشان الرسايل ما تضيعش.\n"
	        f"الحل غالبًا: إعادة تشغيل حاوية Evolution.")
	for number in targets:
		try:
			requests.post(f"{url}/message/sendText/{sender}",
			              headers={"apikey": key, "Content-Type": "application/json"},
			              data=json.dumps({"number": number, "text": text},
			                              ensure_ascii=False).encode("utf-8"),
			              timeout=20)
		except Exception:
			pass
	return True


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
		allowed = send_hours(settings)
		if now.hour not in allowed:
			return {"send": 0,
			        "reason": f"برّه ساعات الشغل ({allowed[0]}–{allowed[-1]}) — الساعة دلوقتي {now.hour}",
			        "messages": []}

	daily_limit = _int(settings.daily_limit, 50)
	already = _sent_today()
	room = max(0, daily_limit - already)

	# نصيب الساعة الواحدة — عشان الإرسال يتوزّع مش يتكتّل
	if not _int(ignore_hour) and not preview:
		quota, _hours = hourly_quota(settings)
		room = min(room, max(0, quota - _sent_this_hour()))
	if limit:
		room = min(room, _int(limit))
	if not room:
		return {"send": 0,
		        "reason": f"خلص نصيب الساعة دي (اتبعت {already} النهاردة من {daily_limit})",
		        "messages": []}

	# الجلسة بتموت وتفضل تقول open — نتأكد قبل ما نسلّم رسايل لـ n8n
	if not _int(preview):
		health = instance_health()
		if not health["ok"]:
			return {"send": 0,
			        "reason": f"رقم الحملة مش قادر يبعت: {health['reason'][:80]}",
			        "messages": []}

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

	messages, seen_mobiles, used_templates = [], set(), set()
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
		if days_left > 15:
			continue   # لسه بدري — مفيش داعي نزعج العميل
		if days_left >= 0:
			# نقطة تذكير محددة؛ ولو العميل جديد ولسه ما اتبعتلوش، نبعت مرة
			if days_left not in REMINDER_DAYS and sub.last_reminder_date:
				continue
		elif sub.last_reminder_date:
			# بعد الانتهاء: كل 3 أيام
			if (today - getdate(sub.last_reminder_date)).days < AFTER_EXPIRY_EVERY:
				continue

		# نفس الرقم ممكن يكون معاه كذا جهاز — بنجمّعهم في رسالة واحدة بدل
		# ما ياخد رسالة عن جهاز واحد كل يوم ويحتاج شهور يعرف عن كلهم.
		siblings = [s for s in subs
		            if _normalise_mobile(s.mobile_number) == mobile
		            and s.name != sub.name
		            and s.end_date and (getdate(s.end_date) - today).days <= 15]

		# الرسالة المجمّعة ليها نصوص خاصة بتتكلم بصيغة الجمع من أول سطر
		stage = MULTI_STAGE if siblings else _stage(days_left)
		template = _pick_template(stage, used_templates)
		if not template:
			stage = _stage(days_left)
			template = _pick_template(stage, used_templates)
		if not template:
			continue
		used_templates.add(template.name)

		body = _fill(template.template_text,
		             {**sub, "days_left": days_left,
		              "device_count": len(siblings) + 1}, settings)
		if siblings:
			lines = [f"• {sub.imei or sub.name} — " +
			         (f"باقي {days_left} يوم" if days_left > 0 else
			          "بينتهي النهاردة" if days_left == 0 else f"منتهي من {abs(days_left)} يوم")]
			for s in siblings[:9]:
				d = (getdate(s.end_date) - today).days
				lines.append(f"• {s.imei or s.name} — " +
				             (f"باقي {d} يوم" if d > 0 else
				              "بينتهي النهاردة" if d == 0 else f"منتهي من {abs(d)} يوم"))
			extra = len(siblings) - 9
			if extra > 0:
				lines.append(f"• وكمان {extra} جهاز")
			body += "\n\nالأجهزة:\n" + "\n".join(lines)
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
	if _truthy(ok):
		# نجحت — نصفّر العدّاد عشان فشل قديم متفرّق ميوقفش الرقم
		if _int(sub.get("send_failures")):
			sub.db_set("send_failures", 0, update_modified=False)
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
		# رقم غلط أو مش على واتساب — بعد 3 محاولات نوقفه بدل ما يفضل
		# ياكل من الحصة اليومية كل ساعة من غير فايدة
		if _our_fault(error):
			# عطل مؤقت عندنا — مش ذنب العميل، والرسالة هتتعاد الساعة الجاية
			_log(_normalise_mobile(sub.mobile_number),
			     f"عطل مؤقت في الإرسال (مش محسوب على العميل): {error}", "صادر",
			     sub.name, sub.customer_name, sub.conversation_state)
			frappe.db.commit()
			return {"ok": True, "counted": False}

		fails = _int(sub.get("send_failures")) + 1
		sub.db_set("send_failures", fails, update_modified=False)
		sub.db_set("last_send_error", str(error or "")[:500], update_modified=False)
		if fails >= MAX_SEND_FAILURES:
			sub.db_set("reminder_active", 0, update_modified=False)
			sub.db_set("needs_number_review", 1, update_modified=False)
		_log(_normalise_mobile(sub.mobile_number),
		     f"فشل الإرسال ({fails}/{MAX_SEND_FAILURES}): {error}", "صادر",
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
	"""يقرا من 1 لـ 4 سواء اتكتبوا بالعربي أو اللاتيني أو جوه جملة."""
	raw = str(text or "").strip()
	trans = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

	# رقم طويل = سيريال أو موبايل، مش اختيار. العميل اللي بعت سيريال
	# جهازه كان بيتقرا «3» ويتلغي اشتراكه.
	if re.search(r"\d{5,}", trans):
		return None

	# الاختيار لازم يكون الرسالة نفسها: «2» أو «٢.» أو «2 شكرا»
	compact = re.sub(r"[\s\.\-،,:؛!؟\)\(]+", " ", trans).strip()
	first = compact.split(" ")[0] if compact else ""
	if first in ("1", "2", "3", "4") and len(compact) <= 12:
		return first
	# ناس كتير بتكتب كلام مش رقم — بنفهم النية.
	# الرفض الأول: «مش عايز اجدد» فيها «اجدد»، فلو بدأنا بالتجديد
	# هنقراها غلط ونبعتله طرق دفع وهو رافض.
	if re.search(r"(مش عايز|مش محتاج|لا شكرا|لأ|الغاء|إلغاء|الغي|"
	             r"توقف|بطل|بلاش|كفاية|متبعتش|مش مهتم)", raw):
		return "3"
	if re.search(r"(اتصل|مكالمة|مكالمه|كلمني|اتكلم|حد يكلمني|خدمة العملاء)", raw):
		return "4"
	if re.search(r"(السعر|الاسعار|الأسعار|بكام|كام|التكلفة|الفلوس)", raw):
		return "2"
	if re.search(r"(نعم|تجديد|جدد|موافق|ايوه|أيوة|تمام|ماشي)", raw):
		return "1"
	return None


def _meant_optout(mobile):
	"""هل آخر رسالة بعتناها للعميل ده كانت بتقوله «2 = بطّل رسايل»؟

	القايمة القديمة كانت رقمين (2 = إيقاف)، والجديدة أربعة (3 = إيقاف).
	عميل استلم القديمة ورد بـ 2 النهاردة قصده يوقف الرسايل مش يشوف
	الأسعار — ولو فهمناه غلط هنبعتله رسايل وهو طالب يبطّلها.
	"""
	rows = frappe.get_all("Renewal Conversation Log",
	                      filters={"mobile_number": mobile, "direction": "صادر"},
	                      fields=["body"], order_by="creation desc", limit=1)
	if not rows:
		return False
	return "2 لو مش عايز" in (rows[0].body or "")


def _ticket_unknown(mobile, body):
	"""تذكرة لرقم مش في الاشتراكات — عشان محدش يفضل مستني رد مايجيش."""
	settings = _settings()
	if not settings.get("create_ticket"):
		return None
	# مرة واحدة في اليوم للرقم الواحد، مش تذكرة لكل رسالة
	stamp = frappe.utils.nowdate()
	if frappe.db.exists("ToDo", {"reference_type": "Renewal Campaign Settings",
	                             "reference_name": f"{mobile}-{stamp}"}):
		return None
	todo = frappe.new_doc("ToDo")
	todo.description = (
		f"<b>رسالة واتساب من رقم مش في الاشتراكات</b><br>"
		f"الموبايل: {mobile}<br>"
		f"الرسالة: {frappe.utils.escape_html(str(body or '')[:300])}")
	todo.priority = "High"
	todo.date = stamp
	todo.reference_type = "Renewal Campaign Settings"
	todo.reference_name = f"{mobile}-{stamp}"
	if settings.get("ticket_owner"):
		todo.allocated_to = settings.ticket_owner
	todo.flags.ignore_permissions = True
	todo.insert()
	return todo.name


INTENT_MULTI = r"(كل جهاز|لكل جهاز|للجهاز الواحد|الاربعه|الأربعة|"\
              r"اكتر من جهاز|أكتر من جهاز|اكثر من جهاز|كل الاجهزة|كل الأجهزة|"\
              r"الاجهزة كلها|جهازين|تلات اجهزة|٣ اجهزة)"
INTENT_IGNORED = r"(مردتيش|مردتوش|محدش رد|مش بترد|مفيش رد|مستني رد|"\
                 r"بقالي كتير|مش بيردوا)"


INTENT_EXPIRY = r"(هينتهي|هاينتهي|ينتهي|بينتهي|هيخلص|بيخلص|امته|إمتى|امتى|"\
                r"تاريخ الانتهاء|فاضل كام|باقي كام|لسه كام)"
INTENT_PAID = r"(دفعت|حولت|حوّلت|حولتلك|بعتلك الصورة|بعتلك صورة|بعثت لك صوره|"\
              r"بعتلك الإيصال|تم التحويل|تم الدفع|حولت الفلوس)"
INTENT_CHURN = r"(جددت مع|جدات مع|اشتركت مع|مع شركة|شركة تانية|شركه تانيه|"\
               r"غيرت الشركة|سبت الشركة)"
INTENT_TROUBLE = r"(مش شغال|مش بيشتغل|ما اشتغلش|مااشتغلش|واقف|عطلان|بايظ|"\
                 r"مش بيرسل|مش ظاهر|اتسرق|سرقه|سرقة|ضاع|مش لاقي العربية)"


def _smart_reply(sub, body, mobile, settings):
	"""يرد على الأسئلة الشائعة بدل ما يحوّل كل حاجة لموظف.

	بيرجّع dict فيه الرد والإجراء، أو None لو مفيش حاجة مفهومة.
	"""
	text = str(body or "")

	# «السعر ده لكل جهاز؟» — سؤال متكرر وإجابته عندنا بالظبط
	if re.search(INTENT_MULTI, text):
		mine = frappe.get_all(
			"Customer Subscription",
			filters={"mobile_number": sub.get("mobile_number"), "renewed": 0,
			         "customer_refused_to_renew": 0},
			fields=["imei", "end_date"], order_by="end_date asc",
			limit_page_length=20)
		count = len(mine) or 1
		yearly = _money(settings.price_yearly)
		total = _money(_int(settings.price_yearly) * count)
		lines = [f"السعر ده **لكل جهاز**، مش للكل مع بعض 🙏", ""]
		lines.append(f"عندك {count} جهاز:")
		for row in mine[:10]:
			end = getdate(row.end_date) if row.end_date else None
			days = (end - getdate(nowdate())).days if end else None
			when = ("" if days is None else
			        f" — باقي {days} يوم" if days > 0 else
			        " — بينتهي النهاردة" if days == 0 else
			        f" — منتهي من {abs(days)} يوم")
			lines.append(f"• {row.imei or ''}{when}")
		if count > 10:
			lines.append(f"• وكمان {count - 10} جهاز")
		lines.append("")
		lines.append(f"سنة لكل جهاز: {yearly} جنيه")
		if count > 1:
			lines.append(f"إجمالي {count} أجهزة: {total} جنيه")
		lines.append("")
		lines.append(settings.get("choices_text") or "")
		return {"reply": "\n".join(lines).strip(), "action": "multi_device_answered",
		        "urgent": False}

	# عميل زعلان إن محدش رد عليه — ده يستاهل إشعار فوري
	if re.search(INTENT_IGNORED, text):
		return {"reply": "معلش والله 🙏 حصل تأخير، وأنا حوّلتك لخدمة العملاء "
		                 "وهيكلموك حالًا.",
		        "action": "complaint_no_reply", "urgent": True,
		        "reason": f"😞 عميل زعلان إن محدش رد عليه: {text[:110]}"}

	# «امتى بينتهي؟» — إجابة موجودة عندنا، مش محتاجة موظف
	if re.search(INTENT_EXPIRY, text):
		end = getdate(sub.get("end_date")) if sub.get("end_date") else None
		if end:
			days = (end - getdate(nowdate())).days
			pretty = frappe.utils.formatdate(end, "d MMMM yyyy")
			if days > 0:
				when = f"باقي {days} يوم — بينتهي يوم {pretty}"
			elif days == 0:
				when = f"بينتهي النهاردة ({pretty})"
			else:
				when = f"منتهي من {abs(days)} يوم — كان يوم {pretty}"
			reply = (f"اشتراك جهاز {sub.get('imei') or ''} {when}.\n\n"
			         + (settings.get("choices_text") or ""))
			return {"reply": reply.strip(), "action": "expiry_answered",
			        "urgent": False}

	# «أنا دفعت» — ده بلاغ دفع، مش كلام عادي
	if re.search(INTENT_PAID, text):
		out = report_payment(mobile, note=text)
		return {"reply": out.get("reply"), "action": "payment_reported",
		        "urgent": False, "handled": True}

	# «جددت مع شركة تانية» — نوقف الرسايل بدل ما نفضل نزعّجه
	if re.search(INTENT_CHURN, text):
		frappe.db.set_value("Customer Subscription", sub.name, {
			"customer_refused_to_renew": 1,
			"reminder_active": 0,
			"conversation_state": STATE_REFUSED,
			"customer_feedback": f"جدد مع جهة تانية: {text[:200]}",
		}, update_modified=False)
		_make_ticket(sub, f"عميل جدد مع شركة تانية: {text[:150]}", mobile)
		return {"reply": "تمام، شكرًا لصراحتك 🌹 وقّفنا رسايل التجديد. "
		                 "لو احتجتنا في أي وقت إحنا موجودين.",
		        "action": "churned", "urgent": False, "handled": True}

	# عطل أو سرقة — ده بيعطّل العميل فعلاً، يستاهل إشعار فوري
	if re.search(INTENT_TROUBLE, text):
		return {"reply": "وصلتنا مشكلتك ✅ حوّلتها للفني حالًا وهنكلمك في أقرب وقت.",
		        "action": "trouble_reported", "urgent": True,
		        "reason": f"🔧 مشكلة في الجهاز: {text[:120]}"}

	return None


def _flag_needs_call(sub, reason, mobile, urgent=True):
	"""علامة على الاشتراك + تذكرة، والإشعار الفوري للحاجات المهمة بس.

	`urgent=False` معناها: سجّل التذكرة عشان محدش يضيع، بس متبعتش
	واتساب. الكلام العادي اللي البوت مش فاهمه مش سبب كافي إن موبايل
	المالك يرن.
	"""
	frappe.db.set_value("Customer Subscription", sub.name, {
		"conversation_state": STATE_SUPPORT,
		"needs_call": 1,
		"needs_call_since": now_datetime(),
	}, update_modified=False)
	_make_ticket(sub, reason, mobile)
	if urgent:
		_alert_support(sub, mobile, reason)


def _alert_support(sub, mobile, reason):
	"""رسالة واتساب لخدمة العملاء إن فيه عميل مستني مكالمة.

	التذكرة في ERPNext لوحدها مش كفاية — محدش بيفتح ERPNext كل شوية.
	"""
	settings = _settings()

	# إشعار واحد للعميل الواحد في اليوم — العميل اللي بيكتب جملته على
	# خمس رسايل مكانش ينفع يبعت خمس إشعارات.
	flag = f"alert_sup_{sub.get('name')}"
	if frappe.db.get_default(flag) == nowdate():
		return False
	frappe.db.set_default(flag, nowdate())

	# التنبيه بيروح لخدمة العملاء + المالك وضحى (owner_alert_numbers)
	targets = []
	for raw in [settings.get("support_alert_number")] + \
	           str(settings.get("owner_alert_numbers") or "").split(","):
		n = _normalise_mobile(raw)
		if n and n not in targets:
			targets.append(n)
	if not targets:
		return False

	text = (
		"📞 *عميل محتاج مكالمة*\n\n"
		f"الاسم: {sub.get('customer_name') or '—'}\n"
		f"الموبايل: {mobile}\n"
		f"الجهاز: {sub.get('imei') or '—'}\n"
		f"السبب: {reason}\n\n"
		f"https://erp1.dpono.com/app/customer-subscription/{sub.get('name')}"
	)
	try:
		import json as _json
		import requests
		content = frappe.get_single("Webshop Content Settings")
		url = (content.get("evolution_url") or "http://localhost:8080").rstrip("/")
		key = content.get_password("evolution_api_key", raise_exception=False)
		if not key:
			return False
		sent = 0
		for number in targets:
			r = requests.post(
				f"{url}/message/sendText/{settings.instance_name or '97'}",
				headers={"apikey": key, "Content-Type": "application/json"},
				data=_json.dumps({"number": number, "text": text}, ensure_ascii=False).encode("utf-8"),
				timeout=20)
			sent += 1 if r.status_code < 300 else 0
		return sent > 0
	except Exception:
		frappe.log_error(frappe.get_traceback(), "_alert_support")
		return False


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
		# رقم مش في قاعدة الاشتراكات — قبل كده كان بياخد صمت تام.
		# عميل بيكلمنا لازم يلاقي حد، حتى لو مش عارفينه.
		_log(clean_mobile, body, "وارد", state="مش لاقي اشتراك")
		_ticket_unknown(clean_mobile, body)
		frappe.db.commit()
		return {"reply": (settings.get("unknown_reply") or
		                  "وصلتنا رسالتك ✅ حد من خدمة العملاء هيرد عليك حالًا 🌹"),
		        "action": "unknown_number"}

	_log(clean_mobile, body, "وارد", sub.name, sub.customer_name, sub.conversation_state)
	choice = _choice(body)
	state = sub.conversation_state
	result = {"subscription": sub.name, "customer_name": sub.customer_name, "reply": None,
	          "send_image": None, "action": None}

	# ——— مستني منه سبب الإيقاف: أي كلام يتسجل كسبب ———
	if state == STATE_ASK_REASON:
		frappe.db.set_value("Customer Subscription", sub.name, {
			"optout_reason": body[:500] or "مردش بسبب",
			"conversation_state": STATE_REFUSED,
		}, update_modified=False)
		_log_optout_reason(sub, clean_mobile, body)
		result.update(reply=settings.get("optout_thanks") or
		              "شكرًا على وقتك 🌹 ملاحظتك وصلت للإدارة.",
		              action="optout_reason_saved")
		if result["reply"]:
			_log(clean_mobile, result["reply"], "صادر", sub.name,
			     sub.customer_name, result["action"])
		frappe.db.commit()
		return result

	# عميل لسه شايف القايمة القديمة (2 = بطّل رسايل) — نحترم قصده
	if choice == "2" and _meant_optout(clean_mobile):
		choice = "3"

	# ——— 1: عايز يجدد — نبعت طرق الدفع على طول ———
	if choice == "1":
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_INTERESTED, update_modified=False)
		_make_ticket(sub, "طلب التجديد — متابعة التحصيل", clean_mobile)
		result.update(reply=_fill(settings.payment_text, {**sub, "days_left": None}, settings),
		              send_image=settings.payment_image, action="payment_sent")

	# ——— 2: عايز يعرف الأسعار ———
	elif choice == "2":
		text_out = _fill(settings.prices_text, {**sub, "days_left": None}, settings)
		frappe.db.set_value("Customer Subscription", sub.name, "conversation_state",
		                    STATE_AWAIT_PAYMENT, update_modified=False)
		result.update(reply=text_out, action="prices_sent")

	# ——— 3: مش عايز رسايل تانية ———
	elif choice == "3":
		# بنوقف التذكيرات **فورًا**، والسؤال عن السبب بعد كده اختياري.
		# لو قلبناها ونستنى رده الأول، ممكن نفضل نبعتله وهو طالب نبطّل.
		doc = frappe.get_doc("Customer Subscription", sub.name)
		doc.db_set("customer_refused_to_renew", 1, update_modified=False)
		doc.db_set("reminder_active", 0, update_modified=False)
		doc.db_set("conversation_state", STATE_ASK_REASON, update_modified=False)
		doc.db_set("customer_feedback", "طلب إيقاف رسايل التجديد", update_modified=False)
		result.update(reply=settings.optout_reply, action="opted_out")

	# ——— 4: عايز مكالمة من خدمة العملاء ———
	elif choice == "4":
		_flag_needs_call(sub, "طلب مكالمة من خدمة العملاء", clean_mobile)
		result.update(reply=settings.support_reply, action="support_requested")

	# ——— أي كلام تاني: تذكرة، ومنبعتش رد آلي ———
	else:
		smart = _smart_reply(sub, body, clean_mobile, settings)
		if smart:
			if not smart.get("handled"):
				if smart.get("urgent"):
					_flag_needs_call(sub, smart.get("reason") or body[:120],
					                 clean_mobile, urgent=True)
			result.update(reply=smart.get("reply"), action=smart["action"])
		else:
			# مش فاهمين — تذكرة عشان محدش يضيع، من غير إشعار مزعج
			_flag_needs_call(sub, f"رد بكلام محتاج رد بشري: {body[:120]}",
			                 clean_mobile, urgent=False)
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


@frappe.whitelist()
def send_payment_image(mobile, brand="gps"):
	"""يبعت صورة طرق الدفع للعميل.

	الصورة بتتبعت من ERPNext مباشرة عبر Evolution عشان تشتغل سواء كانت
	مرفوعة عامة أو خاصة — n8n مش هيقدر يقرا الملفات الخاصة.
	"""
	settings = _settings()
	# نشاطين ببراند ورقم خدمة عملاء مختلف — كل عميل يشوف صورة نشاطه
	field = "payment_image_coffee" if str(brand).lower() in ("coffee", "بن", "قهوة") else "payment_image"
	image = settings.get(field) or settings.get("payment_image")
	if not image:
		return {"sent": 0, "reason": "مفيش صورة مرفوعة في الإعدادات"}

	sub = _find_subscription(mobile)
	caption = _fill(settings.payment_text or "",
	                {**(sub or {}), "days_left": None}, settings)
	return _send_media(mobile, image, caption)


def _send_media(mobile, image, caption=""):
	"""بيبعت صورة من ERPNext لواتساب عبر Evolution."""
	settings = _settings()
	number = _normalise_mobile(mobile)
	if not number:
		return {"sent": 0, "reason": f"رقم مش مظبوط: {mobile}"}

	import base64, json as _json, mimetypes, os
	import requests

	path = frappe.get_site_path(image.lstrip("/").replace("private/files", "private/files")
	                            if image.startswith("/private") else "public" + image)
	if not os.path.exists(path):
		row = frappe.db.get_value("File", {"file_url": image}, ["name"], as_dict=True)
		if row:
			path = frappe.get_doc("File", row.name).get_full_path()
	if not os.path.exists(path):
		return {"sent": 0, "reason": f"مالقيتش الملف: {image}"}

	with open(path, "rb") as fh:
		encoded = base64.b64encode(fh.read()).decode()

	content = frappe.get_single("Webshop Content Settings")
	url = (content.get("evolution_url") or "http://localhost:8080").rstrip("/")
	key = content.get_password("evolution_api_key", raise_exception=False)
	instance = settings.instance_name or "97"
	if not key:
		return {"sent": 0, "reason": "مفيش مفتاح Evolution في إعدادات محتوى الموقع"}

	payload = {
		"number": number,
		"mediatype": "image",
		"mimetype": mimetypes.guess_type(path)[0] or "image/jpeg",
		"media": encoded,
		"fileName": os.path.basename(path),
		"caption": caption or "",
	}
	try:
		r = requests.post(f"{url}/message/sendMedia/{instance}",
		                  headers={"apikey": key, "Content-Type": "application/json"},
		                  data=_json.dumps(payload, ensure_ascii=False).encode("utf-8"),
		                  timeout=45)
		ok = r.status_code < 300
		if not ok:
			frappe.log_error(r.text[:400], "_send_media")
		return {"sent": 1 if ok else 0, "status": r.status_code}
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "_send_media")
		return {"sent": 0, "reason": str(exc)[:150]}


def _log_optout_reason(sub, mobile, reason):
	"""سبب الإيقاف مهم للإدارة — بنعمله تذكرة عشان حد يقراه."""
	settings = _settings()
	if not settings.get("create_ticket"):
		return None
	todo = frappe.new_doc("ToDo")
	todo.description = (
		f"<b>عميل أوقف رسايل التجديد</b><br>"
		f"الاسم: {sub.get('customer_name') or ''}<br>"
		f"الموبايل: {mobile}<br>"
		f"الجهاز: {sub.get('imei') or ''}<br>"
		f"<b>السبب/الملاحظة:</b> {frappe.utils.escape_html(reason or '—')}"
	)
	todo.priority = "Medium"
	todo.date = nowdate()
	todo.reference_type = "Customer Subscription"
	todo.reference_name = sub.get("name")
	if settings.get("ticket_owner"):
		todo.allocated_to = settings.ticket_owner
	todo.flags.ignore_permissions = True
	todo.insert()
	return todo.name


@frappe.whitelist()
def report_payment(mobile, note=None):
	"""العميل بعت صورة (اسكرين التحويل) — نسجّله «دفع» وننبّه الفريق.

	مش تأكيد دفع فعلي — ده بلاغ من العميل لازم حد يراجعه ويأكده.
	"""
	clean = _normalise_mobile(mobile)
	sub = _find_subscription(clean)
	if not sub:
		_log(clean, note or "[صورة]", "وارد", state="مش لاقي اشتراك")
		frappe.db.commit()
		return {"ok": 0, "action": "unknown_number"}

	frappe.db.set_value("Customer Subscription", sub.name, {
		"payment_reported": 1,
		"payment_reported_at": now_datetime(),
		"conversation_state": STATE_PAID,
		"needs_call": 1,
		"needs_call_since": now_datetime(),
	}, update_modified=False)

	_log(clean, note or "[بعت صورة تحويل]", "وارد", sub.name,
	     sub.customer_name, STATE_PAID)
	_make_ticket(sub, "بعت صورة تحويل — محتاج مراجعة وتأكيد الدفع", clean)
	_alert_support(sub, clean, "💰 بعت صورة تحويل — راجع الدفع")

	settings = _settings()
	reply = (settings.get("payment_received_reply") or
	         "وصلتنا صورة التحويل ✅ هنراجعها ونفعّل اشتراكك، "
	         "وهنكلمك نأكدلك. شكرًا لثقتك 🌹")
	_log(clean, reply, "صادر", sub.name, sub.customer_name, "payment_reported")
	frappe.db.commit()
	return {"ok": 1, "action": "payment_reported", "reply": reply,
	        "subscription": sub.name, "customer_name": sub.customer_name}


@frappe.whitelist()
def send_prices_image(mobile):
	"""صورة الاشتراكات والأسعار. لو مفيش صورة مرفوعة بيرجع 0 و n8n بيكتفي بالنص."""
	settings = _settings()
	image = settings.get("prices_image")
	if not image:
		return {"sent": 0, "reason": "مفيش صورة أسعار مرفوعة"}
	sub = _find_subscription(mobile)
	caption = _fill(settings.get("prices_text") or "",
	                {**(sub or {}), "days_left": None}, settings)
	return _send_media(mobile, image, caption)


@frappe.whitelist()
def handle_incoming(mobile, text=None, is_image=0):
	"""المدخل الوحيد لأي رسالة واردة من واتساب.

	الصورة من العميل معناها إيصال تحويل — أي كلام تاني بيمشي على
	شجرة الاختيارات العادية.
	"""
	if _int(is_image):
		out = report_payment(mobile, note=text)
		return {"reply": out.get("reply"), "send_image": None,
		        "send_prices_image": 0, "action": out.get("action"),
		        "subscription": out.get("subscription"),
		        "customer_name": out.get("customer_name")}

	out = handle_reply(mobile, text)
	# صورة الأسعار بتتبعت مع رد «2» بس
	out["send_prices_image"] = 1 if out.get("action") == "prices_sent" else 0
	return out
