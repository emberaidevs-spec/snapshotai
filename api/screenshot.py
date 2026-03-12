"""
SnapShotAI - Screenshot Analysis API
Vercel serverless function
"""
import os
import json
import base64
import time
import urllib.request
from http.server import BaseHTTPRequestHandler
import google.generativeai as genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
SUPABASE_URL = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.getenv('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
FREE_DAILY_LIMIT = 15
MODEL = 'gemini-2.5-flash'

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL)


def verify_user(token):
    """Verify Supabase auth token"""
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


def get_usage(user_id):
    """Get today's capture count"""
    try:
        today = time.strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_usage?user_id=eq.{user_id}&date=eq.{today}&select=count"
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
        })
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return data[0]['count'] if data else 0
    except:
        return 0


def is_pro(user_id):
    """Check if user has active pro subscription"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}&plan=eq.pro&status=eq.active&select=id"
        req = urllib.request.Request(url, headers={
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
        })
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return len(data) > 0
    except:
        return False


def increment_usage(user_id):
    """Increment daily usage counter"""
    try:
        data = json.dumps({'p_user_id': user_id}).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/rpc/increment_usage",
            data=data,
            headers={
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def analyze(image_b64, question):
    """Analyze screenshot with Gemini Vision"""
    try:
        image_data = base64.b64decode(image_b64)
        response = model.generate_content([
            {'mime_type': 'image/png', 'data': image_data},
            question
        ])
        return response.text
    except Exception as e:
        return f"Analysis failed: {str(e)}"


def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        headers = cors_headers()
        
        # Auth
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            self._respond(401, {'error': 'Unauthorized'}, headers)
            return

        user = verify_user(auth.replace('Bearer ', ''))
        if not user:
            self._respond(401, {'error': 'Invalid token'}, headers)
            return

        # Parse body
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
        except:
            self._respond(400, {'error': 'Invalid request'}, headers)
            return

        image_b64 = body.get('image', '')
        question = body.get('question', 'What\'s on this screen? Explain it clearly and concisely. If it\'s code, explain what it does. If it\'s an error, explain how to fix it. If it\'s homework, help solve it step by step.')

        if not image_b64:
            self._respond(400, {'error': 'No image provided'}, headers)
            return

        # Usage check
        user_id = user.get('id', '')
        pro = is_pro(user_id)

        if not pro:
            usage = get_usage(user_id)
            if usage >= FREE_DAILY_LIMIT:
                self._respond(429, {
                    'error': 'Daily limit reached! Upgrade to Pro for unlimited captures.',
                    'remaining': 0,
                    'limit': FREE_DAILY_LIMIT
                }, headers)
                return

        # Analyze
        result = analyze(image_b64, question)
        increment_usage(user_id)

        remaining = 'unlimited' if pro else FREE_DAILY_LIMIT - get_usage(user_id)
        self._respond(200, {'result': result, 'remaining': remaining}, headers)

    def _respond(self, code, data, headers):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
