import frappe


def _allowed_origins():
	"""Origins configured in Webshop API Settings, one per line or comma separated."""
	try:
		raw = frappe.get_single("Webshop API Settings").allowed_origins or ""
	except Exception:
		raw = ""
	parts = [p.strip().rstrip("/") for p in raw.replace(",", "\n").splitlines()]
	return [p for p in parts if p]


def set_cors_headers():
	"""
	Echo the caller's Origin back only when it is listed in Webshop API Settings.
	A wildcard here would let any site on the internet call these endpoints.
	"""
	try:
		if not getattr(frappe, "request", None):
			return
		origin = (frappe.get_request_header("Origin") or "").strip().rstrip("/")
		if not origin or origin not in _allowed_origins():
			return
		if frappe.local.response.get("headers") is None:
			frappe.local.response.headers = {}
		headers = frappe.local.response.headers
		headers["Access-Control-Allow-Origin"] = origin
		headers["Vary"] = "Origin"
		headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
		headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
		headers["Access-Control-Max-Age"] = "600"
	except Exception:
		pass


def guest_catalog_allowed():
	"""Whether anonymous visitors may read theme/content/catalog endpoints."""
	try:
		settings = frappe.get_single("Webshop API Settings")
		return bool(settings.enable_guest_catalog_access)
	except Exception:
		return True


def require_catalog_access():
	"""Function to check if guest access is allowed or user is logged in."""
	if not guest_catalog_allowed() and frappe.session.user == "Guest":
		frappe.throw(frappe._("التصفّح متاح للمسجّلين فقط."), frappe.PermissionError)


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


def clear_webshop_cache(doc=None, method=None):
	"""
	Invalidate only the document that changed. The storefront reads live from the
	database, so the previous frappe.clear_cache() + cache().flushall() wiped the
	whole ERP's Redis on every single Item save.
	"""
	try:
		if doc is not None:
			frappe.clear_document_cache(doc.doctype, doc.name)
	except Exception:
		pass
