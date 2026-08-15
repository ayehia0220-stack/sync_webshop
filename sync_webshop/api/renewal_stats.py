# -*- coding: utf-8 -*-
"""أرقام مساحة عمل «تجديد الاشتراكات».

كل رسالة صادرة أو واردة بتتسجّل في `Renewal Conversation Log` ومعاها
`state_after` اللي بيقول الرسالة دي كانت إيه. الأرقام هنا بتقرا من هناك،
فمش محتاجين حقول جديدة ولا عدّادات موازية.

خريطة `state_after` للرسايل الصادرة:
  مستني رده على التذكير → رسالة تذكير من الحملة
  payment_sent          → العميل قال «1» فبعتنا طرق الدفع
  prices_sent           → العميل قال «2» فبعتنا الأسعار
  opted_out             → العميل قال «3» فوقّفنا التذكيرات
  support_requested     → العميل قال «4» فطلب مكالمة
  payment_reported      → العميل بعت صورة تحويل
وللرسايل الواردة: الحالة اللي كان فيها العميل، أو «مش لاقي اشتراك».
"""

import frappe
from frappe.utils import add_days, getdate, nowdate

STATE_REMINDER = "مستني رده على التذكير"
STATE_UNKNOWN = "مش لاقي اشتراك"

FAIL_PREFIX = "فشل الإرسال"

LOG_LIST = ["List", "Renewal Conversation Log"]
SUB_LIST = ["List", "Customer Subscription"]
ERROR_LIST = ["List", "Error Log"]


# ————————————————————— أدوات —————————————————————

def _card(value, fieldtype="Int", route=None, route_options=None):
	"""⚠️ الرقم بيترجع كنص و`fieldtype="Data"` عن قصد.

	كارت الأرقام في فرابي بيمرّر الـ fieldtype على `frappe.format`، واللي
	بيلبّس الرقم شكل العملة بكسور وفواصل («1,363.00»). بـ Data الكارت
	بيعرض النص زي ما هو بالظبط — رقم عادي. الوحدة بتتكتب في اسم الكارت.
	"""
	out = {"value": str(int(round(float(value or 0)))), "fieldtype": "Data",
	       "route": route or LOG_LIST}
	if route_options:
		out["route_options"] = route_options
	return out


def _today_start():
	return f"{nowdate()} 00:00:00"


def _log_count(direction=None, state=None, since=None, like=None, not_like=None, unique=False):
	conditions = ["1=1"]
	values = []
	if direction:
		conditions.append("direction = %s")
		values.append(direction)
	if state:
		conditions.append("ifnull(state_after,'') = %s")
		values.append(state)
	if since:
		conditions.append("creation >= %s")
		values.append(since)
	if like:
		conditions.append("body like %s")
		values.append(like)
	if not_like:
		conditions.append("ifnull(body,'') not like %s")
		values.append(not_like)
	field = "count(distinct mobile_number)" if unique else "count(*)"
	row = frappe.db.sql(
		f"select {field} from `tabRenewal Conversation Log` where " + " and ".join(conditions),
		tuple(values))
	return row[0][0] if row else 0


def _sub_count(filters):
	return frappe.db.count("Customer Subscription", filters)


def _today_log_route(direction=None):
	options = {"creation": [">=", _today_start()]}
	if direction:
		options["direction"] = direction
	return options


# ————————————————————— الإرسال —————————————————————

@frappe.whitelist()
def sent_today(**kwargs):
	"""رسايل التذكير اللي اتبعتت فعلًا النهاردة (من غير اللي فشلت)."""
	value = _log_count(direction="صادر", state=STATE_REMINDER, since=_today_start(),
	                   not_like=f"{FAIL_PREFIX}%")
	return _card(value, route_options=_today_log_route("صادر"))


@frappe.whitelist()
def auto_replies_today(**kwargs):
	"""الردود الآلية اللي البوت بعتها النهاردة (غير رسايل التذكير)."""
	total = _log_count(direction="صادر", since=_today_start(), not_like=f"{FAIL_PREFIX}%")
	reminders = _log_count(direction="صادر", state=STATE_REMINDER, since=_today_start(),
	                       not_like=f"{FAIL_PREFIX}%")
	return _card(max(total - reminders, 0), route_options=_today_log_route("صادر"))


@frappe.whitelist()
def failed_today(**kwargs):
	"""رسايل فشل إرسالها النهاردة — دي أول حاجة تتراجع لما الأرقام تقل."""
	value = _log_count(direction="صادر", since=_today_start(), like=f"{FAIL_PREFIX}%")
	return _card(value, route_options=_today_log_route("صادر"))


@frappe.whitelist()
def sent_total(**kwargs):
	"""إجمالي رسايل التذكير من بداية الحملة."""
	return _card(_log_count(direction="صادر", state=STATE_REMINDER,
	                        not_like=f"{FAIL_PREFIX}%"),
	             route_options={"direction": "صادر"})


