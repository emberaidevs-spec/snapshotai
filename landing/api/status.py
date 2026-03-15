"""User status proxy — forwards to Hetzner analysis server"""
import json
import urllib.request
from http.server import BaseHTTPRequestHandler

API_BASE = "http://5.78.191.207:8765"

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            auth = self.headers.get('Authorization', '')
            req = urllib.request.Request(
                f"{API_BASE}/api/status",
                headers={'Authorization': auth}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            result = resp.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(result)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
