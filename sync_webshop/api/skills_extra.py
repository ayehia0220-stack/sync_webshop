# -*- coding: utf-8 -*-
"""
مهارات إضافية للمساعد — الحاجات اللي المالك بيسأل عنها فعلًا.

كل مهارة بتقرا بـ `frappe.get_list` فبتحترم صلاحيات المستخدم تلقائيًا،
ومفيش أي كتابة. الأرقام بتترجع متنسّقة عشان الموديل يلخّصها من غير ما
يحسب حاجة بنفسه.
"""
import re

import frappe
from frappe.utils import fmt_money, getdate, nowdate

MAX_ROWS = 10

# أسماء المناديب بالعربي مقابل اللي متسجّل في النظام بالإنجليزي
ALIASES = {
	"ضحى": "Doha", "ضحي": "Doha",
	"سماح": "Samah", "فاطمة": "Fatma", "فاطمه": "Fatma",
	"ابراهيم": "ebrahem", "إبراهيم": "ebrahem",
	"علي": "Ali", "شهاب": "شهاب",
}


def _money(value):
	return fmt_money(value or 0, currency="EGP")


def _name_from(question, prefix_words):
	"""يطلّع الاسم من السؤال بعد كلمة زي «مبيعات» أو «مندوب»."""
	q = str(question or "")
	for w in prefix_words:
		q = re.sub(rf"\b{w}\b", " ", q)
	q = re.sub(r"[؟?،.]", " ", q)
	drop = {"مبيعات", "بتاع", "بتاعة", "بتاعت", "كام", "ايه", "إيه", "قد", "المندوب",
	        "مندوب", "الموظف", "موظف", "عملت", "عمل", "حقق", "الشهر", "ده", "النهاردة"}
	words = [w for w in q.split() if w and w not in drop]
	return " ".join(words).strip()


# ————————————————————— مبيعات المناديب —————————————————————

def act_salesperson_sales(question):
	"""مبيعات مندوب معيّن، أو كل المناديب لو مفيش اسم."""
	name = _name_from(question, ["مبيعات", "مندوب", "المندوب"])
	month_start = getdate(nowdate()).replace(day=1)

	rows = frappe.db.sql("""
		select st.sales_person, count(distinct so.name) orders, sum(st.allocated_amount) total
		from `tabSales Team` st
		join `tabSales Order` so on so.name = st.parent
		where so.docstatus = 1 and so.transaction_date >= %s
		group by st.sales_person
		order by sum(st.allocated_amount) desc
	""", (month_start,), as_dict=True)

	if not rows:
		return "مفيش مبيعات مسجّلة على مناديب الشهر ده."

	if name:
		target = ALIASES.get(name.strip(), name)
		hit = [r for r in rows if target.lower() in (r.sales_person or "").lower()]
		if not hit:
			hit = [r for r in rows if name.lower() in (r.sales_person or "").lower()]
		if not hit:
			available = "، ".join(r.sales_person for r in rows[:8])
			return f"مالقيتش مندوب اسمه «{name}». المناديب اللي عندهم مبيعات الشهر ده: {available}"
		r = hit[0]
		return (f"{r.sales_person} الشهر ده: {r.orders} طلب بإجمالي {_money(r.total)}.")

	lines = ["مبيعات المناديب الشهر ده:"]
	for r in rows[:MAX_ROWS]:
		lines.append(f"• {r.sales_person} — {r.orders} طلب — {_money(r.total)}")
	return "\n".join(lines)


# ————————————————————— الفواتير والمستحقات —————————————————————

def act_overdue_invoices(_question):
	"""الفواتير اللي فات ميعاد سدادها."""
	rows = frappe.get_list(
		"Sales Invoice",
		filters={"docstatus": 1, "status": "Overdue"},
		fields=["name", "customer", "grand_total", "outstanding_amount", "due_date"],
		order_by="due_date asc",
		limit_page_length=MAX_ROWS,
		ignore_permissions=False,
	)
	total = frappe.db.sql("""
		select sum(outstanding_amount) from `tabSales Invoice`
		where docstatus = 1 and status = 'Overdue'
	""")[0][0] or 0
	count = frappe.db.count("Sales Invoice", {"docstatus": 1, "status": "Overdue"})

	if not count:
		return "مفيش فواتير متأخرة — كله متحصّل."

	lines = [f"فيه {count} فاتورة متأخرة بإجمالي {_money(total)}.", "", "أكبرهم تأخيرًا:"]
	for r in rows:
		days = (getdate(nowdate()) - getdate(r.due_date)).days if r.due_date else 0
		lines.append(f"• {r.customer} — {_money(r.outstanding_amount)} — متأخرة {days} يوم")
	return "\n".join(lines)


