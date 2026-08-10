# -*- coding: utf-8 -*-
"""
Fill every empty part of the store with a working example so the owner can see
each feature running, then edit the wording.

Every example carries a visible «نموذج — راجعه قبل النشر» banner. Shipping,
returns, privacy and terms are commitments to a customer, so they must not read
as final text written by someone other than the business.
"""
import frappe

DRAFT_BANNER = (
	'<p style="background:#FFF3EB;border-radius:8px;padding:10px 14px;color:#8C5B3F">'
	'<strong>نموذج — راجعه وعدّله قبل النشر للعملاء.</strong></p>'
)

PAGE_EXAMPLES = {
	"shipping": """
<h2>مناطق التوصيل</h2>
<p>بنوصّل لكل محافظات مصر عن طريق شركة شحن.</p>
<h2>مدة التوصيل</h2>
<ul><li>القاهرة والجيزة: من يوم لـ 3 أيام عمل</li>
<li>الإسكندرية والدلتا: من يومين لـ 4 أيام عمل</li>
<li>باقي المحافظات: من 3 لـ 5 أيام عمل</li></ul>
<h2>تكلفة الشحن</h2>
<p>التكلفة بتظهرلك في صفحة إتمام الطلب حسب محافظتك، قبل ما تأكد.</p>
<h2>متابعة الشحنة</h2>
<p>أول ما الشحنة تخرج بنبعتلك رسالة فيها رقم التتبّع، وتقدر تتابعها من صفحة تتبّع الطلب.</p>
""",
	"returns": """
<h2>مدة الاسترجاع</h2>
<p>تقدر تطلب استرجاع خلال 14 يوم من استلام الطلب.</p>
<h2>حالة المنتج</h2>
<p>المنتج يكون بحالته الأصلية وبعبوته المغلقة. المنتجات المفتوحة مش بتترجع لأسباب صحية.</p>
<h2>طريقة الاسترجاع</h2>
<p>كلّمنا على واتساب أو الإيميل برقم طلبك وسبب الاسترجاع، وهنرتّب استلام المنتج.</p>
<h2>استرداد المبلغ</h2>
<p>بيتم بعد استلام المنتج ومراجعته، بنفس طريقة الدفع، خلال مدة نوضّحها لك وقت الطلب.</p>
""",
	"privacy": """
<h2>البيانات اللي بنجمعها</h2>
<p>اسمك ورقم موبايلك وبريدك وعنوان التوصيل — وده اللي محتاجينه عشان نوصّلك طلبك.</p>
<h2>ليه بنجمعها</h2>
<p>لتنفيذ الطلب والتواصل معاك بخصوصه، ولإرسال تأكيد الطلب وإشعار الشحن.</p>
<h2>مين بيشوفها</h2>
<p>فريق العمل عندنا، وشركة الشحن (الاسم والعنوان ورقم الموبايل بس عشان توصّلك).</p>
<h2>مدة الاحتفاظ</h2>
<p>بنحتفظ ببيانات الطلبات للسجلات المحاسبية.</p>
<h2>حقوقك</h2>
<p>تقدر تطلب نسخة من بياناتك أو تعديلها أو حذفها بالتواصل معانا.</p>
""",
	"terms": """
<h2>الطلب</h2>
<p>الطلب بيتأكد بعد ما تستلم رسالة التأكيد على بريدك. الأسعار المعروضة بالجنيه المصري.</p>
<h2>الدفع</h2>
<p>طرق الدفع المتاحة بتظهر في صفحة إتمام الطلب.</p>
<h2>الإلغاء</h2>
<p>تقدر تلغي الطلب قبل ما يخرج للشحن بالتواصل معانا.</p>
<h2>التوفّر</h2>
<p>لو منتج خلص بعد ما طلبته، هنتواصل معاك ونرجّعلك قيمته.</p>
<p><em>يُفضّل مراجعة الشروط دي مع محامٍ قبل النشر.</em></p>
""",
	"contact": """
<h2>تواصل معانا</h2>
<p>واتساب وتليفون: <strong>01092301212</strong></p>
<p>البريد: <strong>info@dpono.com</strong></p>
<h2>مواعيد الرد</h2>
<p>من السبت للخميس، من 10 صباحًا لـ 6 مساءً.</p>
""",
}

