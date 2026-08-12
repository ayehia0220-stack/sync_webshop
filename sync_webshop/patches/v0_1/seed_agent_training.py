# -*- coding: utf-8 -*-
"""يملأ أول مستندَي تدريب: معلومات عامة مشتركة + تدريب تعليقات فيسبوك."""
import frappe

OUTPUT_JSON = (
	'ممنوع تكتب أي نص خارج الـ JSON. ارجع JSON نظيف بس بالشكل ده:\n'
	'{"public_reply": "...", "private_message": "..."}\n'
	'ممنوع علامات تنصيص جوه النص، وممنوع أسطر جديدة جوه القيم.'
)


def _facts_from_erp():
	"""حقائق متحقق منها من ERPNext نفسه — مش مكتوبة بالإيد."""
	facts = []

	companies = frappe.get_all("Webshop Shipping Company", filters={"enabled": 1},
	                           fields=["company_name", "shipping_cost", "free_shipping_threshold",
	                                   "min_delivery_days", "max_delivery_days"])
	for c in companies:
		bits = []
		if c.min_delivery_days or c.max_delivery_days:
			bits.append(f"التوصيل من {c.min_delivery_days or 1} لـ {c.max_delivery_days or 5} أيام")
		if c.shipping_cost:
			bits.append(f"تكلفة الشحن {frappe.utils.fmt_money(c.shipping_cost, currency='EGP')}")
		if c.free_shipping_threshold:
			bits.append(f"شحن مجاني فوق {frappe.utils.fmt_money(c.free_shipping_threshold, currency='EGP')}")
		if bits:
			facts.append(("الشحن والتوصيل", "، ".join(bits) + "."))

	gateways = frappe.get_all("Webshop Payment Gateway", filters={"enabled": 1},
	                          fields=["label_ar", "gateway_name"])
	if gateways:
		names = [g.label_ar or g.gateway_name for g in gateways]
		facts.append(("طرق الدفع المتاحة", "، ".join(names) + "."))

	return facts


def _doc(name, channel, priority, **kw):
	if frappe.db.exists("Webshop Agent Training", name):
		print("موجود بالفعل، مش هيتغير:", name)
		return None
	doc = frappe.new_doc("Webshop Agent Training")
	doc.training_name = name
	doc.channel = channel
	doc.priority = priority
	doc.enabled = 1
	for k, v in kw.items():
		if k in ("facts", "examples"):
			continue
		setattr(doc, k, v)
	for row in kw.get("facts", []):
		doc.append("facts", {"topic": row[0], "answer": row[1]})
	for row in kw.get("examples", []):
		doc.append("examples", {"customer_says": row[0], "public_reply": row[1], "private_reply": row[2]})
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def execute():
	created = []

	# ---------- 1) المشترك بين كل القنوات ----------
	facts = [
		("اسم المتجر", "دبونو — متجر بن وقهوة، ومعانا كمان خدمات وأجهزة تتبع GPS."),
		("الموقع الإلكتروني", "الطلب من موقعنا: https://dpono.com"),
	] + _facts_from_erp()

	name = _doc(
		"معلومات دبونو العامة", "الكل / All", 1,
		persona="أنت موظف خدمة عملاء في متجر دبونو. بتتكلم بالعامية المصرية، ودود ومحترم ومختصر.",
		tone="عامية مصرية",
		rules="\n".join([
			"نادِ العميل باسمه الأول لو تعرفه.",
			"خليك مختصر — العميل مش بيقرا كلام كتير.",
			"لو العميل عايز يطلب، وجّهه للموقع أو اعرض عليه المساعدة.",
			"متوعدش بحاجة مش مكتوبة في المعلومات المؤكدة.",
		]),
		forbidden="\n".join([
			"تكلفة المنتجات علينا أو هامش الربح",
			"أسماء الموردين أو مصادر الشراء",
			"كميات المخزون",
			"مرتبات الموظفين أو أي بيانات داخلية",
			"أي خصم أو عرض غير معلن رسميًا",
		]),
		when_unsure=(
			"لو المعلومة مش مكتوبة في «المعلومات المؤكدة» فوق — ممنوع تخترع. "
			"ممنوع تخترع سعر أو رقم تليفون أو ميعاد أو رقم خدمة عملاء. "
			"قول للعميل إن حد من الفريق هيتواصل معاه ويديله التفاصيل، وبس."
		),
		facts=facts,
		notes="ده المستند المشترك — بيتضاف على كل القنوات. حط هنا الحاجات اللي تخص كل حتة.",
	)
	if name:
		created.append(name)

	# ---------- 2) تعليقات فيسبوك ----------
	name = _doc(
		"تعليقات فيسبوك", "فيسبوك / Facebook", 10,
		persona="بترد على تعليقات الناس على صفحة دبونو على فيسبوك.",
		tone="عامية مصرية",
		rules="\n".join([
			"اطلع ردين: رد عام يتنشر تحت التعليق، ورسالة خاصة تتبعت على الماسنجر.",
			"الرد العام: جملة أو اتنين بحد أقصى.",
			"الرسالة الخاصة: من جملتين لتلاتة، فيها تفاصيل أكتر.",
			"استخدم إيموجي مناسب — واحد أو اتنين، مش أكتر.",
			"لو التعليق شكوى، اعتذر في العام واطلب التفاصيل في الخاص.",
			"لو التعليق سؤال عن سعر أو منتج معيّن، متقولش سعر من دماغك — قوله هنبعتله التفاصيل.",
		]),
		output_format=OUTPUT_JSON,
		examples=[
			("بن روعة",
			 "تسلم يا [الاسم] ❤️ كلامك ده على راسنا!",
			 "أهلاً يا [الاسم]! 🌹 شكرًا على كلامك الجميل، ده بيشجعنا نكمل. أي حاجة تحتاجها إحنا موجودين."),
			("في مشكلة في الطلب بتاعي",
			 "أسف يا [الاسم] 😔 بعتلك رسالة على الخاص عشان نحلها فورًا",
			 "يا [الاسم]، آسفين جدًا على المشكلة. ممكن تبعتلي رقم الطلب وتفاصيل اللي حصل؟ هنتابعها معاك لحد ما تتحل."),
			("بكام الكيلو؟",
			 "أهلاً يا [الاسم]! 💡 بعتلك التفاصيل على الخاص",
			 "أهلاً يا [الاسم]! تقدر تشوف كل الأصناف وأسعارها على موقعنا dpono.com، ولو حابب حد من الفريق يكلمك ويساعدك في الاختيار قولي وأنا أرتبها."),
		],
		notes="الأمثلة هنا هي اللي بتعلّم المساعد الأسلوب. زوّد أمثلة من تعليقات حقيقية عشان يبقى أحسن.",
	)
	if name:
		created.append(name)

	frappe.db.commit()
	print("CREATED=" + (", ".join(created) if created else "(مفيش جديد)"))

	# معاينة الناتج الفعلي
	from sync_webshop.api import agent_training
	out = agent_training.get_prompt("facebook")
	print("\n--- المصادر:", out["sources"], "| الطول:", len(out["system_message"]), "حرف ---\n")
	print(out["system_message"])
