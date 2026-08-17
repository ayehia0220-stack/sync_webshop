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
# The assistant rides along with the Desk on every page.
app_include_css = "/assets/sync_webshop/css/agent_widget.css"
app_include_js = "/assets/sync_webshop/js/agent_widget.js"

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
	"Territory": {
		"on_update": "sync_webshop.api.regions.clear_regions_cache",
		"on_trash": "sync_webshop.api.regions.clear_regions_cache",
	},
	"Webshop Shipping Zone": {
		"on_update": "sync_webshop.api.regions.clear_regions_cache",
	},
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
	},
	"Project": {
		"before_insert": "sync_webshop.api.turbo.keep_project_series_ahead",
	},
	"Sales Invoice": {
		"validate": "sync_webshop.api.turbo.fill_invoice_contact",
	},
	"Sales Order": {
		"validate": [
			"sync_webshop.api.turbo.fill_customer_address",
			"sync_webshop.api.turbo.check_cod_amount",
		],
		"on_submit": "sync_webshop.api.notifications.on_sales_order_submit",
		# validate does not fire on a submitted doc; this one does.
		"before_update_after_submit": "sync_webshop.api.turbo.check_cod_amount",
		"on_update_after_submit": [
			"sync_webshop.api.notifications.on_sales_order_update",
			"sync_webshop.api.turbo.on_preparation_status",
		]
	}
}

# Scheduled Tasks
# ------------------
scheduler_events = {
	"daily": [
		"sync_webshop.api.regions.refresh_daily",
		"sync_webshop.api.intelligence.daily_refresh",
		"sync_webshop.api.board.refresh_overdue_cards",
	],
}


doctype_js = {
	"Customer": "public/js/customer_call.js",
}