BOT_EXAMPLES = [
	{
		"question_ar": "بتوصّلوا لفين؟",
		"question_en": "Where do you deliver?",
		"category": "الشحن والتوصيل",
		"keywords_ar": "بتوصلوا, التوصيل, مناطق, محافظات, شحن, بتشحنوا",
		"keywords_en": "deliver, delivery, shipping, areas, governorates",
		"answer_ar": "<p>بنوصّل لكل محافظات مصر. التكلفة والمدة بتظهرلك في صفحة إتمام الطلب حسب محافظتك. التفاصيل في <a href='/page/shipping'>سياسة الشحن</a>.</p>",
		"answer_en": "<p>We deliver across Egypt. Cost and timing appear at checkout based on your governorate. See our <a href='/page/shipping'>shipping policy</a>.</p>",
	},
	{
		"question_ar": "أقدر أرجّع المنتج؟",
		"question_en": "Can I return a product?",
		"category": "الاسترجاع",
		"keywords_ar": "أرجع, ارجاع, استرجاع, مرتجع, استبدال",
		"keywords_en": "return, refund, exchange",
		"answer_ar": "<p>أيوة، خلال 14 يوم من الاستلام والمنتج بحالته الأصلية. التفاصيل في <a href='/page/returns'>سياسة الاسترجاع</a>.</p>",
		"answer_en": "<p>Yes, within 14 days of delivery if the product is unopened. See our <a href='/page/returns'>returns policy</a>.</p>",
	},
	{
		"question_ar": "عندكم أوزان إيه؟",
		"question_en": "What sizes do you have?",
		"category": "المنتجات",
		"keywords_ar": "أوزان, وزن, كيلو, جرام, حجم, عبوة, عبوات",
		"keywords_en": "size, sizes, weight, kilo, gram, pack",
		"answer_ar": "<p>عندنا أوزان مختلفة من كيس 10 جرام لحد عبوة الكيلو. اتفرّج على <a href='/products'>كل المنتجات</a>.</p>",
		"answer_en": "<p>From 10g sachets up to full kilos. Browse <a href='/products'>all products</a>.</p>",
	},
	{
		"question_ar": "الطلب هيوصل إمتى؟",
		"question_en": "When will my order arrive?",
		"category": "الشحن والتوصيل",
		"keywords_ar": "هيوصل امتى, مدة, كام يوم, التوصيل امتى",
		"keywords_en": "how long, when arrive, delivery time",
		"answer_ar": "<p>المدة المتوقعة بتظهرلك في صفحة المنتج وفي إتمام الطلب. لو محتاج تتأكد لطلب معيّن، ابعتلنا رقم الطلب.</p>",
		"answer_en": "<p>The estimate shows on the product page and at checkout. For a specific order, send us the order number.</p>",
	},
]


def _seed_pages():
	changed = []
	for slug, html in PAGE_EXAMPLES.items():
		if not frappe.db.exists("Webshop Page", slug):
			continue
		doc = frappe.get_doc("Webshop Page", slug)
		text = (doc.content_ar or "").strip()
		# Only replace the guidance text, never anything the owner wrote.
		if "اكتب هنا" in text or len(text) < 120:
			doc.content_ar = DRAFT_BANNER + html
			doc.published = 1
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.save()
			changed.append(slug)
	return changed


def _seed_bot():
	created = []
	for row in BOT_EXAMPLES:
		if frappe.db.exists("Webshop Bot Answer", row["question_ar"]):
			continue
		doc = frappe.get_doc({"doctype": "Webshop Bot Answer", "enabled": 1, **row})
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		created.append(row["question_ar"])
	return created


def _seed_shipping():
	"""A working courier with real Egyptian zones, so shipping can be seen."""
	if not frappe.db.exists("Webshop Shipping Company", "Bosta"):
		return None
	doc = frappe.get_doc("Webshop Shipping Company", "Bosta")
	if doc.enabled:
		return "already enabled"

	account = frappe.db.get_value(
		"Account",
		{"company": frappe.db.get_value("Company", {}, "name"), "is_group": 0, "root_type": "Income"},
		"name",
	)
	doc.label_ar = "توصيل للمنزل"
	doc.label_en = "Home delivery"
	doc.shipping_cost = 70
	doc.free_shipping_threshold = 1500
	doc.min_delivery_days = 2
	doc.max_delivery_days = 5
	doc.shipping_account = account
	doc.notes = "نموذج — عدّل الأسعار والمناطق حسب اتفاقك مع شركة الشحن."
	doc.set("zones", [])
	for zone in (
		("القاهرة الكبرى", "القاهرة, الجيزة, القليوبية", 45, 1000, 2),
		("الإسكندرية والدلتا", "الإسكندرية, البحيرة, الغربية, المنوفية, الدقهلية, كفر الشيخ", 60, 1200, 3),
		("الصعيد", "أسيوط, سوهاج, قنا, الأقصر, أسوان, المنيا, بني سويف", 85, 1800, 5),
	):
		doc.append("zones", {
			"zone_name": zone[0], "governorates": zone[1],
			"shipping_cost": zone[2], "free_shipping_threshold": zone[3], "delivery_days": zone[4],
		})
	doc.enabled = 1
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return f"Bosta enabled ({account})"


def execute():
	report = {
		"pages": _seed_pages(),
		"bot_answers": _seed_bot(),
		"shipping": _seed_shipping(),
	}
	frappe.db.commit()
	frappe.clear_cache()
	print("EXAMPLES=" + str(report))
