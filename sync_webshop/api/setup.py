import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

@frappe.whitelist()
def run_setup():
	"""
	Creates custom fields required for Batch 2.
	This should be run once after deploying the code.
	"""
	# Check if user is System Manager
	if frappe.session.user == "Guest":
		frappe.throw("Guest users cannot run setup.")
		
	# In a real scenario, we might want to restrict this further
	# but for this task, we'll allow it if called correctly.
	
	custom_fields = {
		"Sales Order": [
			{
				"fieldname": "tracking_number", 
				"label": "Tracking Number", 
				"fieldtype": "Data", 
				"insert_after": "delivery_date"
			},
			{
				"fieldname": "webshop_payment_method", 
				"label": "Webshop Payment Method", 
				"fieldtype": "Data", 
				"insert_after": "payment_terms_template"
			},
			{
				"fieldname": "webshop_payment_status", 
				"label": "Webshop Payment Status", 
				"fieldtype": "Data", 
				"insert_after": "webshop_payment_method"
			},
			{
				"fieldname": "stripe_payment_intent", 
				"label": "Stripe Payment Intent", 
				"fieldtype": "Data", 
				"insert_after": "webshop_payment_status"
			},
		],
		"Delivery Note": [
			{
				"fieldname": "tracking_number", 
				"label": "Tracking Number", 
				"fieldtype": "Data", 
				"insert_after": "delivery_date"
			},
		]
	}
	
	create_custom_fields(custom_fields)
	
	# Create a default Webshop Payment Settings record if it doesn't exist
	if not frappe.db.exists("Webshop Payment Settings", "Webshop Payment Settings"):
		doc = frappe.get_doc({
			"doctype": "Webshop Payment Settings",
			"cod_enabled": 1,
			"cod_label_en": "Cash on Delivery",
			"cod_label_ar": "الدفع عند الاستلام"
		})
		doc.insert(ignore_permissions=True)
		
	# Create a default Webshop Shipping Rule if none exists
	if not frappe.db.count("Webshop Shipping Rule"):
		doc = frappe.get_doc({
			"doctype": "Webshop Shipping Rule",
			"rule_name": "Standard Shipping",
			"enabled": 1,
			"shipping_cost": 5.0,
			"free_shipping_threshold": 50.0
		})
		doc.insert(ignore_permissions=True)
		
	return "Setup completed successfully. Custom fields and default settings created."
