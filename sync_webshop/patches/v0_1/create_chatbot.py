# -*- coding: utf-8 -*-
"""
Storefront assistant, built on answers the owner writes.

Two documents:

  Webshop Bot Answer   — one question/answer pair with the words that trigger it.
  Webshop Bot Settings — the greeting, the fallback, the handover, and the list
                         of subjects the bot must never discuss.

The bot only ever repeats an answer that exists. It has no generative step, so
it cannot leak a cost, a margin, a supplier or a stock figure — the guarded
topics are refused before any matching happens, and anything unmatched hands
over to a human instead of guessing.
"""
import frappe


def _f(fieldname, label, fieldtype, **kw):
	return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, **kw}


BOT_ANSWER = {
	"name": "Webshop Bot Answer",
	"autoname": "field:question_ar",
	"title_field": "question_ar",
	"fields": [
		_f("question_ar", "السؤال (عربي)", "Data", reqd=1, in_list_view=1),
		_f("enabled", "مفعّل / Enabled", "Check", default="1", in_list_view=1),
		_f("cb1", "", "Column Break"),
		_f("question_en", "Question (English)", "Data"),
		_f("category", "التصنيف / Category", "Select", in_list_view=1,
		   options="عام\nالشحن والتوصيل\nالدفع\nالمنتجات\nالاسترجاع\nالطلبات",
		   default="عام"),
		_f("sec_kw", "كلمات التطابق / Trigger Words", "Section Break",
		   description="اكتب الكلمات اللي لو العميل كتب أي واحدة منها يظهر الرد ده. مفصولة بفاصلة."),
		_f("keywords_ar", "كلمات عربية", "Small Text", reqd=1),
		_f("keywords_en", "English words", "Small Text"),
		_f("sec_ans", "الرد / Answer", "Section Break"),
		_f("answer_ar", "الرد (عربي)", "Text Editor", reqd=1),
		_f("answer_en", "Answer (English)", "Text Editor"),
		_f("sec_stats", "", "Section Break"),
		_f("times_used", "عدد مرات الاستخدام", "Int", read_only=1,
		   description="كام مرة الرد ده ساعد عميل."),
	],
}

BOT_SETTINGS = {
	"name": "Webshop Bot Settings",
	"issingle": 1,
	"fields": [
		_f("enabled", "شغّال على الموقع / Enabled", "Check", default="0",
		   description="مش هيظهر للعملاء غير لما تعلّم هنا."),
		_f("cb1", "", "Column Break"),
		_f("bot_name_ar", "اسم المساعد (عربي)", "Data", default="مساعد دبونو"),
		_f("bot_name_en", "Assistant name (English)", "Data", default="dpono assistant"),
		_f("sec_msgs", "الرسائل / Messages", "Section Break"),
		_f("greeting_ar", "رسالة الترحيب (عربي)", "Small Text",
		   default="أهلاً! اسألني عن الشحن أو الدفع أو المنتجات."),
		_f("greeting_en", "Greeting (English)", "Small Text",
		   default="Hi! Ask me about delivery, payment or our products."),
		_f("cb2", "", "Column Break"),
		_f("fallback_ar", "لو مالقاش رد (عربي)", "Small Text",
		   default="مش عندي إجابة للسؤال ده. هوصّلك بفريق الخدمة."),
		_f("fallback_en", "When no answer matches (English)", "Small Text",
		   default="I don't have an answer for that. Let me connect you to our team."),
		_f("sec_handover", "التحويل لموظف / Handover", "Section Break"),
		_f("handover_whatsapp", "تحويل على واتساب", "Check", default="1",
		   description="يظهر زر واتساب برقم المتجر مع رسالة «لو مالقاش رد»."),
		_f("handover_label_ar", "نص الزر (عربي)", "Data", default="اتكلم مع الفريق"),
		_f("handover_label_en", "Button label (English)", "Data", default="Talk to our team"),
		_f("sec_guard", "مواضيع ممنوعة / Blocked Subjects", "Section Break",
		   description="المساعد يرفض أي سؤال فيه الكلمات دي ويحوّل لموظف. القائمة دي فوق كل الردود."),
		_f("blocked_keywords_ar", "كلمات ممنوعة (عربي)", "Small Text",
		   default="تكلفة, التكلفة, سعر التكلفة, هامش, ربح, الربح, مكسب, المورد, الموردين, "
		           "مصنع, المخزون الفعلي, الرصيد, حسابات, ميزانية, مرتب, راتب, خصم خاص, "
		           "عمولة, صافي, فاتورة المورد, أسعار الشراء"),
		_f("blocked_keywords_en", "Blocked words (English)", "Small Text",
		   default="cost, cost price, margin, profit, supplier, suppliers, wholesale price, "
		           "purchase price, salary, payroll, commission, balance sheet, stock level"),
		_f("blocked_reply_ar", "الرد على سؤال ممنوع (عربي)", "Small Text",
		   default="ده استفسار داخلي مش بقدر أرد عليه. لو محتاج مساعدة في طلبك أنا موجود."),
		_f("blocked_reply_en", "Reply to a blocked question (English)", "Small Text",
		   default="That's internal information I can't share. I'm happy to help with your order."),
		_f("sec_log", "السجل / Log", "Section Break"),
		_f("log_questions", "سجّل أسئلة العملاء", "Check", default="1",
		   description="بيسجّل السؤال والرد عشان تشوف العملاء بيسألوا عن إيه وتضيف ردود ناقصة."),
	],
}

