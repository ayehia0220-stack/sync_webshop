import frappe
import stripe
import json
from sync_webshop.api.utils import set_cors_headers

@frappe.whitelist(allow_guest=True)
def create_payment_intent(amount, currency="gbp"):
    set_cors_headers()
    settings = frappe.get_single("Webshop Payment Settings")
    if not settings.stripe_enabled:
        frappe.throw("Stripe is not enabled.")
    
    stripe.api_key = settings.get_password("stripe_secret_key")
    
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(float(amount) * 100),
            currency=currency.lower(),
            automatic_payment_methods={"enabled": True},
        )
        return {"clientSecret": intent.client_secret}
    except Exception as e:
        frappe.throw(str(e))

@frappe.whitelist(allow_guest=True)
def stripe_webhook():
    set_cors_headers()
    settings = frappe.get_single("Webshop Payment Settings")
    payload = frappe.request.get_data()
    sig_header = frappe.get_request_header("Stripe-Signature")
    endpoint_secret = settings.get_password("stripe_webhook_secret")

    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        frappe.local.response.http_status_code = 400
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        frappe.local.response.http_status_code = 400
        return {"error": "Invalid signature"}

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        # Update Sales Order status
        # We need to store the payment intent ID in the Sales Order to find it
        so_name = frappe.db.get_value("Sales Order", {"stripe_payment_intent": payment_intent['id']}, "name")
        if so_name:
            so = frappe.get_doc("Sales Order", so_name)
            so.db_set("webshop_payment_status", "Paid")
            so.add_comment("Assignment", "Payment verified via Stripe Webhook")
            
    return {"status": "success"}
