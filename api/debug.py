"""Debug endpoint - test Supabase connectivity from Vercel"""
import os
import json
import urllib.request
import urllib.error
import traceback
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.getenv('SNAPSHOTAI_SUPABASE_ANON_KEY', '')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        results = {}
        
        # Check env vars
        results['env'] = {
            'supabase_url': SUPABASE_URL[:40] + '...' if SUPABASE_URL else 'MISSING',
            'anon_key_len': len(SUPABASE_ANON_KEY),
        }
        
        # Test Supabase connectivity
        try:
            req = urllib.request.Request(f"{SUPABASE_URL}/auth/v1/settings")
            req.add_header('apikey', SUPABASE_ANON_KEY)
            resp = urllib.request.urlopen(req, timeout=10)
            settings = json.loads(resp.read())
            results['supabase_reachable'] = True
            results['providers'] = list(settings.get('external', {}).keys())[:5]
        except Exception as e:
            results['supabase_reachable'] = False
            results['supabase_error'] = f"{type(e).__name__}: {str(e)}"
        
        # Test token verification if provided
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            results['token_length'] = len(token)
            try:
                req = urllib.request.Request(f"{SUPABASE_URL}/auth/v1/user")
                req.add_header('Authorization', f'Bearer {token}')
                req.add_header('apikey', SUPABASE_ANON_KEY)
                resp = urllib.request.urlopen(req, timeout=10)
                user_data = json.loads(resp.read())
                results['token_valid'] = True
                results['user_email'] = user_data.get('email', '?')
            except urllib.error.HTTPError as e:
                body = ''
                try:
                    body = e.read().decode()
                except:
                    pass
                results['token_valid'] = False
                results['token_error'] = f"HTTP {e.code}: {body[:200]}"
            except Exception as e:
                results['token_valid'] = False
                results['token_error'] = f"{type(e).__name__}: {str(e)}"
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(results, indent=2).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization')
        self.end_headers()
