"""Debug endpoint - check env vars are loaded"""
import os
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        supabase_url = os.getenv('SNAPSHOTAI_SUPABASE_URL', '')
        anon_key = os.getenv('SNAPSHOTAI_SUPABASE_ANON_KEY', '')
        service_key = os.getenv('SNAPSHOTAI_SUPABASE_SERVICE_KEY', '')
        gemini_key = os.getenv('GEMINI_API_KEY', '')
        
        self.wfile.write(json.dumps({
            'supabase_url': supabase_url[:30] + '...' if supabase_url else 'MISSING',
            'anon_key': anon_key[:20] + '...' if anon_key else 'MISSING',
            'service_key': service_key[:20] + '...' if service_key else 'MISSING',
            'gemini_key': gemini_key[:10] + '...' if gemini_key else 'MISSING',
        }).encode())
