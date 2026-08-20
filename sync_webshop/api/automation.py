# -*- coding: utf-8 -*-
"""
شاشة «الأتمتة» — كل ورك فلو في مكان واحد.

الفكرة: n8n و ERPNext الاتنين بيشغّلوا أتمتة، وماكانش فيه مكان واحد
تشوف منه الاتنين. الملف ده بيسحب حالة الورك فلوز من n8n عن طريق الـ API
بتاعه، وبيقرأ أتمتة الـ ERP من جواه، ويحطّهم كلهم في «Automation Job».

الصفحة نفسها تقرير عادي بيقرأ من الجدول ده — عشان فتح الصفحة يبقى
فوري ومايستناش n8n يرد.
"""

import frappe
import requests
from frappe.utils import add_days, cint, get_datetime, now_datetime

SOURCE_N8N = "n8n"
SOURCE_ERP = "ERPNext"

HEALTH_OK = "شغال"
HEALTH_STOPPED = "متوقف"
HEALTH_DEAD = "ميت"
HEALTH_ERRORS = "فيه أخطاء"

WINDOW_DAYS = 7
# ورك فلو مفعّلة وماشتغلتش من أسبوعين = حد نسي يقفلها
DEAD_AFTER_DAYS = 14
# نسبة الفشل اللي بعدها نقول «فيه أخطاء»
ERROR_RATE = 0.10


# ————————————————————————————— الإعدادات —————————————————————————————

def _n8n():
	"""عنوان n8n ومفتاحه، أو None لو لسه مااتظبطوش."""
	s = frappe.get_single("Webshop API Settings")
	url = (s.get("n8n_url") or "").strip().rstrip("/")
	if not url:
		return None
	try:
		key = s.get_password("n8n_api_key", raise_exception=False)
	except Exception:
		key = None
	if not key:
		return None
	return frappe._dict({"url": url, "key": key})


def _get(cfg, path, params=None):
	r = requests.get(
		"%s/api/v1/%s" % (cfg.url, path.lstrip("/")),
		headers={"X-N8N-API-KEY": cfg.key, "Accept": "application/json"},
		params=params or {}, timeout=30)
	r.raise_for_status()
	return r.json() or {}


def _pages(cfg, path, params=None, max_pages=40):
	"""n8n بيرجّع النتايج على صفحات بـ cursor — بنلفّ عليها كلها."""
	params = dict(params or {})
	for _ in range(max_pages):
		data = _get(cfg, path, params)
		rows = data.get("data") or []
		if not rows:
			return
		for row in rows:
			yield row
		cursor = data.get("nextCursor")
		if not cursor:
			return
		params["cursor"] = cursor


# ————————————————————————————— السحب من n8n —————————————————————————————

def _execution_stats(cfg, since):
	"""
	كام مرة اشتغلت كل ورك فلو وكام نجحت وكام فشلت خلال آخر أسبوع.

	التنفيذات بترجع الأحدث الأول، فأول ما نوصل لحاجة أقدم من الأسبوع
	بنقف — مش محتاجين نجيب تاريخ n8n كله عشان صفحة واحدة.
	"""
	stats = {}
	for row in _pages(cfg, "executions", {"limit": 250, "includeData": "false"}):
		started = row.get("startedAt") or row.get("createdAt")
		if not started:
			continue
		when = get_datetime(str(started).replace("Z", "").replace("T", " ")[:19])
		if when < since:
			break
		wid = str(row.get("workflowId") or "")
		if not wid:
			continue
		box = stats.setdefault(wid, {"runs": 0, "ok": 0, "err": 0, "last": None})
		box["runs"] += 1
		if (row.get("status") or "") == "success":
			box["ok"] += 1
		elif (row.get("status") or "") in ("error", "crashed", "failed"):
			box["err"] += 1
		if not box["last"] or when > box["last"]:
			box["last"] = when
	return stats


def _last_run_ever(cfg, workflow_id):
	"""آخر مرة اشتغلت فيها — حتى لو من شهور. ده اللي بيكشف الميتة."""
	data = _get(cfg, "executions",
	            {"limit": 1, "includeData": "false", "workflowId": workflow_id})
	rows = data.get("data") or []
	if not rows:
		return None
	started = rows[0].get("startedAt") or rows[0].get("createdAt")
	if not started:
		return None
	return get_datetime(str(started).replace("Z", "").replace("T", " ")[:19])


