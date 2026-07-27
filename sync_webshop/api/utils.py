import frappe


def set_cors_headers():
	"""
	Reads the allowed frontend origin(s) from Webshop API Settings and, if the
	incoming request's Origin header matches one of them, allows it via CORS.

	This is what lets a separate React app (on its own domain) call this
	server's API. Each server has its own Webshop API Settings record, so
	each deployment only needs to allow its own frontend domain(s) -
	no code change required to add/change a frontend origin.
	"""
	origin = frappe.get_request_header("Origin")
	if not origin:
		return

	settings = frappe.get_single("Webshop API Settings")
	allowed_raw = settings.allowed_origins or ""
	allowed = [line.strip().rstrip("/") for line in allowed_raw.splitlines() if line.strip()]

	if not allowed:
		# Nothing configured yet (e.g. fresh install) - don't silently block
		# local development, but don't silently open production either.
		# Admin should fill in Webshop API Settings > Allowed Frontend Origins.
		return

	if origin.rstrip("/") in allowed:
		if frappe.local.response.get("headers") is None:
			frappe.local.response.headers = {}
		frappe.local.response.headers["Access-Control-Allow-Origin"] = origin
		frappe.local.response.headers["Vary"] = "Origin"


def guest_catalog_allowed():
	"""Whether anonymous visitors may read theme/content/catalog endpoints."""
	settings = frappe.get_single("Webshop API Settings")
	return bool(settings.enable_guest_catalog_access)


def require_catalog_access():
	"""
	Call at the top of any read endpoint that should respect the
	'Enable Guest Catalog Access' toggle. Raises a clean permission error
	instead of leaking a stack trace if guest access is turned off and
	nobody is logged in.
	"""
	if frappe.session.user == "Guest" and not guest_catalog_allowed():
		frappe.throw(
			"Guest access is disabled for this store. Please log in.",
			frappe.PermissionError,
		)


def full_url(file_url):
	"""Turn a stored Attach/Attach Image value into an absolute URL the
	React frontend (on a different domain) can load directly."""
	if not file_url:
		return None
	if file_url.startswith("http://") or file_url.startswith("https://"):
		return file_url
	return frappe.utils.get_url(file_url)
