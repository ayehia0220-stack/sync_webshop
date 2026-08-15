# -*- coding: utf-8 -*-
"""أرقام مساحة عمل «المكالمات».

⚠️ الأساس اللي كل حاجة هنا مبنية عليه:
السنترال بيبعت حدث لكل **قناة** (Uniqueid) مش لكل **مكالمة**. يعني المكالمة
الواحدة بتتسجّل كذا صف في `Call Log`: صف للرنين، وصف لكل محاولة اتصال في
الدايال بلان، وصف للـ CDR في الآخر. مكالمة واحدة من 01140256120 يوم 13/8
اتسجّلت **20 صف**. عشان كده أي عدّ مباشر على الصفوف بيطلع رقم مضخّم.

كل دالة هنا بتجمّع الصفوف المتقاربة لنفس الرقم في «مكالمة واحدة» الأول،
وبعدين تعدّ. ده بيصلّح الأرقام القديمة والجديدة من غير ما نلمس السنترال.
"""

import frappe
from frappe.utils import add_days, flt, now_datetime, nowdate

# فرق أكبر من كده بين صفين لنفس الرقم = مكالمة جديدة مش نفس المكالمة
GAP_SECONDS = 120

# اتصلّح الجسر على السنترال يوم 2026-08-15 (بقى يستخدم Linkedid بتاع المكالمة
# بدل Uniqueid بتاع القناة)، فمن الوقت ده كل مكالمة = صف واحد صح ومحتاجش دمج.
# الدمج بيتطبّق على السجلات الأقدم بس — عشان الأرقام القديمة تفضل مظبوطة كمان.
CLEAN_FROM = "2026-08-15 00:10:00"

# أولوية الحالة جوه المكالمة الواحدة: أول حالة موجودة هي حالة المكالمة
STATUS_PRIORITY = (
	"Completed", "In Progress", "No Answer", "Missed",
	"Busy", "Failed", "Canceled", "Queued", "Ringing",
)

ANSWERED = ("Completed", "In Progress")
WORK_START, WORK_END = 9, 21  # ساعات الشغل — أي حاجة برّه دي «خارج المواعيد»

CALL_LIST = ["List", "Call Log"]


# ————————————————————— أدوات —————————————————————

def _digits(value):
	return "".join(ch for ch in str(value or "") if ch.isdigit())


def _number_of(row):
	"""الرقم الخارجي بتاع المكالمة — الطرف التاني مش التحويلة."""
	raw = row.get("from") if row.get("type") != "Outgoing" else row.get("to")
	num = _digits(raw)
	return num[-10:] if len(num) > 10 else num


def _rows(start, end):
	return frappe.db.sql("""
		select name, `from`, `to`, `type`, status, start_time, end_time,
		       duration, custom_trunk, customer, call_received_by
		from `tabCall Log`
		where start_time between %s and %s
		order by start_time asc
	""", (start, end), as_dict=True)


def _merge(group):
	statuses = {r.status for r in group}
	status = next((s for s in STATUS_PRIORITY if s in statuses), group[-1].status)
	return frappe._dict({
		"number": _number_of(group[0]),
		"type": group[0].type or "Incoming",
		"status": status,
		"answered": status in ANSWERED,
		"duration": max([flt(r.duration) for r in group] or [0]),
		"start": group[0].start_time,
		"end": group[-1].end_time or group[-1].start_time,
		"customer": next((r.customer for r in group if r.customer), None),
		"trunk": next((r.custom_trunk for r in group if r.custom_trunk), None),
		"employee": next((r.call_received_by for r in group if r.call_received_by), None),
		"rows": len(group),
	})


def calls_between(start, end):
	"""المكالمات الحقيقية في الفترة — بعد دمج صفوف المكالمة الواحدة."""
	cache = getattr(frappe.local, "_call_stats_cache", None)
	if cache is None:
		cache = frappe.local._call_stats_cache = {}
	key = (str(start), str(end))
	if key in cache:
		return cache[key]

	cutoff = frappe.utils.get_datetime(CLEAN_FROM)
	buckets = {}
	clean = []
	for row in _rows(start, end):
		# بعد إصلاح الجسر كل صف = مكالمة كاملة، فمفيش داعي للدمج
		if row.start_time and row.start_time >= cutoff:
			clean.append([row])
			continue
		key_row = (row.type or "Incoming", _number_of(row))
		groups = buckets.setdefault(key_row, [])
		if groups and row.start_time and groups[-1][-1].start_time and \
				(row.start_time - groups[-1][-1].start_time).total_seconds() <= GAP_SECONDS:
			groups[-1].append(row)
		else:
			groups.append([row])

	calls = [_merge(g) for groups in buckets.values() for g in groups]
	calls += [_merge(g) for g in clean]
	calls.sort(key=lambda c: c.start or now_datetime())
	cache[key] = calls
	return calls


