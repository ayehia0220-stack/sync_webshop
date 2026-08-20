# -*- coding: utf-8 -*-
"""
رسايل الواتساب اللي كانت في n8n، بقت جوّه الـ ERP.

أربع لحظات بنكلّم فيها العميل: أول ما يتسجّل، أول ما يعمل طلب، أول ما
يدفع، وأول ما تتعمل له فاتورة. كانوا أربع ورك فلوز في n8n بتنادي على
الـ ERP عشان تجيب بيانات العميل، وبتقرر الرقم من `customer_group` بس.

هنا القرار بيتاخد من `whatsapp_line_for` اللي موجودة أصلًا: بتبص على
أصناف الطلب الأول (كرتونة بن = محادثة بن مهما كانت مجموعة العميل)،
وبعدين مجموعة العميل، وبعدين الخط الافتراضي. يعني البن من 1212 و
الـ GPS من 97 من غير ما نكتب الشرط تاني.

نص الرسالة نفسه مش في الكود — في «Webshop Lifecycle Message» عشان
المالك يعدّله من غير ما يفتح سيرفر.
"""

import frappe
from frappe.utils import cint, flt, now_datetime

from sync_webshop.api.notifications import (normalise_msisdn,
                                            send_whatsapp_text,
                                            whatsapp_line_for)

EVENT_CUSTOMER = "تسجيل عميل"
EVENT_ORDER = "طلب بيع"
EVENT_PAYMENT = "قيد دفع"
EVENT_INVOICE = "فاتورة بيع"

EVENTS = (EVENT_CUSTOMER, EVENT_ORDER, EVENT_PAYMENT, EVENT_INVOICE)


def _money(value):
	try:
		return "{:,.0f}".format(flt(value))
	except Exception:
		return str(value or 0)


def _mobile(customer):
	"""رقم العميل — الحقل المخصص الأول، وبعدين الحقل الأصلي."""
	if not customer:
		return None
	row = frappe.db.get_value(
		"Customer", customer,
		["custom_mobile_phone", "mobile_no", "custom_second_phone_number"],
		as_dict=True) or {}
	for field in ("custom_mobile_phone", "mobile_no",
	              "custom_second_phone_number"):
		number = normalise_msisdn(row.get(field))
		if number:
			return number
	return None


def _customer_name(customer):
	return frappe.db.get_value("Customer", customer, "customer_name") or customer


# ————————————————————————————— السياق —————————————————————————————

def _context(doc, event):
	"""المتغيرات اللي النص بيستخدمها."""
	ctx = {"doc": doc, "event": event}

	if event == EVENT_CUSTOMER:
		ctx["customer"] = doc.name
		ctx["customer_name"] = doc.customer_name or doc.name

	elif event == EVENT_ORDER:
		ctx["customer"] = doc.customer
		ctx["customer_name"] = doc.customer_name or _customer_name(doc.customer)
		ctx["items"] = [{"item_name": i.item_name, "qty": _money(i.qty),
		                 "rate": _money(i.rate), "amount": _money(i.amount)}
		                for i in (doc.items or [])]
		ctx["grand_total"] = _money(doc.grand_total)
		ctx["delivery_date"] = doc.get("delivery_date")

	elif event == EVENT_PAYMENT:
		ctx["customer"] = doc.party
		ctx["customer_name"] = doc.party_name or _customer_name(doc.party)
		ctx["paid_amount"] = _money(doc.base_paid_amount or doc.paid_amount)
		ctx["mode_of_payment"] = doc.get("mode_of_payment")

	elif event == EVENT_INVOICE:
		ctx["customer"] = doc.customer
		ctx["customer_name"] = doc.customer_name or _customer_name(doc.customer)
		# `paid_amount` بتتملي في فواتير نقطة البيع بس. المدفوع الحقيقي
		# هو الإجمالي ناقص المتبقي — من غير كده كل فاتورة مدفوعة
		# بتقول للعميل «المدفوع صفر».
		outstanding = flt(doc.get("outstanding_amount"))
		ctx["grand_total"] = _money(doc.grand_total)
		ctx["outstanding"] = outstanding
		ctx["outstanding_text"] = _money(outstanding)
		ctx["paid_amount"] = _money(flt(doc.grand_total) - outstanding)
		ctx["posting_date"] = doc.get("posting_date")
		ctx["due_date"] = doc.get("due_date")
		ctx["items"] = [{"item_name": i.item_name, "qty": _money(i.qty),
		                 "amount": _money(i.amount)} for i in (doc.items or [])]

	return ctx


def _template(event, line_name):
	"""نص الخط ده بالتحديد، وإلا النص العام للحدث."""
	row = frappe.db.get_value(
		"Webshop Lifecycle Message",
		{"event": event, "line_name": line_name, "enabled": 1},
		["name", "message"], as_dict=True)
	if not row:
		row = frappe.db.get_value(
			"Webshop Lifecycle Message",
			{"event": event, "line_name": "", "enabled": 1},
			["name", "message"], as_dict=True)
	return row