@frappe.whitelist()
def remaining_quota_today(**kwargs):
	"""الباقي من الحد اليومي — لو صفر يبقى الحملة وقفت لحد بكرة."""
	settings = frappe.get_single("Renewal Campaign Settings")
	limit = frappe.utils.cint(settings.get("daily_limit")) or 80
	sent = _log_count(direction="صادر", since=_today_start(), not_like=f"{FAIL_PREFIX}%")
	return _card(max(limit - sent, 0), route_options=_today_log_route("صادر"))


# ————————————————————— ردود العملاء —————————————————————

@frappe.whitelist()
def replies_today(**kwargs):
	"""كام عميل رد النهاردة (أرقام مختلفة، مش عدد الرسايل)."""
	value = _log_count(direction="وارد", since=_today_start(), unique=True)
	return _card(value, route_options=_today_log_route("وارد"))


@frappe.whitelist()
def reply_rate_today(**kwargs):
	"""نسبة اللي ردّوا من اللي اتبعتلهم النهاردة."""
	sent = _log_count(direction="صادر", state=STATE_REMINDER, since=_today_start(),
	                  not_like=f"{FAIL_PREFIX}%", unique=True)
	if not sent:
		return _card(0, "Percent", route_options=_today_log_route())
	replied = _log_count(direction="وارد", since=_today_start(), unique=True)
	return _card(round(min(replied, sent) * 100.0 / sent, 1), "Percent",
	             route_options=_today_log_route())


@frappe.whitelist()
def chose_renew_today(**kwargs):
	"""عملاء قالوا «1» عايزين يجددوا النهاردة."""
	return _card(_log_count(direction="صادر", state="payment_sent", since=_today_start()),
	             route_options=_today_log_route("صادر"))


@frappe.whitelist()
def asked_prices_today(**kwargs):
	"""عملاء سألوا عن الأسعار النهاردة."""
	return _card(_log_count(direction="صادر", state="prices_sent", since=_today_start()),
	             route_options=_today_log_route("صادر"))


@frappe.whitelist()
def opted_out_today(**kwargs):
	"""عملاء قالوا «بطّل الرسايل» النهاردة."""
	return _card(_log_count(direction="صادر", state="opted_out", since=_today_start()),
	             route_options=_today_log_route("صادر"))


@frappe.whitelist()
def support_requested_today(**kwargs):
	"""عملاء طلبوا مكالمة النهاردة."""
	return _card(_log_count(direction="صادر", state="support_requested", since=_today_start()),
	             route_options=_today_log_route("صادر"))


@frappe.whitelist()
def payment_reported_today(**kwargs):
	"""عملاء بعتوا صورة تحويل النهاردة — محتاجة مراجعة."""
	return _card(_log_count(direction="وارد", state="قال إنه دفع", since=_today_start()),
	             route_options=_today_log_route("وارد"))


@frappe.whitelist()
def handover_tickets_today(**kwargs):
	"""تذاكر اتفتحت النهاردة لموظف يرد على عميل — رد بكلام البوت مش بيرد عليه."""
	value = frappe.db.count("ToDo", {
		"reference_type": "Customer Subscription",
		"creation": [">=", _today_start()],
	})
	return _card(value, route=["List", "ToDo"],
	             route_options={"reference_type": "Customer Subscription",
	                            "creation": [">=", _today_start()]})


# ————————————————————— مشاكل محتاجة تدخّل —————————————————————

@frappe.whitelist()
def unmatched_replies_week(**kwargs):
	"""ردود جت من أرقام مش لاقيينها في الاشتراكات — آخر 7 أيام.

	كل واحد هنا يا إما رقمه متسجّل غلط في الاشتراك، يا إما بيرد من رقم تاني.
	محدش بيرد عليهم آليًا، فلازم حد يبص عليهم.
	"""
	since = f"{add_days(nowdate(), -6)} 00:00:00"
	return _card(_log_count(direction="وارد", state=STATE_UNKNOWN, since=since, unique=True),
	             route_options={"direction": "وارد", "state_after": STATE_UNKNOWN})


@frappe.whitelist()
def campaign_errors_today(**kwargs):
	"""أخطاء متسجّلة النهاردة في كود الحملة أو الواتساب."""
	row = frappe.db.sql("""
		select count(*) from `tabError Log`
		where creation >= %s
		  and (ifnull(method,'') like %s or ifnull(method,'') like %s
		       or ifnull(method,'') like %s or ifnull(error,'') like %s)
	""", (_today_start(), "%renewal%", "%_send_media%", "%_alert_support%", "%renewal%"))
	value = row[0][0] if row else 0
	return _card(value, route=ERROR_LIST, route_options={"creation": [">=", _today_start()]})