def act_receivables(_question):
	"""كل المستحق على العملاء (متأخر ولسه)."""
	total = frappe.db.sql("""
		select sum(outstanding_amount) from `tabSales Invoice`
		where docstatus = 1 and outstanding_amount > 0
	""")[0][0] or 0
	count = frappe.db.count("Sales Invoice", {"docstatus": 1, "outstanding_amount": [">", 0]})
	overdue = frappe.db.sql("""
		select sum(outstanding_amount) from `tabSales Invoice`
		where docstatus = 1 and status = 'Overdue'
	""")[0][0] or 0

	if not count:
		return "مفيش مستحقات على العملاء."

	rows = frappe.db.sql("""
		select customer, sum(outstanding_amount) amt from `tabSales Invoice`
		where docstatus = 1 and outstanding_amount > 0
		group by customer order by sum(outstanding_amount) desc limit %s
	""", (MAX_ROWS,), as_dict=True)

	lines = [f"إجمالي المستحق على العملاء: {_money(total)} من {count} فاتورة "
	         f"(منها {_money(overdue)} متأخرة).", "", "أكبر المديونيات:"]
	for r in rows:
		lines.append(f"• {r.customer} — {_money(r.amt)}")
	return "\n".join(lines)


def act_unbilled_deliveries(_question):
	"""إذون تسليم اتسلّمت ولسه ما اتفوترتش."""
	count = frappe.db.count("Delivery Note", {"docstatus": 1, "status": "To Bill"})
	if not count:
		return "كل إذون التسليم متفوترة."
	rows = frappe.get_list(
		"Delivery Note",
		filters={"docstatus": 1, "status": "To Bill"},
		fields=["name", "customer", "grand_total", "posting_date"],
		order_by="posting_date asc",
		limit_page_length=MAX_ROWS,
	)
	total = frappe.db.sql("""
		select sum(grand_total) from `tabDelivery Note`
		where docstatus = 1 and status = 'To Bill'
	""")[0][0] or 0
	lines = [f"فيه {count} إذن تسليم مش متفوتر بإجمالي {_money(total)}.", "", "أقدمهم:"]
	for r in rows:
		lines.append(f"• {r.customer} — {_money(r.grand_total)} — {r.posting_date}")
	return "\n".join(lines)


# ————————————————————— الاشتراكات —————————————————————

def act_failed_numbers(_question):
	"""أرقام وقفت لأنها فشلت في الإرسال ومحتاجة مراجعة بشرية."""
	rows = frappe.get_list(
		"Customer Subscription",
		filters={"needs_number_review": 1},
		fields=["customer_name", "mobile_number", "imei",
		        "send_failures", "last_send_error", "end_date"],
		order_by="modified desc",
		limit_page_length=MAX_ROWS,
	)
	total = frappe.db.count("Customer Subscription", {"needs_number_review": 1})
	if not total:
		return "مفيش أرقام محتاجة مراجعة دلوقتي 👍"
	lines = [f"فيه {total} رقم وقف بسبب فشل الإرسال ومحتاج مراجعة:"]
	for r in rows:
		lines.append(
			f"• {r.customer_name or '—'} — {r.mobile_number or '—'} "
			f"(جهاز {r.imei or '—'}) — فشل {r.send_failures} مرات")
	if total > len(rows):
		lines.append(f"…وكمان {total - len(rows)}")
	return "\n".join(lines)

