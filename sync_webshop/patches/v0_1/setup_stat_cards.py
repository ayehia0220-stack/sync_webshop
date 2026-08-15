# -*- coding: utf-8 -*-
"""بيعمل/بيحدّث كروت الأرقام في مساحتي «المكالمات» و«تجديد الاشتراكات».

كل الكروت نوعها Custom وبتنده دوال في `api/call_stats.py` و`api/renewal_stats.py`،
عشان الرقم يتحسب بمنطق حقيقي (زي دمج صفوف المكالمة الواحدة) بدل فلتر بسيط.

تشغيله تاني آمن — بيحدّث الموجود ومبيكررش.
"""

import json

import frappe

CALL_CARDS = [
	("أرقام النهاردة", [
		("مكالمات النهاردة", "calls_today"),
		("مكالمات واردة النهاردة", "incoming_today"),
		("مكالمات صادرة النهاردة", "outgoing_today"),
		("مكالمات مردود عليها النهاردة", "answered_today"),
		("مكالمات فايتة النهاردة", "missed_today"),
		("نسبة الرد على المكالمات %", "answer_rate_today"),
	]),
	("جودة الخدمة", [
		("مكالمات ضاعت ومحدش رجّعلها", "missed_not_returned"),
		("دقايق كلام النهاردة", "talk_minutes_today"),
		("متوسط مدة المكالمة بالثواني", "avg_duration_today"),
		("أطول مكالمة النهاردة بالثواني", "longest_call_today"),
	]),
	("الأرقام والعملاء", [
		("أرقام اتصلت النهاردة", "unique_callers_today"),
		("أرقام كررت الاتصال النهاردة", "repeat_callers_today"),
		("أرقام مش عملاء اتصلت النهاردة", "unknown_numbers_today"),
		("مكالمات عملاء معروفين النهاردة", "calls_with_customers_today"),
	]),
	("تشغيل ومتابعة", [
		("مكالمات آخر 7 أيام", "calls_week"),
		("مكالمات برّه المواعيد النهاردة", "after_hours_today"),
		("خطوط شغّالة النهاردة", "active_trunks_today"),
		("مكالمات عالقة عند الرنين", "stuck_ringing"),
	]),
]

RENEWAL_CARDS = [
	("حركة النهاردة", [
		("رسايل تجديد اتبعتت النهاردة", "sent_today"),
		("ردود آلية اتبعتت النهاردة", "auto_replies_today"),
		("عملاء ردّوا النهاردة", "replies_today"),
		("نسبة رد العملاء على الرسايل %", "reply_rate_today"),
	]),
	("العملاء ردّوا بإيه النهاردة", [
		("عايزين يجددوا النهاردة", "chose_renew_today"),
		("سألوا عن الأسعار النهاردة", "asked_prices_today"),
		("طلبوا مكالمة النهاردة", "support_requested_today"),
		("بطّلوا الرسايل النهاردة", "opted_out_today"),
		("بعتوا صورة تحويل النهاردة", "payment_reported_today"),
		("تذاكر للموظفين النهاردة", "handover_tickets_today"),
	]),
	("مشاكل محتاجة تدخّل", [
		("رسايل فشل إرسالها النهاردة", "failed_today"),
		("أخطاء الحملة النهاردة", "campaign_errors_today"),
		("أخطاء ERPNext النهاردة", "system_errors_today"),
		("ردود من أرقام مش لاقيينها", "unmatched_replies_week"),
	]),
	("حالة الاشتراكات", [
		("إجمالي السيريالات", "subscriptions_total"),
		("لسه في طابور التذكير", "pending_subscriptions"),
		("اتبعتلهم ولسه مردوش", "awaiting_reply"),
		("محتاجين مكالمة", "needs_call"),
		("دفع مستني مراجعة", "payment_pending_review"),
		("جددوا النهاردة", "renewed_today"),
		("إجمالي اللي جددوا", "renewed_total"),
		("إجمالي اللي رفضوا", "refused_total"),
		("هتنتهي خلال أسبوع", "expiring_week"),
		("منتهية ومجددتش", "expired_not_renewed"),
		("محدش كلّمها ولا مرة", "never_contacted"),
		("نسبة التجديد من اللي اتكلّموا %", "conversion_rate"),
	]),
	("مدى الحملة", [
		("إجمالي رسايل التجديد المبعوتة", "sent_total"),
		("الباقي من حد النهاردة", "remaining_quota_today"),
	]),
]


