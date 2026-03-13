"""Redirect downloads to Hetzner file server"""
from http.server import BaseHTTPRequestHandler
import urllib.parse

DOWNLOAD_BASE = "http://5.78.191.207:8766"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        file = query.get('file', [''])[0]
        
        if file not in ('SnapShotAI.exe', 'SnapShotAI.dmg'):
            self.send_response(400)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Invalid file parameter')
            return
        
        self.send_response(302)
        self.send_header('Location', f'{DOWNLOAD_BASE}/{file}')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