def act_expiring_subscriptions(_question):
	"""اشتراكات GPS اللي قربت تنتهي."""
	today = getdate(nowdate())
	rows = frappe.get_list(
		"Customer Subscription",
		filters={"renewed": 0, "reminder_active": 1, "customer_refused_to_renew": 0,
		         "end_date": ["between", [today, frappe.utils.add_days(today, 30)]]},
		fields=["customer_name", "imei", "end_date", "mobile_number"],
		order_by="end_date asc",
		limit_page_length=MAX_ROWS,
	)
	total = frappe.db.count("Customer Subscription", {
		"renewed": 0, "reminder_active": 1, "customer_refused_to_renew": 0,
		"end_date": ["between", [today, frappe.utils.add_days(today, 30)]]})
	expired = frappe.db.count("Customer Subscription", {
		"renewed": 0, "reminder_active": 1, "end_date": ["<", today]})

	if not total and not expired:
		return "مفيش اشتراكات قربت تخلص."
	lines = [f"{total} اشتراك بينتهي خلال 30 يوم، و{expired} اشتراك منتهي بالفعل."]
	if rows:
		lines += ["", "أقربهم:"]
		for r in rows:
			days = (getdate(r.end_date) - today).days
			lines.append(f"• {r.customer_name} — جهاز {r.imei or '—'} — باقي {days} يوم")
	return "\n".join(lines)


# ————————————————————— المكالمات —————————————————————

def act_calls_summary(_question):
	"""ملخص مكالمات النهاردة."""
	today = nowdate()
	total = frappe.db.count("Call Log", {"medium": "Issabel", "start_time": [">=", f"{today} 00:00:00"]})
	if not total:
		return "مفيش مكالمات مسجّلة النهاردة."
	missed = frappe.db.count("Call Log", {"medium": "Issabel", "status": ["in", ["No Answer", "Missed"]],
	                                      "start_time": [">=", f"{today} 00:00:00"]})
	answered = frappe.db.count("Call Log", {"medium": "Issabel", "status": "Completed",
	                                        "start_time": [">=", f"{today} 00:00:00"]})
	unknown = frappe.db.count("Call Log", {"medium": "Issabel", "customer": ["is", "not set"],
	                                       "start_time": [">=", f"{today} 00:00:00"]})
	lines = [f"مكالمات النهاردة: {total} — ردّينا على {answered}، وضاعت {missed}."]
	if unknown:
		lines.append(f"منهم {unknown} من أرقام مش مسجّلة كعملاء.")
	return "\n".join(lines)


def act_missed_calls(_question):
	"""المكالمات اللي ضاعت ومحدش رجّعها."""
	rows = frappe.db.sql("""
		select cl.`from` num, cl.customer, max(cl.start_time) last_try, count(*) tries
		from `tabCall Log` cl
		where cl.medium = 'Issabel' and cl.type = 'Incoming'
		  and cl.status in ('No Answer','Missed')
		  and not exists (select 1 from `tabCall Log` c2
		                  where c2.`from` = cl.`from` and c2.status = 'Completed'
		                    and c2.start_time > cl.start_time)
		group by cl.`from`, cl.customer
		order by max(cl.start_time) desc limit %s
	""", (MAX_ROWS,), as_dict=True)
	if not rows:
		return "مفيش مكالمات ضايعة محتاجة رد."
	lines = [f"فيه {len(rows)} رقم اتصل ومحدش رجّعله:"]
	for r in rows:
		who = r.customer or "رقم مش مسجّل"
		lines.append(f"• {r.num} ({who}) — حاول {r.tries} مرة — آخر مرة {str(r.last_try)[:16]}")
	return "\n".join(lines)


# ————————————————————— أرقام الشركة العامة —————————————————————

def act_company_stats(_question):
	"""أرقام عامة: كام موظف، كام عميل، كام صنف… الأسئلة اللي بتتسأل كتير."""
	def count(dt, filters=None):
		try:
			return frappe.db.count(dt, filters) if frappe.db.exists("DocType", dt) else None
		except Exception:
			return None

	lines = ["أرقام الشركة دلوقتي:"]

	active = count("Employee", {"status": "Active"})
	if active is not None:
		total = count("Employee")
		part = f"• الموظفين: {active} على رأس العمل"
		if total and total > active:
			part += f" (من إجمالي {total} مسجّلين)"
		lines.append(part)

	for dt, label, filters in (
		("Customer", "العملاء", None),
		("Supplier", "الموردين", None),
		("Item", "الأصناف", {"disabled": 0}),
		("Sales Person", "المناديب", {"enabled": 1}),
		("Customer Subscription", "اشتراكات GPS النشطة", {"renewed": 0, "reminder_active": 1}),
	):
		n = count(dt, filters)
		if n is not None:
			lines.append(f"• {label}: {n}")

	users = count("User", {"enabled": 1, "user_type": "System User"})
	if users:
		lines.append(f"• مستخدمي النظام: {users}")

	return "\n".join(lines)


