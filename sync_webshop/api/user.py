import frappe
from sync_webshop.api.utils import set_cors_headers, full_url

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    set_cors_headers()
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.AuthenticationError:
        frappe.clear_messages()
        frappe.throw("Invalid login credentials", frappe.AuthenticationError)
    
    user = frappe.get_doc("User", frappe.session.user)
    return {
        "message": "Logged in",
        "user": user.first_name,
        "email": user.email,
        "sid": frappe.session.sid
    }

@frappe.whitelist(allow_guest=True)
def signup(email, first_name, password):
    set_cors_headers()
    if frappe.db.exists("User", email):
        frappe.throw("User already exists")
    
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "enabled": 1,
        "new_password": password,
        "roles": [{"role": "Customer"}]
    })
    user.insert(ignore_permissions=True)
    
    # Also create a Customer record linked to this user
    if not frappe.db.exists("Customer", {"email_id": email}):
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": first_name,
            "customer_type": "Individual",
            "email_id": email
        })
        customer.insert(ignore_permissions=True)
        
    return "User created successfully"

@frappe.whitelist()
def get_current_user():
    set_cors_headers()
    if frappe.session.user == "Guest":
        return None
    
    user = frappe.get_doc("User", frappe.session.user)
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name
    }

@frappe.whitelist()
def logout():
    set_cors_headers()
    frappe.local.login_manager.logout()
    return "Logged out"

@frappe.whitelist()
def get_wishlist():
    set_cors_headers()
    if frappe.session.user == "Guest":
        return []
    
    wishlist = frappe.get_all("Webshop Wishlist", 
        filters={"user": frappe.session.user},
        fields=["item_code"]
    )
    
    items = []
    for w in wishlist:
        item_doc = frappe.get_doc("Item", w.item_code)
        items.append({
            "item_code": w.item_code,
            "item_name": item_doc.item_name,
            "image": full_url(item_doc.image) if item_doc.image else None
        })
    return items

@frappe.whitelist()
def add_to_wishlist(item_code):
    set_cors_headers()
    if frappe.session.user == "Guest":
        frappe.throw("Please login to add to wishlist")
    
    if not frappe.db.exists("Webshop Wishlist", {"user": frappe.session.user, "item_code": item_code}):
        wishlist = frappe.get_doc({
            "doctype": "Webshop Wishlist",
            "user": frappe.session.user,
            "item_code": item_code
        })
        wishlist.insert(ignore_permissions=True)
    return "Added to wishlist"

@frappe.whitelist()
def remove_from_wishlist(item_code):
    set_cors_headers()
    if frappe.session.user == "Guest":
        return
    
    frappe.db.delete("Webshop Wishlist", {"user": frappe.session.user, "item_code": item_code})
    return "Removed from wishlist"