def _ensure_card(label, method, doctype):
	if frappe.db.exists("Number Card", label):
		doc = frappe.get_doc("Number Card", label)
	else:
		doc = frappe.new_doc("Number Card")
		doc.label = label
	doc.type = "Custom"
	doc.method = method
	doc.document_type = doctype
	doc.function = "Count"
	doc.is_public = 1
	doc.show_percentage_stats = 0
	# من غير ده فرابي بيختصر الأرقام الكبيرة («1.36 K») — إحنا عايزين الرقم كامل
	doc.show_full_number = 1
	doc.currency = None
	doc.filters_json = "[]"
	doc.dynamic_filters_json = ""
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


def _build_content(old_content, sections, col):
	"""بيستبدل قسم الأرقام في أول المساحة ويسيب الاختصارات والروابط زي ما هي."""
	old = json.loads(old_content or "[]")
	tail = [b for b in old if b.get("type") != "number_card"]

	# الهيدر القديم بتاع الأرقام والفواصل اللي بعده بقت فاضية
	while tail and (
		(tail[0].get("type") == "header" and "أرقام" in (tail[0].get("data", {}).get("text") or ""))
		or tail[0].get("type") == "spacer"
	):
		tail.pop(0)

	blocks = []
	counter = 0
	for title, cards in sections:
		counter += 1
		blocks.append({
			"id": f"sthdr{counter}",
			"type": "header",
			"data": {"text": f'<span class="h4"><b>{title}</b></span>', "col": 12},
		})
		for label, _method in cards:
			counter += 1
			blocks.append({
				"id": f"stcard{counter}",
				"type": "number_card",
				"data": {"number_card_name": label, "col": col},
			})
		counter += 1
		blocks.append({"id": f"stspc{counter}", "type": "spacer", "data": {"col": 12}})

	return blocks + tail


def _ensure_link_cards(ws, content):
	"""الروابط مبتظهرش من غير بلوك card — بنتأكد إن كل Card Break ليه بلوك."""
	shown = {b.get("data", {}).get("card_name") for b in content if b.get("type") == "card"}
	missing = [l.label for l in ws.links
	           if l.type == "Card Break" and l.label and l.label not in shown]
	if not missing:
		return content
	content.append({"id": "stlinkspc", "type": "spacer", "data": {"col": 12}})
	for idx, label in enumerate(missing):
		content.append({
			"id": f"stlink{idx}",
			"type": "card",
			"data": {"card_name": label, "col": 4},
		})
	return content


def _apply(workspace, sections, doctype, col, module_path, hide_custom=False):
	if not frappe.db.exists("Workspace", workspace):
		print(f"⚠️  مساحة «{workspace}» مش موجودة — اتخطّت")
		return
	ws = frappe.get_doc("Workspace", workspace)

	labels = []
	for _title, cards in sections:
		for label, method in cards:
			_ensure_card(label, f"{module_path}.{method}", doctype)
			labels.append(label)

	content = _build_content(ws.content, sections, col)
	content = _ensure_link_cards(ws, content)
	ws.content = json.dumps(content, ensure_ascii=False)

	ws.number_cards = []
	for label in labels:
		ws.append("number_cards", {"label": label, "number_card_name": label})

	# فرابي بيضيف كارت «تقارير مخصصة» تلقائي بكل تقارير الموديول — وده بيبقى
	# نسخة تانية من كارت «التقارير» اللي إحنا مرتبينه. بنقفل التلقائي.
	if hide_custom:
		ws.hide_custom = 1

	ws.flags.ignore_permissions = True
	ws.save()
	print(f"✅ {workspace}: {len(labels)} كارت")


# كروت اتعملت بأسماء قديمة واتغيّرت — بتتشال عشان متفضلش معلّقة في القايمة
STALE = [
	"نسبة الرد النهاردة",
	"متوسط مدة المكالمة النهاردة",
	"أطول مكالمة النهاردة",
	"نسبة التجديد من اللي اتكلّموا",
]


def _drop_stale():
	linked = {row.number_card_name for row in
	          frappe.get_all("Workspace Number Card", fields=["number_card_name"])}
	for label in STALE:
		if label in linked:
			continue
		if frappe.db.exists("Number Card", label):
			frappe.delete_doc("Number Card", label, force=1, ignore_permissions=True)
			print(f"🗑️  اتشال كارت قديم: {label}")


def execute():
	_apply("المكالمات", CALL_CARDS, "Call Log", 3,
	       "sync_webshop.api.call_stats", hide_custom=True)
	_apply("تجديد الاشتراكات", RENEWAL_CARDS, "Customer Subscription", 3,
	       "sync_webshop.api.renewal_stats")
	_drop_stale()
	frappe.db.commit()
	frappe.clear_cache()
	print("تم.")
