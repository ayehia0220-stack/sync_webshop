# -*- coding: utf-8 -*-
"""
مساعد دبونو الموحّد — عقل واحد لكل القنوات.

المساعد القديم كان بيطابق كلمات: لو السؤال مصاغ بشكل مختلف عن المهارة
مبيفهمش ويرد رد افتراضي. هنا الموديل هو اللي **بيفهم** السؤال ويختار
المهارة المناسبة، والمهارة هي اللي بتجيب البيانات من ERPNext.

الصلاحيات مش في الموديل — في المهارة نفسها. كل استعلام بيمشي بصلاحيات
المستخدم عن طريق `frappe.set_user`، فالموديل ميقدرش يوصل لحاجة مش مسموح
بيها حتى لو حاول. والعميل معاه مهارات محدودة بترد على بياناته هو بس.
"""
import json
import random
import re

import frappe
import requests

from sync_webshop.api import agent as skills_module
from sync_webshop.api import agent_training
from sync_webshop.api import skills_extra

# مهارات إضافية مش مسجّلة في Webshop Agent Skill — بتتعرّف هنا مباشرة
EXTRA_TOOLS = [
	("salesperson_sales", "مبيعات المناديب — مندوب معيّن أو كلهم. مثال: مبيعات ضحى"),
	("overdue_invoices", "الفواتير المتأخرة اللي فات ميعاد سدادها وقيمتها"),
	("receivables", "إجمالي المستحق على العملاء وأكبر المديونيات"),
	("unbilled_deliveries", "إذون التسليم اللي اتسلّمت ولسه ما اتفوترتش"),
	("expiring_subscriptions", "اشتراكات GPS اللي قربت تنتهي أو انتهت"),
	("failed_numbers", "أرقام وقفت لأن الرسايل فشلت عليها ومحتاجة مراجعة"),
	("calls_summary", "ملخص مكالمات النهاردة — كام ردّينا وكام ضاع"),
	("missed_calls", "المكالمات اللي ضاعت ومحدش رجّع للعميل"),
	("customer_balance", "المستحق على عميل معيّن بالاسم. مثال: محمود إبراهيم عليه كام؟"),
	("turbo_collections", "فلوس شحنات تربو حسب حالة كل شحنة — التحصيلات عند الشركة"),
	("company_stats", "أرقام الشركة العامة: كام موظف، كام عميل، كام مورّد، كام صنف، "
	                  "كام مندوب، كام اشتراك. مثال: كام موظف موجود؟"),
	("staff_list", "أسماء الموظفين ووظايفهم وتحويلاتهم. مثال: مين الموظفين عندنا؟"),
	("find_name", "بيدوّر على أي اسم في النظام كله (عميل/مورّد/شريك بيع/مندوب/موظف/صنف) "
	              "ويقول هو إيه وإيه أرقامه. **استخدمها لما `customer_balance` مالقاش الاسم** "
	              "— الاسم ممكن يكون شريك بيع أو موظف مش عميل."),
]

# الاستعلام الحر — لمديري النظام بس
ADMIN_TOOLS = [
	{
		"name": "explore_system",
		"description": ("يقولك إيه الجداول الموجودة في ERPNext وكام سجل في كل واحد. "
		                "استخدمها الأول لما السؤال عن حاجة مش في المهارات الجاهزة."),
		"parameters": {
			"type": "object",
			"properties": {"question": {"type": "string", "description": "كلمات تدوّر بيها"}},
			"required": ["question"],
		},
	},
	{
		"name": "query_system",
		"description": ("استعلام حر على أي جدول في ERPNext — قراءة بس. استخدمها لما "
		                "السؤال محتاج بيانات مش موجودة في المهارات الجاهزة."),
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string", "description": "اسم الجدول بالظبط، مثل Sales Invoice"},
				"filters": {"type": "string", "description": 'شروط JSON، مثل {"status":"Overdue"}'},
				"fields": {"type": "string", "description": 'حقول JSON، مثل ["name","customer"]'},
				"limit": {"type": "integer", "description": "عدد النتائج (حد أقصى 30)"},
				"order_by": {"type": "string", "description": "ترتيب، مثل creation desc"},
			},
			"required": ["doctype"],
		},
	},
]

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"