def act_staff_list(question):
	"""أسماء الموظفين — كلهم أو اللي في قسم معيّن."""
	rows = frappe.get_list(
		"Employee",
		filters={"status": "Active"},
		fields=["employee_name", "designation", "department", "custom_extension"],
		order_by="employee_name asc",
		limit_page_length=30,
	)
	if not rows:
		return "مفيش موظفين مسجّلين على رأس العمل."

	total = frappe.db.count("Employee", {"status": "Active"})
	lines = [f"فيه {total} موظف على رأس العمل:"]
	for r in rows:
		part = f"• {r.employee_name}"
		bits = [b for b in (r.designation, r.department) if b]
		if bits:
			part += " — " + " / ".join(bits)
		if r.custom_extension:
			part += f" (تحويلة {r.custom_extension})"
		lines.append(part)
	if total > len(rows):
		lines.append(f"… وباقي {total - len(rows)}")
	return "\n".join(lines)


# ————————————————————— بحث شامل عن أي اسم —————————————————————

# فين ممكن نلاقي اسم: (الجدول، وصفه للمستخدم)
NAME_PLACES = [
	("Customer", "عميل"),
	("Supplier", "مورّد"),
	("Sales Partner", "شريك بيع"),
	("Sales Person", "مندوب"),
	("Employee", "موظف"),
	("Item", "صنف"),
]


def act_find_name(question):
	"""بيقول الاسم ده موجود فين في النظام وإيه أرقامه.

	المالك بيسأل عن أسماء من غير ما يحدد نوعها، والاسم ممكن يكون شريك بيع
	أو موظف مش عميل — فلازم نقوله ده بدل ما نقول «مالقيتش».
	"""
	name = _name_from(question, ["عليه", "عليها", "عندها", "عنده", "لينا", "علينا",
	                             "مديونية", "رصيد", "حساب", "مستحق", "مين", "هو", "هي"])
	if not name or len(name) < 2:
		return "اكتب الاسم اللي عايز تعرف عنه."

	# الأسماء في النظام فيها كلمات زيادة ومسافات مزدوجة («محمود  ابراهيم  محمد
	# ابو غرارة»)، فالبحث بالجملة كاملة مش بيلاقي حاجة. بندوّر بكل كلمة.
	words = [w for w in name.split() if len(w) > 2]
	if not words:
		words = [name]
	where = " and ".join(["name like %s"] * len(words))
	params = tuple(f"%{w}%" for w in words)

	found = []
	for dt, label in NAME_PLACES:
		if not frappe.db.exists("DocType", dt):
			continue
		try:
			rows = frappe.db.sql(
				"select name from `tab{}` where {} limit 3".format(dt, where), params)
			if not rows and len(words) > 1:
				# جرّب أطول كلمة لوحدها — «غرارة» بتكفي
				longest = max(words, key=len)
				rows = frappe.db.sql(
					"select name from `tab{}` where name like %s limit 3".format(dt),
					(f"%{longest}%",))
		except Exception:
			continue
		for r in rows:
			found.append((label, dt, r[0]))

	if not found:
		return f"مالقيتش «{name}» في النظام — لا كعميل ولا مورّد ولا موظف ولا شريك بيع."

	lines = [f"«{name}» موجود في:"]
	for label, dt, rec in found[:8]:
		extra = ""
		if dt == "Customer":
			amt = frappe.db.sql("""
				select sum(outstanding_amount) from `tabSales Invoice`
				where docstatus = 1 and customer = %s and outstanding_amount > 0
			""", (rec,))[0][0] or 0
			extra = f" — عليه {_money(amt)}" if amt else " — مفيش عليه مستحقات"
		elif dt == "Supplier":
			amt = frappe.db.sql("""
				select sum(outstanding_amount) from `tabPurchase Invoice`
				where docstatus = 1 and supplier = %s and outstanding_amount > 0
			""", (rec,))[0][0] or 0
			extra = f" — علينا له {_money(amt)}" if amt else " — مفيش عليه مستحقات"
		elif dt == "Sales Partner":
			row = frappe.db.sql("""
				select count(*), sum(grand_total) from `tabSales Order`
				where docstatus = 1 and sales_partner = %s
			""", (rec,))[0]
			extra = f" — {row[0] or 0} طلب بإجمالي {_money(row[1])}"
		elif dt == "Sales Person":
			row = frappe.db.sql("""
				select count(distinct parent), sum(allocated_amount) from `tabSales Team`
				where sales_person = %s
			""", (rec,))[0]
			extra = f" — {row[0] or 0} طلب بإجمالي {_money(row[1])}"
		lines.append(f"• {rec} ({label}){extra}")
	return "\n".join(lines)


