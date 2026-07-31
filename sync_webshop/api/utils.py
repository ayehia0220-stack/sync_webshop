import frappe
from functools import wraps

def set_cors_headers():
    """
    Reads the allowed frontend origin(s) from Webshop API Settings and allows CORS.
    """
    try:
        if not getattr(frappe, "request", None):
            return
        if frappe.local.response.get("headers") is None:
            frappe.local.response.headers = {}
        frappe.local.response.headers["Access-Control-Allow-Origin"] = "*"
        frappe.local.response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        frappe.local.response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    except Exception:
        pass

def guest_catalog_allowed():
    """Whether anonymous visitors may read theme/content/catalog endpoints."""
    try:
        settings = frappe.get_single("Webshop API Settings")
        return bool(settings.enable_guest_catalog_access)
    except Exception:
        return True

def require_catalog_access(func):
    """Decorator to check if guest access is allowed or user is logged in."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not guest_catalog_allowed() and frappe.session.user == "Guest":
            frappe.throw(frappe._("Catalog access restricted to logged-in users."), frappe.PermissionError)
        return func(*args, **kwargs)
    return wrapper

def full_url(file_url):
    """Turn a stored Attach/Attach Image value into an absolute URL, optionally via CDN."""
    if not file_url:
        return None
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url
    
    try:
        settings = frappe.get_single("Webshop Content Settings")
        if settings.cdn_url_prefix:
            prefix = settings.cdn_url_prefix.rstrip('/')
            return f"{prefix}{file_url}"
    except Exception:
        pass
        
    return frappe.utils.get_url(file_url)
