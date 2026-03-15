"""
SnapShotAI - Analysis Server
Runs on Hetzner VPS — no timeout limits
"""
import os
import sys
import json
import base64
import time
import io
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Load env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

import google.generativeai as genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
SUPABASE_URL = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.getenv('SNAPSHOTAI_SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_KEY = os.getenv('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
FREE_DAILY_LIMIT = 15
PORT = 8765
MODEL = 'gemini-2.5-flash'

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL)

print(f"[SnapShotAI] Gemini model: {MODEL}")
print(f"[SnapShotAI] Supabase: {SUPABASE_URL[:40]}...")


def verify_user(token):
    try:
        req = urllib.request.Request(f"{SUPABASE_URL}/auth/v1/user")
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('apikey', SUPABASE_ANON_KEY)
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[Auth] Failed: {e}")
        return None


def get_usage(user_id):
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
    try:
        url = f"{SUPABASE_URL}/rest/v1/snapshotai_subscriptions?user_id=eq.{user_id}&plan=eq.pro&status=eq.active&select=id"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        resp = urllib.request.urlopen(req, timeout=5)
        return len(json.loads(resp.read())) > 0
    except:
        return False


def increment_usage(user_id):
    try:
        data = json.dumps({'p_user_id': user_id}).encode()
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/increment_usage", data=data, method='POST')
        req.add_header('apikey', SUPABASE_SERVICE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_KEY}')
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req, timeout=5)
    except:
        pass


def analyze(image_b64, question):
    try:
        image_data = base64.b64decode(image_b64)
        
        # Compress large images
        if len(image_data) > 500_000:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
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
        
        print(f"[Analyze] Image: {len(image_data)//1024}KB ({mime})")
        
        system = "Answer only. No explanations, no steps, no context. Just the answer. If it's a question, give the answer. If it's multiple choice, give the letter. If it's math, give the number. If it's code, give the fix. Nothing else."
        response = model.generate_content(
            [system, {'mime_type': mime, 'data': image_data}, question],
            generation_config={'max_output_tokens': 512}
        )
        return response.text
    except Exception as e:
        print(f"[Analyze] Error: {e}")
        return f"Analysis failed: {str(e)}"


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/screenshot':
            self._handle_screenshot()
        elif self.path == '/api/checkout':
            self._handle_stripe('checkout')
        elif self.path == '/api/portal':
            self._handle_stripe('portal')
        elif self.path == '/api/webhook':
            self._handle_stripe('webhook')
        else:
            self._json(404, {'error': 'Not found'})

    def do_GET(self):
        if self.path == '/health':
            self._json(200, {'status': 'ok', 'model': MODEL})
        elif self.path.startswith('/api/status'):
            self._handle_status()
        else:
            self._json(404, {'error': 'Not found'})

    def _handle_status(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return self._json(401, {'error': 'Unauthorized'})
        
        token = auth[7:]
        user = verify_user(token)
        if not user:
            return self._json(401, {'error': 'Invalid token'})
        
        user_id = user.get('id', '')
        email = user.get('email', '')
        pro = is_pro(user_id)
        usage = get_usage(user_id) if not pro else 0
        
        self._json(200, {
            'email': email,
            'plan': 'pro' if pro else 'free',
            'usage_today': usage,
            'limit': 'unlimited' if pro else FREE_DAILY_LIMIT,
            'remaining': 'unlimited' if pro else max(0, FREE_DAILY_LIMIT - usage)
        })

    def _handle_stripe(self, action):
        from stripe_handler import handle_checkout, handle_portal, handle_webhook
        
        length = int(self.headers.get('Content-Length', 0))
        body_raw = self.rfile.read(length)
        
        if action == 'webhook':
            sig = self.headers.get('Stripe-Signature', '')
            code, data = handle_webhook(body_raw, sig)
        else:
            try:
                body = json.loads(body_raw)
            except:
                return self._json(400, {'error': 'Invalid JSON'})
            
            if action == 'checkout':
                code, data = handle_checkout(body)
            elif action == 'portal':
                code, data = handle_portal(body)
            else:
                return self._json(404, {'error': 'Unknown action'})
        
        self._json(code, data)

    def _handle_screenshot(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return self._json(401, {'error': 'Unauthorized'})

        token = auth[7:]
        user = verify_user(token)
        if not user:
            return self._json(401, {'error': 'Invalid token'})

        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
        except:
            return self._json(400, {'error': 'Invalid request'})

        image_b64 = body.get('image', '')
        question = body.get('question', "Give a direct, concise answer. No fluff. Under 100 words.")

        if not image_b64:
            return self._json(400, {'error': 'No image'})

        user_id = user.get('id', '')
        pro = is_pro(user_id)

        if not pro:
            usage = get_usage(user_id)
            if usage >= FREE_DAILY_LIMIT:
                return self._json(429, {'error': 'Daily limit reached! Upgrade to Pro.', 'remaining': 0})

        print(f"[Request] User: {user.get('email', '?')} | Pro: {pro}")
        
        result = analyze(image_b64, question)
        increment_usage(user_id)

        remaining = 'unlimited' if pro else FREE_DAILY_LIMIT - get_usage(user_id)
        self._json(200, {'result': result, 'remaining': remaining})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        # CORS handled by nginx reverse proxy — skip when behind it
        if self.headers.get('X-Real-IP'):
            return
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"\n{'='*50}")
    print(f"  📸 SnapShotAI Analysis Server")
    print(f"  Port: {PORT}")
    print(f"  Model: {MODEL}")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
