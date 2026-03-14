"""
SnapShotAI Stripe Handler
- POST /checkout — create Stripe Checkout session
- POST /webhook — handle Stripe events (subscription created/cancelled)
- POST /portal — create billing portal session
"""
import os
import json
import urllib.request
import urllib.parse
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('SNAPSHOTAI_STRIPE_WEBHOOK_SECRET', '')
PRICE_ID = os.environ.get('SNAPSHOTAI_STRIPE_PRICE_ID', 'price_1TAij45B7nvYWk02xbDUuXtw')
SUPABASE_URL = os.environ.get('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
SITE_URL = 'https://snapshotai-beta.vercel.app'


def update_subscription_status(user_id, plan, stripe_customer_id=None, stripe_subscription_id=None):
    """Update user's subscription in Supabase"""
    try:
        # Upsert into snapshotai_subscriptions
        data = {
            'user_id': user_id,
            'plan': plan,
            'updated_at': 'now()'
        }
        if stripe_customer_id:
            data['stripe_customer_id'] = stripe_customer_id
        if stripe_subscription_id:
            data['stripe_subscription_id'] = stripe_subscription_id

        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}"
        
        # Try update first
        req = urllib.request.Request(url, method='PATCH')
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Prefer', 'return=minimal')
        
        patch_data = {'plan': plan}
        if stripe_customer_id:
            patch_data['stripe_customer_id'] = stripe_customer_id
        if stripe_subscription_id:
            patch_data['stripe_subscription_id'] = stripe_subscription_id
            
        req.data = json.dumps(patch_data).encode()
        urllib.request.urlopen(req, timeout=5)
        print(f"[Stripe] Updated user {user_id} to {plan}")
    except Exception as e:
        print(f"[Stripe] Error updating subscription: {e}")
        # Try insert if update failed
        try:
            url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions"
            req = urllib.request.Request(url, method='POST')
            req.add_header('apikey', SUPABASE_SERVICE_KEY)
            req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Prefer', 'return=minimal')
            insert_data = {
                'user_id': user_id,
                'plan': plan,
            }
            if stripe_customer_id:
                insert_data['stripe_customer_id'] = stripe_customer_id
            if stripe_subscription_id:
                insert_data['stripe_subscription_id'] = stripe_subscription_id
            req.data = json.dumps(insert_data).encode()
            urllib.request.urlopen(req, timeout=5)
            print(f"[Stripe] Inserted subscription for user {user_id}")
        except Exception as e2:
            print(f"[Stripe] Insert also failed: {e2}")


def get_user_by_stripe_customer(customer_id):
    """Look up user_id from stripe customer_id"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?stripe_customer_id=eq.{customer_id}&select=user_id"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        if data:
            return data[0]['user_id']
    except Exception as e:
        print(f"[Stripe] Error looking up customer: {e}")
    return None


def handle_checkout(body):
    """Create a Stripe Checkout session"""
    user_id = body.get('user_id', '')
    email = body.get('email', '')
    
    if not user_id:
        return 400, {'error': 'Missing user_id'}
    
    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            payment_method_types=['card'],
            line_items=[{'price': PRICE_ID, 'quantity': 1}],
            customer_email=email if email else None,
            client_reference_id=user_id,
            success_url=f'{SITE_URL}/dashboard?upgraded=true',
            cancel_url=f'{SITE_URL}/pricing',
            metadata={'user_id': user_id},
        )
        return 200, {'url': session.url}
    except Exception as e:
        print(f"[Stripe] Checkout error: {e}")
        return 500, {'error': str(e)}


def handle_portal(body):
    """Create a Stripe billing portal session"""
    user_id = body.get('user_id', '')
    
    if not user_id:
        return 400, {'error': 'Missing user_id'}
    
    try:
        # Get stripe customer ID from supabase
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}&select=stripe_customer_id"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        
        if not data or not data[0].get('stripe_customer_id'):
            return 404, {'error': 'No subscription found'}
        
        session = stripe.billing_portal.Session.create(
            customer=data[0]['stripe_customer_id'],
            return_url=f'{SITE_URL}/dashboard',
        )
        return 200, {'url': session.url}
    except Exception as e:
        print(f"[Stripe] Portal error: {e}")
        return 500, {'error': str(e)}


def handle_webhook(body_raw, sig_header):
    """Handle Stripe webhook events"""
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(body_raw, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(body_raw)
            print("[Stripe] WARNING: No webhook secret set, skipping signature verification")
    except Exception as e:
        print(f"[Stripe] Webhook verification failed: {e}")
        return 400, {'error': 'Invalid signature'}
    
    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})
    
    print(f"[Stripe] Event: {event_type}")
    
    if event_type == 'checkout.session.completed':
        user_id = data.get('client_reference_id') or data.get('metadata', {}).get('user_id')
        customer_id = data.get('customer')
        subscription_id = data.get('subscription')
        
        if user_id:
            update_subscription_status(user_id, 'pro', customer_id, subscription_id)
            print(f"[Stripe] User {user_id} upgraded to Pro!")
    
    elif event_type in ('customer.subscription.deleted', 'customer.subscription.expired'):
        customer_id = data.get('customer')
        user_id = get_user_by_stripe_customer(customer_id)
        if user_id:
            update_subscription_status(user_id, 'free')
            print(f"[Stripe] User {user_id} downgraded to Free")
    
    elif event_type == 'customer.subscription.updated':
        customer_id = data.get('customer')
        status = data.get('status')
        user_id = get_user_by_stripe_customer(customer_id)
        if user_id:
            if status in ('active', 'trialing'):
                update_subscription_status(user_id, 'pro')
            elif status in ('canceled', 'unpaid', 'past_due'):
                update_subscription_status(user_id, 'free')
    
    return 200, {'received': True}