def _health(is_active, last_run, runs, errors, has_run_data=True):
	if not is_active:
		return HEALTH_STOPPED
	# مهام الـ ERP مافيهاش عدّاد تشغيل، فبنحكم على آخر مرة بس
	if not has_run_data:
		if not last_run:
			return HEALTH_OK
		return (HEALTH_OK if last_run >= add_days(now_datetime(), -DEAD_AFTER_DAYS)
		        else HEALTH_DEAD)
	# مفعّلة وماشتغلتش ولا مرة خلال الأسبوع = حد نسي يقفلها، أو حاجة
	# بتنده عليها اتقفلت من غير ما ياخد باله
	if not runs:
		return HEALTH_DEAD
	if not last_run or last_run < add_days(now_datetime(), -DEAD_AFTER_DAYS):
		return HEALTH_DEAD
	if runs and errors and (float(errors) / runs) > ERROR_RATE:
		return HEALTH_ERRORS
	return HEALTH_OK


def _pull_n8n(cfg, rows):
	since = add_days(now_datetime(), -WINDOW_DAYS)
	stats = _execution_stats(cfg, since)

	for wf in _pages(cfg, "workflows", {"limit": 100, "excludePinnedData": "true"}):
		if wf.get("isArchived"):
			continue
		wid = str(wf.get("id") or "")
		if not wid:
			continue
		box = stats.get(wid) or {"runs": 0, "ok": 0, "err": 0, "last": None}
		last = box["last"]
		is_active = 1 if wf.get("active") else 0

		# مش موجودة في آخر أسبوع؟ نسأل n8n عن آخر مرة اشتغلت أصلًا —
		# بس للمفعّلة، عشان مانضيعش نداءات على 49 ورك فلو مقفولة.
		if not last and is_active:
			try:
				last = _last_run_ever(cfg, wid)
			except Exception:
				last = None

		rows.append({
			"job_key": "n8n:%s" % wid,
			"source": SOURCE_N8N,
			"job_name": wf.get("name") or wid,
			"is_active": is_active,
			"last_run": last,
			"runs_7d": box["runs"], "success_7d": box["ok"], "error_7d": box["err"],
			"node_count": len(wf.get("nodes") or []),
			"health": _health(is_active, last, box["runs"], box["err"]),
			"open_url": "%s/workflow/%s" % (cfg.url, wid),
			"detail": "",
		})


# ————————————————————————————— أتمتة الـ ERP —————————————————————————————

def _pull_erpnext(rows):
	"""
	الـ ERP بيشغّل أتمتة كمان — مواعيد مجدولة وويب هوك وسكربتات.
	من غيرها الصفحة بتوريك نص الصورة.
	"""
	for job in frappe.get_all(
			"Scheduled Job Type",
			filters={"method": ["like", "%%sync_webshop%%"]},
			fields=["name", "method", "frequency", "stopped", "last_execution"]):
		active = 0 if job.stopped else 1
		rows.append({
			"job_key": "erp:job:%s" % job.name,
			"source": SOURCE_ERP,
			"job_name": job.method,
			"is_active": active,
			"last_run": job.last_execution,
			"runs_7d": 0, "success_7d": 0, "error_7d": 0, "node_count": 0,
			"health": _health(active, job.last_execution, 0, 0, has_run_data=False),
			"open_url": "/app/scheduled-job-type/%s" % job.name,
			"detail": "مهمة مجدولة — %s" % (job.frequency or ""),
		})

	for hook in frappe.get_all(
			"Webhook", fields=["name", "webhook_doctype", "webhook_docevent",
			                   "request_url", "enabled"]):
		rows.append({
			"job_key": "erp:hook:%s" % hook.name,
			"source": SOURCE_ERP,
			"job_name": "ويب هوك: %s — %s" % (hook.webhook_doctype or "",
			                                  hook.webhook_docevent or ""),
			"is_active": cint(hook.enabled),
			"last_run": None,
			"runs_7d": 0, "success_7d": 0, "error_7d": 0, "node_count": 0,
			"health": HEALTH_OK if cint(hook.enabled) else HEALTH_STOPPED,
			"open_url": "/app/webhook/%s" % hook.name,
			"detail": (hook.request_url or "")[:200],
		})

	for scr in frappe.get_all(
			"Server Script",
			filters={"script_type": ["in", ["DocType Event", "Scheduler Event"]]},
			fields=["name", "script_type", "reference_doctype", "disabled"]):
		active = 0 if cint(scr.disabled) else 1
		rows.append({
			"job_key": "erp:script:%s" % scr.name,
			"source": SOURCE_ERP,
			"job_name": "سكربت: %s" % scr.name,
			"is_active": active,
			"last_run": None,
			"runs_7d": 0, "success_7d": 0, "error_7d": 0, "node_count": 0,
			"health": HEALTH_OK if active else HEALTH_STOPPED,
			"open_url": "/app/server-script/%s" % scr.name,
			"detail": "%s — %s" % (scr.script_type, scr.reference_doctype or ""),
		})


