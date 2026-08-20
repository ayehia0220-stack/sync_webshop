# -*- coding: utf-8 -*-
import time
from sync_webshop.api import assistant

def execute():
    cat = assistant._skill_catalog(assistant.CUSTOMER_SKILLS, customer_only=True)
    for q in ("بكام كيلو البن؟", "عايز اعرف سعر المنتج", "فين طلبي؟"):
        t = time.time()
        try:
            a = assistant._local_pick_tool(q, cat)
        except Exception as exc:
            a = "خطأ: %s" % str(exc)[:80]
        print("  %-24s -> %-30s (%.1f ث)" % (q, a, time.time() - t))
