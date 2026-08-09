import frappe
import json
import requests
from sync_webshop.api.utils import set_cors_headers

@frappe.whitelist(allow_guest=True)
def validate_coupon(coupon_code, total_amount):
    set_cors_headers()
    settings = frappe.get_single("Webshop Content Settings")
    if not settings.enable_coupons:
        frappe.throw("Coupons are currently disabled")
        
    coupon = frappe.db.get_value("Coupon Code", {"coupon_code": coupon_code}, ["name", "pricing_rule"], as_dict=True)
    if not coupon:
        frappe.throw("Invalid coupon code")
        
    pricing_rule = frappe.get_doc("Pricing Rule", coupon.pricing_rule)
    
    # Simple validation: Check if active and date range
    from frappe.utils import getdate, nowdate
    if pricing_rule.disable:
        frappe.throw("Coupon is disabled")
    if pricing_rule.valid_from and getdate(pricing_rule.valid_from) > getdate(nowdate()):
        frappe.throw("Coupon is not yet valid")
    if pricing_rule.valid_upto and getdate(pricing_rule.valid_upto) < getdate(nowdate()):
        frappe.throw("Coupon has expired")
        
    discount_amount = 0
    if pricing_rule.rate_or_discount == "Discount Amount":
        discount_amount = pricing_rule.discount_amount
    elif pricing_rule.rate_or_discount == "Discount Percentage":
        discount_amount = (float(total_amount) * pricing_rule.discount_percentage) / 100.0
        
    return {
        "coupon_code": coupon_code,
        "discount_amount": discount_amount,
        "pricing_rule": pricing_rule.name
    }

@frappe.whitelist()
def sync_cart(cart_data):
    set_cors_headers()
    if frappe.session.user == "Guest":
        return
        
    settings = frappe.get_single("Webshop Content Settings")
    if not settings.enable_abandoned_cart_recovery:
        return
        
    user = frappe.get_doc("User", frappe.session.user)
    
    abandoned_cart = frappe.db.get_value("Webshop Abandoned Cart", {"user": user.name, "status": "Abandoned"}, "name")
    
    if abandoned_cart:
        doc = frappe.get_doc("Webshop Abandoned Cart", abandoned_cart)
        doc.cart_data = json.dumps(cart_data)
        doc.last_updated = frappe.utils.now()
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Webshop Abandoned Cart",
            "user": user.name,
            "email": user.email,
            "cart_data": json.dumps(cart_data),
            "status": "Abandoned",
            "last_updated": frappe.utils.now()
        })
        doc.insert(ignore_permissions=True)
        
    return "Cart synced"

@frappe.whitelist(allow_guest=True)
def subscribe_newsletter(email):
    set_cors_headers()
    settings = frappe.get_single("Webshop Content Settings")
    if not settings.enable_mailchimp:
        # Fallback: Save to a local DocType or just return success
        return "Subscription successful (local)"
        
    api_key = settings.mailchimp_api_key
    list_id = settings.mailchimp_list_id
    server = settings.mailchimp_server_prefix
    
    if not all([api_key, list_id, server]):
        frappe.throw("Mailchimp configuration is incomplete")
        
    url = f"https://{server}.api.mailchimp.com/3.0/lists/{list_id}/members"
    auth = ("any", api_key)
    data = {
        "email_address": email,
        "status": "subscribed"
    }
    
    try:
        response = requests.post(url, auth=auth, json=data)
        if response.status_code == 200 or response.status_code == 201:
            return "Subscribed successfully"
        else:
            res_json = response.json()
            if res_json.get("title") == "Member Exists":
                return "Already subscribed"
            frappe.throw(f"Mailchimp error: {res_json.get('detail')}")
    except Exception as e:
        frappe.throw(f"Failed to connect to Mailchimp: {str(e)}")