# ————————————————————— مديونية عميل معيّن —————————————————————

def act_customer_balance(question):
	"""كل المستحق على عميل بالاسم."""
	name = _name_from(question, ["عليه", "عليها", "مديونية", "رصيد", "حساب", "مستحق",
	                             "اديته", "أديته", "ادينا", "له"])
	if not name:
		return "اكتب اسم العميل، مثلاً: محمود إبراهيم عليه كام؟"

	# نفس حكاية الكلمات الزيادة في الأسماء — بندوّر بكل كلمة
	words = [w for w in name.split() if len(w) > 2] or [name]
	where = " and ".join(["si.customer like %s"] * len(words))
	params = tuple(f"%{w}%" for w in words)

	rows = frappe.db.sql("""
		select si.customer, sum(si.outstanding_amount) amt, count(*) cnt,
		       min(si.due_date) oldest,
		       sum(case when si.status = 'Overdue' then si.outstanding_amount else 0 end) overdue
		from `tabSales Invoice` si
		where si.docstatus = 1 and si.outstanding_amount > 0
		  and {}
		group by si.customer
		order by sum(si.outstanding_amount) desc
	""".format(where), params, as_dict=True)

	if not rows:
		exists = frappe.db.sql(
			"select name from `tabCustomer` where name like %s or customer_name like %s limit 3",
			(f"%{name}%", f"%{name}%"))
		if exists:
			return f"«{exists[0][0]}» مفيش عليه مستحقات — كل فواتيره متسدّدة."
		# مش عميل؟ يبقى يمكن شريك بيع أو موظف — بندوّر بدل ما نقول «مالقيتش»
		return act_find_name(name)

	lines = []
	for r in rows:
		part = f"{r.customer}: عليه {_money(r.amt)} من {r.cnt} فاتورة"
		if r.overdue:
			days = (getdate(nowdate()) - getdate(r.oldest)).days if r.oldest else 0
			part += f" — منها {_money(r.overdue)} متأخرة (أقدمها {days} يوم)"
		lines.append(part)
	return "\n".join(lines)


# ————————————————————— تحصيلات تربو —————————————————————

def act_turbo_collections(_question):
	"""فلوس شحنات تربو حسب حالة كل شحنة."""
	rows = frappe.db.sql("""
		select ifnull(so.turbo_status_text, 'مش محدد') status,
		       count(*) orders, round(sum(so.grand_total)) amount
		from `tabSales Order` so
		where so.docstatus = 1 and ifnull(so.turbo_order_number,'') != ''
		group by so.turbo_status_text
		order by sum(so.grand_total) desc
	""", as_dict=True)

	if not rows:
		return "مفيش شحنات على تربو لسه."

	total = sum(r.amount or 0 for r in rows)
	orders = sum(r.orders or 0 for r in rows)
	lines = [f"شحنات تربو: {orders} شحنة بإجمالي {_money(total)}.", "", "حسب الحالة:"]
	for r in rows:
		lines.append(f"• {r.status} — {r.orders} شحنة — {_money(r.amount)}")
	return "\n".join(lines)


# ————————————————————— الاستعلام الحر (لمديري النظام) —————————————————————