def _today():
	day = nowdate()
	return f"{day} 00:00:00", f"{day} 23:59:59"


def _last_days(days):
	return f"{add_days(nowdate(), -(days - 1))} 00:00:00", f"{nowdate()} 23:59:59"


def _today_calls():
	return calls_between(*_today())


def _card(value, fieldtype="Int", route_options=None, route=None):
	"""⚠️ الرقم بيترجع كنص و`fieldtype="Data"` عن قصد.

	كارت الأرقام في فرابي بيمرّر الـ fieldtype على `frappe.format`، واللي
	بيلبّس الرقم شكل العملة بكسور وفواصل («1,363.00»). بـ Data الكارت
	بيعرض النص زي ما هو بالظبط — رقم عادي. الوحدة بتتكتب في اسم الكارت.
	"""
	out = {"value": str(int(round(float(value or 0)))), "fieldtype": "Data",
	       "route": route or CALL_LIST}
	if route_options:
		out["route_options"] = route_options
	return out


def _today_route(extra=None):
	options = {"start_time": [">=", f"{nowdate()} 00:00:00"]}
	options.update(extra or {})
	return options


# ————————————————————— كروت النهاردة —————————————————————

@frappe.whitelist()
def calls_today(**kwargs):
	"""كل المكالمات النهاردة (واردة + صادرة)."""
	return _card(len(_today_calls()), route_options=_today_route())


@frappe.whitelist()
def incoming_today(**kwargs):
	calls = [c for c in _today_calls() if c.type == "Incoming"]
	return _card(len(calls), route_options=_today_route({"type": "Incoming"}))


@frappe.whitelist()
def outgoing_today(**kwargs):
	calls = [c for c in _today_calls() if c.type == "Outgoing"]
	return _card(len(calls), route_options=_today_route({"type": "Outgoing"}))


@frappe.whitelist()
def answered_today(**kwargs):
	calls = [c for c in _today_calls() if c.answered]
	return _card(len(calls), route_options=_today_route({"status": "Completed"}))


@frappe.whitelist()
def missed_today(**kwargs):
	"""مكالمات واردة النهاردة محدش رد عليها."""
	calls = [c for c in _today_calls() if c.type == "Incoming" and not c.answered]
	return _card(len(calls), route_options=_today_route(
		{"type": "Incoming", "status": ["not in", ["Completed", "In Progress"]]}))


@frappe.whitelist()
def answer_rate_today(**kwargs):
	"""نسبة الرد على الوارد النهاردة."""
	incoming = [c for c in _today_calls() if c.type == "Incoming"]
	if not incoming:
		return _card(0, "Percent", _today_route({"type": "Incoming"}))
	rate = len([c for c in incoming if c.answered]) * 100.0 / len(incoming)
	return _card(round(rate, 1), "Percent", _today_route({"type": "Incoming"}))


@frappe.whitelist()
def talk_minutes_today(**kwargs):
	"""إجمالي دقايق الكلام الفعلي النهاردة."""
	seconds = sum(c.duration for c in _today_calls() if c.answered)
	return _card(int(round(seconds / 60.0)), route_options=_today_route({"status": "Completed"}))


@frappe.whitelist()
def avg_duration_today(**kwargs):
	"""متوسط مدة المكالمة المردود عليها النهاردة — بالثواني."""
	answered = [c for c in _today_calls() if c.answered and c.duration]
	if not answered:
		return _card(0, "Duration", _today_route({"status": "Completed"}))
	avg = sum(c.duration for c in answered) / len(answered)
	return _card(int(round(avg)), "Duration", _today_route({"status": "Completed"}))


