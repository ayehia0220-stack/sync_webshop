# -*- coding: utf-8 -*-
import re, frappe

def execute():
    rows = frappe.get_all("Error Log",
                          filters={"method": ["like", "%%auto_repeat%%"]},
                          fields=["name", "creation"], order_by="creation desc",
                          limit=60)
    seen = {}
    for r in rows:
        text = frappe.db.get_value("Error Log", r.name, "error") or ""
        m = re.findall(r"^(frappe\.exceptions\.\w+|\w+Error): (.+)$", text, re.M)
        key = "%s: %s" % m[-1] if m else "غير معروف"
        seen.setdefault(key[:120], [0, str(r.creation)[:10]])
        seen[key[:120]][0] += 1
    print("عدد سجلات الخطأ المفحوصة:", len(rows))
    for k, (n, last) in sorted(seen.items(), key=lambda x: -x[1][0]):
        print("  %3s مرة | آخر مرة %s | %s" % (n, last, k))
