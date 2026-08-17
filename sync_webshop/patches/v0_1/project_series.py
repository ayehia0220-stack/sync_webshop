# -*- coding: utf-8 -*-
"""
The project counter had fallen behind the projects.

PROJ- was sitting at 21, so the next project would be named PROJ-0022 — which
already exists. ERPNext refuses a duplicate name, and the message the team saw
was "already registered".

Projects run up to PROJ-0211 while the counter said 21, so this was not a
one-off: every attempt would fail until the counter passed the highest name in
use. It is moved past it, and a guard keeps it there if the same thing happens
again — a counter can drift after a restore, an import, or a manual rename.
"""
import re

import frappe

SERIES = "PROJ-"


def highest_used(prefix=SERIES):
	names = frappe.get_all("Project", pluck="name")
	pattern = re.compile(r"^%s(\d+)$" % re.escape(prefix))
	numbers = [int(m.group(1)) for n in names if (m := pattern.match(n or ""))]
	return max(numbers) if numbers else 0


HOOK = u'''

# ============================================================================
# ترقيم المشاريع
# ============================================================================

def keep_project_series_ahead(doc, method=None):
	"""
	Stop the naming counter colliding with a name already in use.

	The counter lives apart from the documents, so a restore, an import, or a
	renamed project can leave it behind — and every new project then fails with
	"already exists". Nudging it past the highest number in use costs nothing
	and turns a blocking error into a gap in the sequence.
	"""
	import re

	prefix = (doc.get("naming_series") or "PROJ-.####").split(".")[0]
	rows = frappe.db.sql(
		"SELECT name FROM `tabProject` WHERE name LIKE %s", prefix + "%", as_dict=True)
	pattern = re.compile(r"^%s(\\d+)$" % re.escape(prefix))
	used = [int(m.group(1)) for r in rows if (m := pattern.match(r.name or ""))]
	if not used:
		return

	current = frappe.db.sql(
		"SELECT current FROM `tabSeries` WHERE name = %s", prefix)
	current = current[0][0] if current else 0

	if current < max(used):
		frappe.db.sql(
			"UPDATE `tabSeries` SET current = %s WHERE name = %s", (max(used), prefix))
'''


def execute():
	import io

	top = highest_used()
	row = frappe.db.sql("SELECT current FROM `tabSeries` WHERE name = %s", SERIES)
	current = row[0][0] if row else 0
	print("counter=%s  highest project=%s" % (current, top))

	if current < top:
		frappe.db.sql("UPDATE `tabSeries` SET current = %s WHERE name = %s", (top, SERIES))
		print("counter moved to %s — next project will be PROJ-%04d" % (top, top + 1))
	else:
		print("counter already ahead")

	p = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"
	s = io.open(p, encoding="utf-8").read()
	if "def keep_project_series_ahead" not in s:
		io.open(p, "w", encoding="utf-8").write(s + HOOK)
		print("turbo.py: series guard")

	h = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/hooks.py"
	s = io.open(h, encoding="utf-8").read()
	if "keep_project_series_ahead" not in s:
		old = '\t"Sales Invoice": {'
		new = ('\t"Project": {\n'
		       '\t\t"before_insert": "sync_webshop.api.turbo.keep_project_series_ahead",\n'
		       '\t},\n'
		       '\t"Sales Invoice": {')
		if old not in s:
			frappe.throw("Sales Invoice hooks block not found")
		io.open(h, "w", encoding="utf-8").write(s.replace(old, new, 1))
		print("hooks: Project before_insert")

	frappe.db.commit()
	frappe.clear_cache()
	print("PROJECT SERIES READY")