# ————————————————————————————— الإرسال —————————————————————————————

def _stamp(event):
	return "lifecycle-whatsapp:%s" % event


def _already_sent(doctype, name, event):
	"""
	نفس طريقة إيميلات المتجر: تعليقة على المستند نفسه.

	الميزة إنك بتشوفها في تاريخ الفاتورة بعينك، وبتفضل موجودة لو
	الـ Redis اتفضّى — بعكس الأعلام المؤقتة.
	"""
	return bool(frappe.db.exists("Comment", {
		"reference_doctype": doctype, "reference_name": name,
		"content": _stamp(event)}))


def _mark_sent(doctype, name, event):
	frappe.get_doc({
		"doctype": "Comment", "comment_type": "Info",
		"reference_doctype": doctype, "reference_name": name,
		"content": _stamp(event)}).insert(ignore_permissions=True)


def deliver(doctype, name, event, force=0, dry_run=0):
	"""بينده من الطابور بعد ما المستند يتحفظ فعلًا."""
	if not cint(force) and _already_sent(doctype, name, event):
		return {"ok": False, "why": "اتبعتت قبل كده"}

	doc = frappe.get_doc(doctype, name)
	ctx = _context(doc, event)
	customer = ctx.get("customer")

	mobile = _mobile(customer)
	if not mobile:
		return {"ok": False, "why": "العميل مالوش رقم موبايل صالح"}

	order_name = name if event == EVENT_ORDER else None
	line = whatsapp_line_for(order_name=order_name, customer=customer)
	if not line:
		return {"ok": False, "why": "مفيش خط واتساب مظبوط"}

	tpl = _template(event, line.line_name)
	if not tpl:
		return {"ok": False, "why": "مفيش نص للحدث ده"}

	try:
		text = frappe.render_template(tpl.message, ctx).strip()
	except Exception as exc:
		frappe.log_error(title="Lifecycle template", message=frappe.get_traceback()[:2000])
		return {"ok": False, "why": "النص فيه غلطة: %s" % str(exc)[:120]}

	if cint(dry_run):
		return {"ok": True, "dry_run": True, "line": line.line_name,
		        "instance": line.evo_instance, "to": mobile, "text": text}

	ok, detail = send_whatsapp_text(mobile, text, line=line,
	                                order_name=order_name, customer=customer)
	if ok:
		_mark_sent(doctype, name, event)
		frappe.db.commit()
	return {"ok": ok, "line": line.line_name, "instance": line.evo_instance,
	        "to": mobile, "detail": detail}


def _queue(doc, event):
	"""
	الإرسال بيتأجّل للطابور عن قصد: واتساب واقع ماينفعش يمنع حفظ فاتورة.
	"""
	if not frappe.db.get_single_value("Webshop Content Settings",
	                                  "lifecycle_messages_on"):
		return
	frappe.enqueue("sync_webshop.api.lifecycle.deliver", queue="short",
	               enqueue_after_commit=True, doctype=doc.doctype,
	               name=doc.name, event=event)


# ————————————————————————————— الخطّافات —————————————————————————————

def on_customer_insert(doc, method=None):
	_queue(doc, EVENT_CUSTOMER)


def on_sales_order_submit(doc, method=None):
	_queue(doc, EVENT_ORDER)


def on_payment_entry_submit(doc, method=None):
	# دفعات الموردين مش بتاعت العميل
	if (doc.get("party_type") or "") != "Customer":
		return
	_queue(doc, EVENT_PAYMENT)


def on_sales_invoice_submit(doc, method=None):
	# فاتورة نقطة البيع بتتدفع في نفس اللحظة، ورسالة الدفع بتغطيها
	if cint(doc.get("is_pos")):
		return
	_queue(doc, EVENT_INVOICE)


# ————————————————————————————— للتجربة —————————————————————————————

@frappe.whitelist()
def preview(doctype, name, event):
	"""يوريك الرسالة والرقم من غير ما يبعت حاجة."""
	frappe.only_for("System Manager")
	return deliver(doctype, name, event, force=1, dry_run=1)


@frappe.whitelist()
def send_now(doctype, name, event):
	frappe.only_for("System Manager")
	return deliver(doctype, name, event, force=1, dry_run=0)


@frappe.whitelist()
def health():
	"""حالة الأربع رسايل: النص موجود؟ الحدث شغال؟"""
	on = cint(frappe.db.get_single_value("Webshop Content Settings",
	                                     "lifecycle_messages_on"))
	out = {"enabled": on, "events": []}
	for event in EVENTS:
		rows = frappe.get_all("Webshop Lifecycle Message",
		                      filters={"event": event, "enabled": 1},
		                      fields=["line_name"])
		out["events"].append({"event": event,
		                      "lines": [r.line_name or "الكل" for r in rows]})
	return out
