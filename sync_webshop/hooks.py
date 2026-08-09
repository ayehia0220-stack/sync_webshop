app_name = "sync_webshop"
app_title = "Sync Webshop"
app_publisher = "Dpono"
app_description = "Headless webshop backend for ERPNext - powers a separate storefront frontend via REST API. Same core app across all servers; per-server theme and content live in data, not code."
app_email = "dev@dpono.com"
app_license = "mit"

# Modules
# ------------------
# Registered automatically via modules.txt -> "Sync Webshop"

# Includes in <head>
# ------------------
# app_include_css = "/assets/sync_webshop/css/sync_webshop.css"
# app_include_js = "/assets/sync_webshop/js/sync_webshop.js"

# Whitelisted methods (added in Step 3 - Backend APIs)
# ------------------
# These will expose read endpoints (theme, content, catalog) and
# write endpoints (checkout -> Sales Order) to the React frontend.
#
# Example (to be filled in step 3):
# from sync_webshop.api import theme, content, catalog, checkout

# CORS (needed since the frontend is a separate app/domain)
# ------------------
# Allowed origins will be read from "Webshop API Settings" doctype
# rather than hardcoded here, so each server can allow its own
# frontend domain without a code change.

# Fixtures (for moving Theme/Content default records between sites, optional)
# ------------------
# fixtures = []

# Document Events
# ------------------
doc_events = {
	"Webshop Content Settings": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Webshop API Settings": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Webshop Theme Settings": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Webshop Announcement Bar": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Webshop Footer Settings": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Item": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	},
	"Item Group": {
		"on_update": "sync_webshop.api.utils.clear_webshop_cache"
	}
}

# Scheduled Tasks
# ------------------
# scheduler_events = {}
