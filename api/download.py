"""Redirect to download server"""
from http.server import BaseHTTPRequestHandler
import urllib.parse

DOWNLOAD_BASE = "http://5.78.191.207:8766"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        file = query.get('file', [''])[0]
        
        if file not in ('SnapShotAI.exe', 'SnapShotAI.dmg'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Invalid file')
            return
        
        self.send_response(302)
        self.send_header('Location', f'{DOWNLOAD_BASE}/{file}')
        self.end_headers()