# المهارات المسموحة لكل نوع سائل. العميل مايشوفش أرقام الشركة.
STAFF_SKILLS = [
	"sales_today", "sales_month", "open_orders", "order_status", "customer_orders",
	"item_stock", "item_price", "low_stock", "top_customers", "at_risk_customers",
	"webshop_orders", "failed_numbers", "help",
]
CUSTOMER_SKILLS = ["item_price", "order_status", "help"]

# مواضيع بترفض قبل ما توصل للموديل أصلًا
BLOCKED = [
	"تكلفة", "التكلفة", "هامش", "الهامش", "ربح", "الربح", "مورد", "المورد",
	"موردين", "مرتب", "المرتبات", "راتب", "صافي الربح", "cost", "margin", "profit",
	"supplier", "salary",
]


def _settings():
	return frappe.get_single("Webshop Agent Settings")


def _model_keys():
	"""كل مفاتيح Gemini المتاحة، بالترتيب: الأول هو الأساسي.

	**المفتاح الأول في الإعدادات لازم يكون المفتاح المدفوع.** الباقي
	احتياطي بيتجرّب بالترتيب لو الأساسي وقع.

	قبل كده كان الترتيب بيتخلط عشوائي عشان يوزّع الحمل بين مفاتيح
	مجانية متساوية. ده بقى ضار بعد ما بقى فيه مفتاح مدفوع: الخلط
	معناه إن جزء من الطلبات يروح لمفتاح مجاني ويقع لما حصته تخلص.
	"""
	content = frappe.get_single("Webshop Content Settings")
	raw = content.get_password("gemini_api_key", raise_exception=False) or ""
	keys = []
	for k in re.split(r"[,\s\n]+", raw):
		k = k.strip()
		if len(k) > 20 and k not in keys:
			keys.append(k)
	return keys


def _skill_catalog(allowed, customer_only=False):
	"""المهارات المتاحة بصيغة أدوات يفهمها الموديل."""
	rows = frappe.get_all(
		"Webshop Agent Skill",
		filters={"enabled": 1, "action": ["in", allowed]},
		fields=["skill_name", "action", "example_question"],
	)
	tools = []
	for r in rows:
		desc = r.skill_name
		if r.example_question:
			desc += f" — مثال على سؤال ليها: {r.example_question}"
		tools.append({
			"name": r.action,
			"description": desc,
			"parameters": {
				"type": "object",
				"properties": {
					"question": {
						"type": "string",
						"description": "سؤال المستخدم كما هو — المهارة بتستخرج منه الاسم أو الرقم لو محتاجة",
					}
				},
				"required": ["question"],
			},
		})

	# المهارات الإضافية — مش محتاجة سجل في Webshop Agent Skill
	if not customer_only:
		for action, desc in EXTRA_TOOLS:
			tools.append({
				"name": action,
				"description": desc,
				"parameters": {
					"type": "object",
					"properties": {
						"question": {"type": "string", "description": "سؤال المستخدم كما هو"}
					},
					"required": ["question"],
				},
			})
		# الاستعلام الحر: بيخلي المساعد يوصل لأي بيانات في النظام، فمقصور
		# على مديري النظام — وحتى معاهم بيمشي بصلاحياتهم الفعلية.
		if _is_admin():
			tools.extend(ADMIN_TOOLS)
	return tools


def _is_admin():
	return "System Manager" in frappe.get_roles()


