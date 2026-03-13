"""
SnapShotAI - Screenshot Analysis API
Vercel serverless function
"""
import os
import json
import base64
import time
import urllib.request
import urllib.error
import traceback
from http.server import BaseHTTPRequestHandler
import google.generativeai as genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
SUPABASE_URL = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.getenv('SNAPSHOTAI_SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_KEY = os.getenv('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
FREE_DAILY_LIMIT = 15
MODEL = 'gemini-2.5-flash'

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)
else:
    model = None


def verify_user(token):
    """Verify Supabase auth token"""
    try:
        url = f"{SUPABASE_URL}/auth/v1/user"
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('apikey', SUPABASE_ANON_KEY)
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read()
        return json.loads(data)
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.read else ''
        print(f"Auth HTTPError {e.code}: {body}")
        return None
    except Exception as e:
        print(f"Auth error: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def get_usage(user_id):
    """Get today's capture count"""
    try:
        today = time.strftime('%Y-%m-%d')
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_usage?user_id=eq.{user_id}&date=eq.{today}&select=count"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return data[0]['count'] if data else 0
    except:
        return 0


def is_pro(user_id):
    """Check if user has active pro subscription"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}&plan=eq.pro&status=eq.active&select=id"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
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
            method='POST'
        )
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def analyze(image_b64, question):
    """Analyze screenshot with Gemini Vision"""
    if not model:
        return "Error: Gemini API not configured"
    try:
        image_data = base64.b64decode(image_b64)
        
        # Compress image if too large (>500KB)
        if len(image_data) > 500_000:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_data))
            # Resize if very large
            max_dim = 1920
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            image_data = buf.getvalue()
            mime = 'image/jpeg'
        else:
            mime = 'image/png'
        
        response = model.generate_content(
            [{'mime_type': mime, 'data': image_data}, question],
            generation_config={'max_output_tokens': 1024}
        )
        return response.text
    except Exception as e:
        return f"Analysis failed: {str(e)}"


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            # Get auth header
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return self._json(401, {'error': 'No authorization header'})

            token = auth[7:]  # Strip 'Bearer '
            
            if not token or len(token) < 10:
                return self._json(401, {'error': 'Empty or invalid token format'})

            # Verify with Supabase
            user = verify_user(token)
            if not user:
                return self._json(401, {'error': 'Invalid token', 'debug': {
                    'supabase_url_set': bool(SUPABASE_URL),
                    'anon_key_set': bool(SUPABASE_ANON_KEY),
                    'token_length': len(token),
                    'token_prefix': token[:20] + '...'
                }})

            # Parse body
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length))
            except:
                return self._json(400, {'error': 'Invalid request body'})

            image_b64 = body.get('image', '')
            question = body.get('question', "What's on this screen? Explain it clearly. If it's code, explain what it does and flag bugs. If it's an error, explain how to fix it.")

            if not image_b64:
                return self._json(400, {'error': 'No image provided'})

            # Usage check
            user_id = user.get('id', '')
            pro = is_pro(user_id)

            if not pro:
                usage = get_usage(user_id)
                if usage >= FREE_DAILY_LIMIT:
                    return self._json(429, {
                        'error': 'Daily limit reached! Upgrade to Pro for unlimited captures.',
                        'remaining': 0
                    })

            # Analyze
            result = analyze(image_b64, question)
            increment_usage(user_id)

            remaining = 'unlimited' if pro else FREE_DAILY_LIMIT - get_usage(user_id)
            return self._json(200, {'result': result, 'remaining': remaining})

        except Exception as e:
            traceback.print_exc()
            return self._json(500, {'error': f'Server error: {str(e)}'})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
