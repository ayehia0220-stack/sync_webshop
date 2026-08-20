# -*- coding: utf-8 -*-
"""
كل حاجة تخص الأتمتة تبان في الصفحة — مش الورك فلوز بس.

اللي كان ناقص: تنبيهات ERPNext الأصلية (Notification)، التكرار التلقائي
(Auto Repeat)، وأرقام الواتساب نفسها — وهي أهم حاجة، لأن كل أتمتة
عندنا بتخرج من واحد منهم، ولو رقم وقع كل حاجة وراه بتقف.
"""
import ast
import io
import shutil
import time

P = ("/home/frappe/frappe-bench-15/apps/sync_webshop/"
     "sync_webshop/api/automation.py")

ANCHOR = "\tfor scr in frappe.get_all(\n\t\t\t\"Server Script\","

BLOCK = '''	for note in frappe.get_all(
			"Notification", fields=["name", "channel", "document_type",
			                        "event", "enabled"]):
		rows.append({
			"job_key": "erp:notify:%s" % note.name,
			"source": SOURCE_ERP,
			"job_name": "تنبيه: %s" % note.name,
			"is_active": cint(note.enabled),
			"last_run": None,
			"runs_7d": 0, "success_7d": 0, "error_7d": 0, "node_count": 0,
			"health": HEALTH_OK if cint(note.enabled) else HEALTH_STOPPED,
			"open_url": "/app/notification/%s" % note.name,
			"detail": "%s — %s / %s" % (note.channel or "",
			                            note.document_type or "", note.event or ""),
		})

	if frappe.db.exists("DocType", "Auto Repeat"):
		for rep in frappe.get_all(
				"Auto Repeat", fields=["name", "reference_doctype", "frequency",
				                       "status", "next_schedule_date"]):
			active = 1 if (rep.status or "") == "Active" else 0
			rows.append({
				"job_key": "erp:repeat:%s" % rep.name,
				"source": SOURCE_ERP,
				"job_name": "تكرار تلقائي: %s" % (rep.reference_doctype or rep.name),
				"is_active": active,
				"last_run": None,
				"runs_7d": 0, "success_7d": 0, "error_7d": 0, "node_count": 0,
				"health": HEALTH_OK if active else HEALTH_STOPPED,
				"open_url": "/app/auto-repeat/%s" % rep.name,
				"detail": "%s — الجاية %s" % (rep.frequency or "",
				                              rep.next_schedule_date or "—"),
			})

	_pull_whatsapp_lines(rows)

'''

LINES_FN = '''

def _pull_whatsapp_lines(rows):
	"""
	أرقام الواتساب نفسها.

	مش أتمتة بالمعنى الحرفي، بس كل أتمتة بتخرج من واحد منهم — ولو
	رقم اتفصل، الحملة والردود ورسايل الطلبات كلها بتقف من غير ما حد
	ياخد باله. فمكانه هنا.
	"""
	from sync_webshop.api.renewal import instance_health

	settings = frappe.get_single("Webshop Content Settings")
	for line in settings.get("wa_lines") or []:
		instance = (line.evo_instance or "").strip()
		if not instance:
			continue
		try:
			state = instance_health(instance, alert=0) or {}
			ok = cint(state.get("ok"))
			why = state.get("reason") or ""
		except Exception as exc:
			ok, why = 0, str(exc)[:120]

		sent = frappe.db.count("Renewal Conversation Log", {
			"direction": "صادر",
			"creation": [">=", add_days(now_datetime(), -WINDOW_DAYS)]}) \\
			if instance == "97" else 0

		rows.append({
			"job_key": "erp:waline:%s" % instance,
			"source": SOURCE_ERP,
			"job_name": "رقم واتساب: %s (%s)" % (line.line_name, instance),
			"is_active": cint(line.enabled),
			"last_run": now_datetime() if ok else None,
			"runs_7d": sent, "success_7d": sent, "error_7d": 0,
			"node_count": 0,
			"health": (HEALTH_STOPPED if not cint(line.enabled)
			           else HEALTH_OK if ok else HEALTH_ERRORS),
			"open_url": "/app/webshop-content-settings",
			"detail": "متصل ✓" if ok else ("مش متصل — %s" % why),
		})
'''


def execute():
	src = io.open(P, encoding="utf-8").read()
	if "_pull_whatsapp_lines" in src:
		print("  — متعدّل بالفعل")
		return
	if ANCHOR not in src:
		raise SystemExit("✗ مالقيتش مكان الإدراج")
	shutil.copy(P, P + ".bak-%s" % time.strftime("%Y%m%d-%H%M%S"))
	src = src.replace(ANCHOR, BLOCK + ANCHOR, 1)
	src = src.replace("\n\n# ————————————————————————————— الحفظ",
	                  LINES_FN + "\n\n# ————————————————————————————— الحفظ", 1)
	ast.parse(src)
	io.open(P, "w", encoding="utf-8").write(src)
	print("  ✓ اتضافوا: التنبيهات، التكرار التلقائي، أرقام الواتساب")