def _run_skill(action, args, question, allowed=None):
	"""بينفّذ المهارة بصلاحيات المستخدم الحالي.

	بنتحقق من القائمة تاني هنا — الموديل ممكن يخترع اسم أداة، والاعتماد
	على إننا مبعتناش الأداة ليه مش كفاية.
	"""
	if allowed is not None and action not in allowed:
		return None

	# الاستعلام الحر لمديري النظام بس، ومهما كان بيمشي بصلاحيات المستخدم
	if action in ("explore_system", "query_system"):
		if not _is_admin():
			return "الاستعلام ده متاح لمديري النظام بس."
		fn = getattr(skills_extra, f"act_{action}")
		try:
			if action == "explore_system":
				return fn(args.get("question") or question)
			return fn(
				doctype=args.get("doctype"), filters=args.get("filters"),
				fields=args.get("fields"), limit=args.get("limit") or 10,
				order_by=args.get("order_by"), question=question,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"assistant {action}")
			return None

	fn = getattr(skills_module, f"act_{action}", None) or getattr(skills_extra, f"act_{action}", None)
	if not fn:
		return None
	try:
		return fn(args.get("question") or question)
	except frappe.PermissionError:
		return "المعلومة دي مش ضمن صلاحياتك."
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"assistant skill {action}")
		return None


def _call_gemini(keys, model, system, history, tools):
	"""بيجرّب المفاتيح بالترتيب لحد ما واحد يرد.

	429 معناه الحصة المجانية خلصت للمفتاح ده — بننتقل للي بعده على طول.
	"""
	body = {
		"system_instruction": {"parts": [{"text": system}]},
		"contents": history,
		"generationConfig": {"temperature": 0.3, "maxOutputTokens": 900},
	}
	if tools:
		body["tools"] = [{"function_declarations": tools}]
	data = json.dumps(body, ensure_ascii=False).encode("utf-8")

	last_error = ""
	for key in keys:
		try:
			r = requests.post(
				GEMINI_URL.format(model=model) + f"?key={key}",
				headers={"Content-Type": "application/json"},
				data=data,
				timeout=45,
			)
		except Exception as exc:
			last_error = str(exc)[:200]
			continue
		if r.status_code < 300:
			return r.json()
		last_error = r.text[:300]
		if r.status_code != 429:
			break   # مش مشكلة حصة — تجربة مفتاح تاني مش هتفرق
	frappe.log_error(f"كل المفاتيح فشلت ({len(keys)}): {last_error}", "assistant gemini")
	return None


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LOCAL_MODEL = "qwen2.5:7b"


def _local_pick_tool(question, tools):
	"""الموديل المحلي بيختار الأداة — الجزء المتكرر اللي بيستهلك حصة Gemini.

	بنطلب JSON مباشرة بدل واجهة الأدوات: Ollama بيكسر صيغة `tool_calls`
	مع الموديل ده، لكن وضع JSON شغّال ودقيق.
	"""
	if not tools:
		return None
	catalog = "\n".join(f"{t['name']} = {t['description'][:90]}" for t in tools)
	prompt = (
		f"عندك الأدوات دي:\n{catalog}\nnone = مفيش أداة مناسبة\n\n"
		f"سؤال المستخدم: {question}\n\n"
		'رد بـ JSON فقط بالشكل: {"tool": "اسم_الأداة"}'
	)
	try:
		r = requests.post(OLLAMA_URL, timeout=40, data=json.dumps({
			"model": LOCAL_MODEL, "stream": False, "format": "json",
			"options": {"temperature": 0.1, "num_predict": 120},
			"prompt": prompt,
		}, ensure_ascii=False).encode("utf-8"))
		if r.status_code >= 300:
			return None
		picked = json.loads(r.json().get("response") or "{}").get("tool")
	except Exception:
		return None

	if not picked or picked == "none":
		return None
	return picked if any(t["name"] == picked for t in tools) else None


def _local_compose(question, data):
	"""صياغة الرد محليًا — بتتستخدم بس لما Gemini مش متاح.

	عربيته مكسورة شوية (بيخلط كلمات أجنبية)، بس أمين ومبيخترعش أرقام،
	وده أهم من الصياغة لما البديل إن المستخدم ميردش عليه حد.
	"""
	prompt = (
		"انت مساعد لشركة دبونو. بتتكلم عامية مصرية بس، مختصر ومحترم.\n"
		"ممنوع تخترع أي رقم — الأرقام من البيانات المديّة ليك بس.\n"
		"ممنوع تكتب أي كلمة بلغة غير العربية.\n\n"
		f"سؤال المستخدم: {question}\n\nالبيانات من النظام:\n{data}\n\nاكتب الرد:"
	)
	try:
		r = requests.post(OLLAMA_URL, timeout=60, data=json.dumps({
			"model": LOCAL_MODEL, "stream": False,
			"options": {"temperature": 0.3, "num_predict": 350},
			"prompt": prompt,
		}, ensure_ascii=False).encode("utf-8"))
		if r.status_code >= 300:
			return None
		return (r.json().get("response") or "").strip() or None
	except Exception:
		return None