# جداول ممنوعة مهما كانت صلاحية المستخدم — أسرار وبيانات دخول
FORBIDDEN_DOCTYPES = {
	"User", "User Password", "Access Log", "Webshop Content Settings",
	"Renewal Campaign Settings", "Webshop Payment Gateway", "Social Login Key",
	"OAuth Bearer Token", "Token Cache", "Webhook", "Server Script",
}
FORBIDDEN_FIELDS = {"password", "api_secret", "api_key", "secret", "token", "pwd"}


def act_explore_system(question):
	"""بيقول للموديل إيه الجداول الموجودة عشان يعرف يسأل فين."""
	words = [w for w in re.sub(r"[؟?،.]", " ", str(question or "")).split() if len(w) > 2]
	rows = frappe.get_all("DocType", filters={"istable": 0, "issingle": 0},
	                      fields=["name", "module"], limit_page_length=0)

	hits = []
	for r in rows:
		if r.name in FORBIDDEN_DOCTYPES:
			continue
		blob = f"{r.name} {r.module}".lower()
		if any(w.lower() in blob for w in words):
			hits.append(r)

	pool = hits or [r for r in rows if r.module in
	                ("Selling", "Accounts", "Stock", "Buying", "Merciful", "Sync Webshop")]
	lines = ["الجداول المتاحة (استخدم `query_system` عليها):"]
	for r in pool[:40]:
		try:
			n = frappe.db.count(r.name)
		except Exception:
			n = "?"
		lines.append(f"• {r.name} ({r.module}) — {n} سجل")
	return "\n".join(lines)


def act_query_system(doctype=None, filters=None, fields=None, limit=10, order_by=None,
                     group_by=None, question=None):
	"""استعلام حر على أي جدول — قراءة بس وبصلاحيات المستخدم.

	`frappe.get_list` بيطبّق صلاحيات المستخدم الحالي، فمدير النظام بيشوف كل
	حاجة والباقي بيشوف اللي مسموح له. مفيش أي كتابة هنا.
	"""
	import json as _json

	if not doctype:
		return "محتاج تحدد اسم الجدول."
	if doctype in FORBIDDEN_DOCTYPES:
		return f"جدول «{doctype}» فيه بيانات حساسة ومش بيتقرا من هنا."
	if not frappe.db.exists("DocType", doctype):
		return f"مفيش جدول اسمه «{doctype}»."

	def _parse(value, default):
		if value in (None, ""):
			return default
		if isinstance(value, (dict, list)):
			return value
		try:
			return _json.loads(value)
		except Exception:
			return default

	filters = _parse(filters, {})
	fields = _parse(fields, None)

	meta = frappe.get_meta(doctype)
	valid = {f.fieldname for f in meta.fields} | {"name", "creation", "modified", "owner", "docstatus"}
	if fields:
		fields = [f for f in fields
		          if (f.split("(")[-1].strip(") ") in valid or "(" in f)
		          and not any(bad in f.lower() for bad in FORBIDDEN_FIELDS)]
	if not fields:
		fields = ["name"] + [f.fieldname for f in meta.fields
		                     if f.fieldtype in ("Data", "Link", "Currency", "Date", "Select", "Int", "Float")
		                     and not any(bad in f.fieldname.lower() for bad in FORBIDDEN_FIELDS)][:6]

	try:
		rows = frappe.get_list(
			doctype, filters=filters, fields=fields,
			limit_page_length=min(int(limit or 10), 30),
			order_by=order_by or None, group_by=group_by or None,
		)
	except frappe.PermissionError:
		return f"مالكش صلاحية تقرا «{doctype}»."
	except Exception as exc:
		return f"الاستعلام مظبوطش: {str(exc)[:180]}"

	if not rows:
		return f"مفيش نتائج في «{doctype}» بالشروط دي."

	total = frappe.db.count(doctype, filters) if isinstance(filters, dict) else len(rows)
	lines = [f"{doctype}: {total} سجل مطابق. أول {len(rows)}:"]
	for r in rows:
		parts = []
		for k, v in r.items():
			if v in (None, "", 0):
				continue
			parts.append(f"{k}={v}")
		lines.append("• " + " | ".join(parts[:7]))
	return "\n".join(lines)
