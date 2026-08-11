# -*- coding: utf-8 -*-
"""
Two fixes found by actually shipping something.

  * Turbo answers add-order with {"result": {"code": …, "bar_code": …}}. The
    code was reading "feed"/"data", so the tracking number came back empty and
    the order had no way to reference the shipment it had just created.

  * receiver was taking Sales Order.customer_name, which is the phone number
    whenever the customer record was matched by phone. The courier would have
    called asking for "+201114021275". The name the shopper typed is on the
    address, so that is used first.
"""
import io

P = "/home/frappe/frappe-bench-15/apps/sync_webshop/sync_webshop/api/turbo.py"


def execute():
	s = io.open(P, encoding="utf-8").read()

	# --- 1. read the tracking number from where Turbo actually puts it -------
	old = '''	feed = result.get("feed") or result.get("data") or {}
	number = (feed.get("order_number") or feed.get("code")
	          or feed.get("id") or result.get("id"))

	order.db_set({
		"turbo_order_number": str(number or ""),
		"turbo_error": None,
		"turbo_last_sync": now_datetime(),
	}, update_modified=False)'''
	new = '''	# Turbo replies {"result": {"code": …, "bar_code": …, "expected_branch": …}}.
	feed = result.get("result") or result.get("feed") or result.get("data") or {}
	number = feed.get("code") or feed.get("bar_code") or feed.get("order_number")
	if not number:
		msg = "Turbo accepted the order but returned no code: %s" % str(result)[:300]
		order.db_set("turbo_error", msg, update_modified=False)
		frappe.log_error(title="Turbo add-order without code", message=msg)
		return {"ok": False, "message": msg}

	order.db_set({
		"turbo_order_number": str(number),
		"turbo_branch": (feed.get("expected_branch") or "")[:140] or None,
		"turbo_error": None,
		"turbo_last_sync": now_datetime(),
	}, update_modified=False)'''
	assert old in s, "response block not found"
	s = s.replace(old, new, 1)

	# --- 2. a person's name, not their phone number --------------------------
	old = '''	payload = {
		"receiver": order.customer_name or order.customer,'''
	new = '''	# customer_name is the phone whenever the customer was matched by phone, so
	# the name the shopper actually typed — kept on the address — comes first.
	receiver = (addr.address_title or "").replace(" - Web", "").strip()
	if not receiver or receiver.startswith("+"):
		receiver = order.customer_name or order.customer

	payload = {
		"receiver": receiver,'''
	assert old in s, "payload block not found"
	s = s.replace(old, new, 1)

	io.open(P, "w", encoding="utf-8").write(s)
	print("turbo.py fixed")
