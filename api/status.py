"""
SnapShotAI - User status endpoint
Returns usage info and subscription status
"""
import os
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.getenv('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
FREE_DAILY_LIMIT = 15


def verify_user(token):
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                'Authorization': f'Bearer {token}',
                'apikey': SUPABASE_SERVICE_KEY
            }
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except:
        return None


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            self._respond(401, {'error': 'Unauthorized'})
            return

        user = verify_user(auth.replace('Bearer ', ''))
        if not user:
            self._respond(401, {'error': 'Invalid token'})
            return

        user_id = user.get('id', '')
        email = user.get('email', '')

        # Get usage
        try:
            today = time.strftime('%Y-%m-%d')
            url = f"{SUPABASE_URL}/rest/v1/snapshotai_usage?user_id=eq.{user_id}&date=eq.{today}&select=count"
            req = urllib.request.Request(url, headers={
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
            })
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            usage = data[0]['count'] if data else 0
        except:
            usage = 0

        # Get subscription
        try:
            url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}&select=plan,status"
            req = urllib.request.Request(url, headers={
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
            })
            resp = urllib.request.urlopen(req, timeout=5)
            subs = json.loads(resp.read())
            plan = subs[0]['plan'] if subs else 'free'
        except:
            plan = 'free'

        self._respond(200, {
            'email': email,
            'plan': plan,
            'usage_today': usage,
            'limit': 'unlimited' if plan == 'pro' else FREE_DAILY_LIMIT,
            'remaining': 'unlimited' if plan == 'pro' else max(0, FREE_DAILY_LIMIT - usage)
        })

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