# ————————————————————————————— الحفظ —————————————————————————————

def _save(rows):
	existing = {d.job_key: d.name for d in frappe.get_all(
		"Automation Job", fields=["name", "job_key"])}
	seen = set()
	for row in rows:
		seen.add(row["job_key"])
		name = existing.get(row["job_key"])
		if name:
			frappe.db.set_value("Automation Job", name, row, update_modified=True)
		else:
			doc = frappe.get_doc(dict(doctype="Automation Job", **row))
			doc.insert(ignore_permissions=True)

	# ورك فلو اتمسحت من n8n مايبقاش لها سطر هنا
	for key, name in existing.items():
		if key not in seen:
			frappe.delete_doc("Automation Job", name,
			                  force=1, ignore_permissions=True)
	frappe.db.commit()
	return len(seen)


@frappe.whitelist()
def sync_workflows():
	"""بينده كل ربع ساعة، وكمان من زرار «حدّث» في الصفحة."""
	rows = []
	note = ""
	cfg = _n8n()
	if cfg:
		try:
			_pull_n8n(cfg, rows)
		except Exception as exc:
			note = str(exc)[:200]
			frappe.log_error(title="Automation sync — n8n",
			                 message=frappe.get_traceback()[:2000])
	else:
		note = "n8n مش متظبط في إعدادات الـ API"

	_pull_erpnext(rows)
	count = _save(rows)
	return {"ok": not note, "count": count, "note": note}


# ————————————————————————————— أزرار الصفحة —————————————————————————————

@frappe.whitelist()
def set_active(job, active):
	"""فعّل أو اقفل ورك فلو في n8n من غير ما تفتحه."""
	doc = frappe.get_doc("Automation Job", job)
	if doc.source != SOURCE_N8N:
		frappe.throw("ده مش ورك فلو n8n — اتظبط من صفحته في الـ ERP")
	cfg = _n8n()
	if not cfg:
		frappe.throw("n8n مش متظبط في إعدادات الـ API")

	wid = doc.job_key.split(":", 1)[1]
	verb = "activate" if cint(active) else "deactivate"
	r = requests.post("%s/api/v1/workflows/%s/%s" % (cfg.url, wid, verb),
	                  headers={"X-N8N-API-KEY": cfg.key}, timeout=30)
	if r.status_code >= 300:
		frappe.throw("n8n رفض: %s" % r.text[:200])

	frappe.db.set_value("Automation Job", job, "is_active", cint(active))
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def summary():
	"""الأرقام اللي فوق الصفحة."""
	rows = frappe.get_all("Automation Job",
	                      fields=["source", "is_active", "health", "error_7d"])
	return {
		"total": len(rows),
		"active": len([r for r in rows if r.is_active]),
		"n8n": len([r for r in rows if r.source == SOURCE_N8N]),
		"erp": len([r for r in rows if r.source == SOURCE_ERP]),
		"dead": len([r for r in rows if r.health == HEALTH_DEAD]),
		"errors": len([r for r in rows if r.health == HEALTH_ERRORS]),
	}