@frappe.whitelist()
def system_errors_today(**kwargs):
	"""كل أخطاء ERPNext النهاردة — لو الرقم قفز يبقى فيه حاجة واقعة."""
	value = frappe.db.count("Error Log", {"creation": [">=", _today_start()]})
	return _card(value, route=ERROR_LIST, route_options={"creation": [">=", _today_start()]})


# ————————————————————— حالة الاشتراكات —————————————————————

@frappe.whitelist()
def awaiting_reply(**kwargs):
	"""اتبعتلهم ولسه مردوش."""
	value = _sub_count({"conversation_state": STATE_REMINDER, "renewed": 0,
	                    "customer_refused_to_renew": 0})
	return _card(value, route=SUB_LIST,
	             route_options={"conversation_state": STATE_REMINDER, "renewed": 0})


@frappe.whitelist()
def needs_call(**kwargs):
	value = _sub_count({"needs_call": 1, "renewed": 0})
	return _card(value, route=SUB_LIST, route_options={"needs_call": 1, "renewed": 0})


@frappe.whitelist()
def payment_pending_review(**kwargs):
	value = _sub_count({"payment_reported": 1, "renewed": 0})
	return _card(value, route=SUB_LIST, route_options={"payment_reported": 1, "renewed": 0})


@frappe.whitelist()
def renewed_today(**kwargs):
	value = _sub_count({"renewed": 1, "renewed_date": nowdate()})
	return _card(value, route=SUB_LIST, route_options={"renewed": 1, "renewed_date": nowdate()})


@frappe.whitelist()
def subscriptions_total(**kwargs):
	"""كل السيريالات المسجّلة."""
	return _card(frappe.db.count("Customer Subscription"), route=SUB_LIST)


@frappe.whitelist()
def renewed_total(**kwargs):
	return _card(_sub_count({"renewed": 1}), route=SUB_LIST, route_options={"renewed": 1})


@frappe.whitelist()
def refused_total(**kwargs):
	"""عملاء رفضوا التجديد أو طلبوا إيقاف الرسايل."""
	return _card(_sub_count({"customer_refused_to_renew": 1}), route=SUB_LIST,
	             route_options={"customer_refused_to_renew": 1})


@frappe.whitelist()
def pending_subscriptions(**kwargs):
	"""لسه في الطابور: مجددش، مرفضش، والتذكير شغّال."""
	value = _sub_count({"renewed": 0, "customer_refused_to_renew": 0, "reminder_active": 1})
	return _card(value, route=SUB_LIST,
	             route_options={"renewed": 0, "customer_refused_to_renew": 0, "reminder_active": 1})


@frappe.whitelist()
def expiring_week(**kwargs):
	"""اشتراكات هتنتهي خلال 7 أيام ولسه مجددتش."""
	value = _sub_count({"renewed": 0, "customer_refused_to_renew": 0,
	                    "end_date": ["between", [nowdate(), add_days(nowdate(), 7)]]})
	return _card(value, route=SUB_LIST, route_options={
		"renewed": 0, "end_date": ["between", [nowdate(), add_days(nowdate(), 7)]]})


@frappe.whitelist()
def expired_not_renewed(**kwargs):
	"""منتهية خلاص ومجددتش ومرفضتش — دي أهم قايمة للتحصيل."""
	value = _sub_count({"renewed": 0, "customer_refused_to_renew": 0,
	                    "end_date": ["<", nowdate()]})
	return _card(value, route=SUB_LIST, route_options={
		"renewed": 0, "customer_refused_to_renew": 0, "end_date": ["<", nowdate()]})


@frappe.whitelist()
def never_contacted(**kwargs):
	"""اشتراكات في الطابور ومحدش كلّمها ولا مرة."""
	value = _sub_count({"renewed": 0, "customer_refused_to_renew": 0,
	                    "reminder_active": 1, "messages_sent_count": ["in", [0, None]]})
	return _card(value, route=SUB_LIST, route_options={
		"renewed": 0, "reminder_active": 1, "messages_sent_count": 0})


@frappe.whitelist()
def conversion_rate(**kwargs):
	"""نسبة اللي جددوا من اللي اتبعتلهم رسايل."""
	messaged = frappe.db.sql("""
		select count(*) from `tabCustomer Subscription`
		where ifnull(messages_sent_count,0) > 0
	""")[0][0]
	if not messaged:
		return _card(0, "Percent", route=SUB_LIST)
	renewed = frappe.db.sql("""
		select count(*) from `tabCustomer Subscription`
		where ifnull(messages_sent_count,0) > 0 and renewed = 1
	""")[0][0]
	return _card(round(renewed * 100.0 / messaged, 1), "Percent", route=SUB_LIST)