@frappe.whitelist()
def longest_call_today(**kwargs):
	"""أطول مكالمة النهاردة."""
	durations = [c.duration for c in _today_calls() if c.answered]
	return _card(int(max(durations or [0])), "Duration", _today_route({"status": "Completed"}))


@frappe.whitelist()
def unique_callers_today(**kwargs):
	"""كام رقم مختلف اتصل النهاردة."""
	numbers = {c.number for c in _today_calls() if c.type == "Incoming" and c.number}
	return _card(len(numbers), route_options=_today_route({"type": "Incoming"}))


@frappe.whitelist()
def repeat_callers_today(**kwargs):
	"""أرقام اتصلت أكتر من مرة النهاردة — غالبًا حد محتاج حاجة ومش لاقيها."""
	seen = {}
	for call in _today_calls():
		if call.type == "Incoming" and call.number:
			seen[call.number] = seen.get(call.number, 0) + 1
	return _card(len([n for n, c in seen.items() if c > 1]),
	             route_options=_today_route({"type": "Incoming"}))


@frappe.whitelist()
def unknown_numbers_today(**kwargs):
	"""أرقام اتصلت النهاردة ومش مسجّلة كعملاء — فرص بيع ضايعة."""
	numbers = {c.number for c in _today_calls()
	           if c.type == "Incoming" and not c.customer and c.number}
	return _card(len(numbers), route_options=_today_route(
		{"type": "Incoming", "customer": ["is", "not set"]}))


@frappe.whitelist()
def after_hours_today(**kwargs):
	"""مكالمات واردة برّه ساعات الشغل (قبل 9 ص أو بعد 9 م)."""
	calls = [c for c in _today_calls()
	         if c.type == "Incoming" and c.start and not (WORK_START <= c.start.hour < WORK_END)]
	return _card(len(calls), route_options=_today_route({"type": "Incoming"}))


@frappe.whitelist()
def active_trunks_today(**kwargs):
	"""كام خط (دنجل) دخلت عليه مكالمات النهاردة — لو الرقم قلّ يبقى فيه خط واقع."""
	trunks = {c.trunk for c in _today_calls() if c.trunk}
	return _card(len(trunks), route_options=_today_route())


# ————————————————————— كروت على مدى أوسع —————————————————————

@frappe.whitelist()
def calls_week(**kwargs):
	"""مكالمات آخر 7 أيام."""
	calls = calls_between(*_last_days(7))
	return _card(len(calls), route_options={"start_time": [">=", f"{add_days(nowdate(), -6)} 00:00:00"]})


@frappe.whitelist()
def missed_not_returned(**kwargs):
	"""مكالمات ضاعت ومحدش رجّعلها — آخر 7 أيام.

	الحساب: كل رقم اتصل ومردش عليه، ونشوف بعد كده فيه مكالمة ناجحة معاه
	(صادرة ليه أو واردة منه) ولا لأ. لو مفيش — الرقم ده لسه مستني.
	"""
	calls = calls_between(*_last_days(7))
	last_missed, last_contact = {}, {}
	for call in calls:
		if not call.number:
			continue
		if call.answered:
			last_contact[call.number] = call.start
		elif call.type == "Incoming":
			last_missed[call.number] = call.start

	pending = [n for n, when in last_missed.items()
	           if not last_contact.get(n) or last_contact[n] < when]
	return _card(len(pending), route_options={
		"type": "Incoming",
		"status": ["not in", ["Completed", "In Progress"]],
		"start_time": [">=", f"{add_days(nowdate(), -6)} 00:00:00"],
	})


@frappe.whitelist()
def stuck_ringing(**kwargs):
	"""مكالمات وقفت عند «رنين» ومجاش لها نهاية — مؤشر إن الجسر بينط أحداث.

	الرقم ده المفروض يفضل صغير. لو كبر يبقى `erp-bridge` على السنترال محتاج بصّة.
	"""
	count = frappe.db.count("Call Log", {
		"status": "Ringing",
		"start_time": ["<", frappe.utils.add_to_date(now_datetime(), hours=-1)],
	})
	return _card(count, route_options={"status": "Ringing"})


@frappe.whitelist()
def calls_with_customers_today(**kwargs):
	"""مكالمات النهاردة اللي اتعرف صاحبها كعميل."""
	calls = [c for c in _today_calls() if c.customer]
	return _card(len(calls), route_options=_today_route({"customer": ["is", "set"]}))