def _first_part(payload):
	try:
		return payload["candidates"][0]["content"]["parts"][0]
	except (KeyError, IndexError, TypeError):
		return {}


def _log(question, reply, channel, action=None):
	if not _settings().get("log_conversations"):
		return
	try:
		doc = frappe.new_doc("Webshop Agent Log")
		doc.question = question[:500]
		doc.response = str(reply)[:2000]
		for field, value in (("channel", channel), ("skill", action), ("outcome", "answered")):
			if doc.meta.get_field(field):
				doc.set(field, value)
		doc.flags.ignore_permissions = True
		doc.insert()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "assistant log")


def _recent_turns(channel, limit=3):
	"""آخر أسئلة وردود للمستخدم ده — عشان «مين هما؟» يبقى ليها سياق."""
	try:
		rows = frappe.get_all(
			"Webshop Agent Log",
			filters={"owner": frappe.session.user},
			fields=["question", "response"],
			order_by="creation desc",
			limit=limit,
		)
	except Exception:
		return []
	turns = []
	for r in reversed(rows):
		if not r.question:
			continue
		turns.append({"role": "user", "parts": [{"text": r.question}]})
		turns.append({"role": "model", "parts": [{"text": str(r.response or "")[:600]}]})
	return turns


@frappe.whitelist()
def ask(question, channel="ERP", customer=None):
	"""نقطة الدخول الوحيدة لكل القنوات."""
	settings = _settings()
	if not settings.get("enabled"):
		return {"ok": False, "reply": "المساعد مش شغّال دلوقتي."}

	question = str(question or "").strip()[:500]
	if len(question) < 2:
		return {"ok": False, "reply": "اكتب سؤالك."}

	low = question.lower()
	if any(word in low for word in BLOCKED):
		return {"ok": True, "reply": "المعلومة دي داخلية ومش بتتقال. اسألني في حاجة تانية وأنا تحت أمرك."}

	is_customer = bool(customer) or channel in ("website", "whatsapp", "facebook", "telegram")
	allowed = CUSTOMER_SKILLS if is_customer else STAFF_SKILLS

	def _fallback():
		"""المساعد القديم بيدوّر في كل المهارات من غير فلترة صلاحيات، فهو
		آمن للموظف بس. العميل بياخد رد محايد بدل ما نسرّب أرقام الشركة."""
		if is_customer:
			return {"ok": True,
			        "reply": "مش قادر أجاوب على ده دلوقتي. حد من الفريق هيتواصل معاك."}
		return skills_module.answer(question, channel=channel)

	keys = _model_keys()
	tools_preview = _skill_catalog(allowed, customer_only=is_customer)

	# الموديل المحلي بيختار الأداة الأول: بيوفّر نداء كامل من حصة Gemini،
	# ولو Gemini مش متاح خالص بيبقى هو الطريق الوحيد للرد بدل «مش فاهم».
	local_action = _local_pick_tool(question, tools_preview)
	local_result = None
	if local_action:
		local_result = _run_skill(local_action, {}, question,
		                          allowed if is_customer else None)

	if not keys:
		# مفيش Gemini — نصيغ محليًا لو معانا بيانات
		if local_result:
			# الموديل المحلي بيحرّف الأسماء والأرقام لما يعيد الصياغة (قال
			# «علي زويل تحويلة 67» وهي بتاعة حد تاني). البيانات الخام أصلًا
			# متنسّقة وواضحة، فبنرجّعها زي ما هي — أفضل من رد جميل وغلط.
			_log(question, local_result, channel, local_action)
			return {"ok": True, "reply": str(local_result), "skill": local_action,
			        "engine": "local"}
		return _fallback()

	training = agent_training.get_prompt(channel).get("system_message") or ""
	system = (
		training
		+ "\n\n## إزاي ترد\n"
		"- عندك أدوات بتجيب بيانات حقيقية من نظام ERPNext. استخدمها لما السؤال محتاج رقم أو بيانات.\n"
		"- لو السؤال عام أو ترحيب، رد من غير أدوات.\n"
		"- لما الأداة ترجّع بيانات، لخّصها بالعربي بشكل واضح ومختصر — متكتبش جداول طويلة.\n"
		"- لو الأداة مرجّعتش حاجة، قول مفيش نتائج، **ومتخترعش أرقام**.\n"
		"- الأرقام اللي بتقولها لازم تكون من الأدوات بس.\n"
		"- لو السؤال محتاج أكتر من معلومة، استخدم أكتر من أداة واجمع الإجابة.\n"
		"- انت **بتقرا بس**: لو حد طلب تعديل أو مسح أو إضافة، قوله إنك مش بتنفّذ "
		"تعديلات وإنه يعملها بنفسه من ERPNext.\n"
		"- **ممنوع تقول «مش عارف» أو «مش فاهم» من غير ما تحاول.** لو مفيش مهارة "
		"جاهزة للسؤال، استخدم `explore_system` تشوف الجداول، وبعدين `query_system` "
		"تجيب البيانات بنفسك. جرّب الأول وبعدين قول لو فعلًا مفيش.\n"
	)
	if is_customer:
		system += "- انت بتكلم عميل: ممنوع تقول أي أرقام تخص الشركة (مبيعات، مخزون، عملاء تانيين).\n"

	model = settings.get("model_name") or DEFAULT_MODEL
	tools = tools_preview
	history = _recent_turns(channel) + [{"role": "user", "parts": [{"text": question}]}]

	payload = _call_gemini(keys, model, system, history, tools)
	if not payload:
		# Gemini وقع (حصة أو شبكة) — نستخدم اللي جابه المحلي
		if local_result:
			# الموديل المحلي بيحرّف الأسماء والأرقام لما يعيد الصياغة (قال
			# «علي زويل تحويلة 67» وهي بتاعة حد تاني). البيانات الخام أصلًا
			# متنسّقة وواضحة، فبنرجّعها زي ما هي — أفضل من رد جميل وغلط.
			_log(question, local_result, channel, local_action)
			return {"ok": True, "reply": str(local_result), "skill": local_action,
			        "engine": "local"}
		return _fallback()

	part = _first_part(payload)
	action, last_result = None, None

	# السؤال المركّب («قارن النهاردة بالشهر») محتاج أكتر من أداة، فبندور
	# لحد ما الموديل يبطّل يطلب أدوات — بحد أقصى تلاتة عشان ميلفش للأبد.
	for _ in range(5):
		if "functionCall" not in part:
			break
		call = part["functionCall"]
		action = call.get("name")
		args = call.get("args") or {}
		result = _run_skill(action, args, question, allowed if is_customer else None)
		last_result = result if result is not None else last_result

		history.append({"role": "model", "parts": [part]})
		history.append({
			"role": "user",
			"parts": [{
				"functionResponse": {
					"name": action,
					"response": {"result": str(result) if result is not None else "مفيش نتائج"},
				}
			}],
		})
		payload = _call_gemini(keys, model, system, history, tools)
		if not payload:
			break
		part = _first_part(payload)

	if not part.get("text") and last_result:
		# الموديل ما صاغش — نرجّع نتيجة المهارة زي ما هي بدل ما نضيّعها
		_log(question, last_result, channel, action)
		return {"ok": True, "reply": str(last_result), "skill": action}

	reply = (part.get("text") or "").strip()
	if not reply:
		return _fallback()

	_log(question, reply, channel, action)
	return {"ok": True, "reply": reply, "skill": action}


@frappe.whitelist(allow_guest=True)
def ask_public(question, channel="website"):
	"""للقنوات العامة — مهارات العميل بس، ومن غير بيانات الشركة."""
	return ask(question, channel=channel, customer="guest")