BOT_LOG = {
	"name": "Webshop Bot Log",
	"autoname": "hash",
	"fields": [
		_f("question", "سؤال العميل", "Data", in_list_view=1, read_only=1),
		_f("matched_answer", "الرد اللي طلع", "Link", options="Webshop Bot Answer",
		   in_list_view=1, read_only=1),
		_f("outcome", "النتيجة", "Select", in_list_view=1, read_only=1,
		   options="أجاب\nمفيش رد\nممنوع"),
		_f("language", "اللغة", "Data", read_only=1),
	],
}

PERMS = [
	{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales Manager", "read": 1, "write": 1, "create": 1},
	{"role": "Sales User", "read": 1},
]

# A handful of answers that are true regardless of how the shop is configured.
# Nothing here promises a price, a delivery time or a policy.
STARTER = [
	{
		"question_ar": "إزاي أتابع طلبي؟",
		"question_en": "How do I track my order?",
		"category": "الطلبات",
		"keywords_ar": "تتبع, أتابع, فين طلبي, وصل, الشحنة, تتبّع",
		"keywords_en": "track, tracking, where is my order, shipment",
		"answer_ar": "<p>من صفحة <a href='/track'>تتبّع الطلب</a>. هتحتاج رقم الطلب والبريد اللي طلبت بيه.</p>",
		"answer_en": "<p>Use the <a href='/track'>order tracking</a> page. You'll need your order number and the email you ordered with.</p>",
	},
	{
		"question_ar": "أقدر أدفع إزاي؟",
		"question_en": "How can I pay?",
		"category": "الدفع",
		"keywords_ar": "أدفع, الدفع, فيزا, كاش, عند الاستلام, طرق الدفع",
		"keywords_en": "pay, payment, card, cash, delivery",
		"answer_ar": "<p>طرق الدفع المتاحة تظهرلك في صفحة إتمام الطلب. الدفع عند الاستلام متاح.</p>",
		"answer_en": "<p>Available payment options are shown at checkout. Cash on delivery is available.</p>",
	},
	{
		"question_ar": "أقدر أشوف طلباتي القديمة؟",
		"question_en": "Can I see my past orders?",
		"category": "الطلبات",
		"keywords_ar": "طلباتي, الطلبات القديمة, حسابي, تاريخ الطلبات",
		"keywords_en": "my orders, past orders, order history, account",
		"answer_ar": "<p>أيوة، من صفحة <a href='/dashboard'>طلباتي</a>. هنبعتلك كود على بريدك عشان نتأكد إنه إنت.</p>",
		"answer_en": "<p>Yes — open <a href='/dashboard'>my orders</a>. We'll email you a code to confirm it's you.</p>",
	},
	{
		"question_ar": "أقدر أعيد طلب سابق؟",
		"question_en": "Can I reorder?",
		"category": "الطلبات",
		"keywords_ar": "أعيد الطلب, اطلب تاني, نفس الطلب",
		"keywords_en": "reorder, order again, repeat order",
		"answer_ar": "<p>أيوة. افتح <a href='/dashboard'>طلباتي</a> واضغط «اطلب تاني» على أي طلب — بنجهّز السلة بالأسعار الحالية.</p>",
		"answer_en": "<p>Yes. Open <a href='/dashboard'>my orders</a> and press “Order again” — we rebuild the cart at today's prices.</p>",
	},
]


def _sync(spec):
	if frappe.db.exists("DocType", spec["name"]):
		doc = frappe.get_doc("DocType", spec["name"])
		doc.fields = []
	else:
		doc = frappe.new_doc("DocType")
		doc.name = spec["name"]

	doc.module = "Sync Webshop"
	doc.custom = 0
	doc.engine = "InnoDB"
	doc.issingle = spec.get("issingle", 0)
	if spec.get("autoname"):
		doc.autoname = spec["autoname"]
	if spec.get("title_field"):
		doc.title_field = spec["title_field"]

	for idx, field in enumerate(spec["fields"], start=1):
		doc.append("fields", {**field, "idx": idx})

	doc.permissions = []
	for perm in PERMS:
		doc.append("permissions", perm)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return doc.name


def execute():
	was_dev = frappe.conf.get("developer_mode")
	frappe.conf["developer_mode"] = 1
	try:
		names = [_sync(BOT_ANSWER), _sync(BOT_SETTINGS), _sync(BOT_LOG)]
	finally:
		frappe.conf["developer_mode"] = was_dev or 0

	created = []
	for row in STARTER:
		if frappe.db.exists("Webshop Bot Answer", row["question_ar"]):
			continue
		doc = frappe.get_doc({"doctype": "Webshop Bot Answer", "enabled": 1, **row})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		created.append(row["question_ar"])

	frappe.db.commit()
	frappe.clear_cache()
	print("BOT=" + ", ".join(names) + " | answers=" + str(len(created)))
