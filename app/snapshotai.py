"""
SnapShotAI - Desktop Client v1.0.0
AI-powered screen capture. Select anything, understand everything.
"""
import os
import sys
import io
import json
import base64
import threading
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
import http.server
from pathlib import Path
from PIL import ImageGrab, Image

try:
    from PyQt6.QtWidgets import (QApplication, QWidget, QTextEdit, QVBoxLayout,
                                  QLabel, QPushButton, QHBoxLayout, QLineEdit,
                                  QSystemTrayIcon, QMenu, QFrame)
    from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer, QSize, QUrl
    from PyQt6.QtGui import (QPainter, QColor, QPen, QFont, QCursor, QIcon, 
                             QPixmap, QAction, QLinearGradient)
    PYQT6 = True
except ImportError:
    from PyQt5.QtWidgets import (QApplication, QWidget, QTextEdit, QVBoxLayout,
                                  QLabel, QPushButton, QHBoxLayout, QLineEdit,
                                  QSystemTrayIcon, QMenu, QAction, QFrame)
    from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer, QSize, QUrl
    from PyQt5.QtGui import (QPainter, QColor, QPen, QFont, QCursor, QIcon, 
                             QPixmap, QLinearGradient)
    PYQT6 = False

import platform
import ctypes
if platform.system() == 'Windows':
    import ctypes.wintypes

# ===== Stealth Mode: Hide from screen capture =====
def make_window_stealth(widget):
    """Make a window invisible to screen sharing (Zoom, Teams, OBS, etc.)"""
    system = platform.system()
    
    if system == 'Windows':
        try:
            import ctypes
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Windows 10 2004+)
            hwnd = int(widget.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            print(f"[Stealth] Window hidden from screen capture (Windows)")
        except Exception as e:
            print(f"[Stealth] Windows stealth failed: {e}")
            # Fallback: WDA_MONITOR (older Windows) 
            try:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000001)
                print(f"[Stealth] Fallback: WDA_MONITOR applied")
            except:
                pass
    
    elif system == 'Darwin':
        try:
            # macOS: set sharing type to none
            from AppKit import NSApp
            ns_window = widget.windowHandle()
            if ns_window:
                ns_window.setSharingType_(0)  # NSWindowSharingNone = 0
                print(f"[Stealth] Window hidden from screen capture (macOS)")
        except Exception as e:
            print(f"[Stealth] macOS stealth failed: {e}")
    
    else:
        print(f"[Stealth] Not supported on {system}")

# ===== Config =====
APP_NAME = "SnapShotAI"
APP_VERSION = "1.0.0"
API_BASE = "http://5.78.191.207:8765"
SUPABASE_URL = "https://xiwfuenqxyfzadggakip.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhpd2Z1ZW5xeHlmemFkZ2dha2lwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMzMzYxNDQsImV4cCI6MjA4ODkxMjE0NH0.leYWfPUg8NLIA3YcFEH5w_gbuVMLw-Z6OVu7_tme4QA"
CONFIG_DIR = Path.home() / '.snapshotai'
CONFIG_FILE = CONFIG_DIR / 'config.json'
CAPTURE_HOTKEY = 'ctrl+shift+s'       # Full screen capture (invisible)
REGION_HOTKEY = 'ctrl+shift+a'        # Region select capture
QUIT_HOTKEY = 'ctrl+shift+q'
OAUTH_PORT = 48271  # Local port for OAuth callback

# Colors
PURPLE = '#8b5cf6'
PURPLE_DARK = '#7c3aed'
BLUE = '#3b82f6'
BG = '#0a0a14'
SURFACE = '#111127'
TEXT = '#ffffff'
BODY = '#a1a1aa'
CAPTION = '#71717a'
GLASS_BG = 'rgba(17,17,39,0.85)'
GLASS_BORDER = 'rgba(255,255,255,0.08)'


# ===== Config Management =====
def load_config():
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except:
        pass
    return {}

def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


# ===== API =====
def api_call(endpoint, method='GET', data=None, token=None):
    """Make API call to SnapShotAI backend"""
    try:
        url = f"{API_BASE}/api/{endpoint}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Content-Type', 'application/json')
        if token:
            req.add_header('Authorization', f'Bearer {token}')
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except:
            return {'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def supabase_auth(email, password, action='login'):
    """Authenticate with Supabase"""
    try:
        endpoint = 'token?grant_type=password' if action == 'login' else 'signup'
        url = f"{SUPABASE_URL}/auth/v1/{endpoint}"
        data = json.dumps({'email': email, 'password': password}).encode()
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('apikey', SUPABASE_ANON_KEY)
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except:
            return {'error': f'Auth failed: HTTP {e.code}'}
    except Exception as e:
        return {'error': str(e)}


# ===== OAuth Callback Server =====
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handle OAuth redirect locally"""
    token = None
    email = None
    
    def do_GET(self):
        # Serve a page that captures the hash fragment
        if '?' not in self.path or 'access_token' not in self.path:
            # Initial redirect — serve JS to capture hash
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''<!DOCTYPE html><html><head>
            <style>body{background:#0a0a14;color:#fff;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
            .c{text-align:center;}</style></head><body><div class="c">
            <p style="font-size:48px;margin-bottom:16px;">&#x2728;</p>
            <h2>Signing you in...</h2>
            <p style="color:#71717a;">Completing authentication...</p>
            </div>
            <script>
            const hash = window.location.hash.substring(1);
            if (hash) {
                const params = new URLSearchParams(hash);
                const token = params.get("access_token");
                if (token) {
                    fetch("/callback?access_token=" + encodeURIComponent(token))
                    .then(() => {
                        window.location.href = "https://snapshotai-beta.vercel.app/dashboard";
                    });
                }
            }
            </script></body></html>''')
        else:
            # Callback with token
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            token = params.get('access_token', [None])[0]
            if token:
                OAuthCallbackHandler.token = token
                # Get user info
                try:
                    req = urllib.request.Request(
                        f"{SUPABASE_URL}/auth/v1/user",
                        headers={'Authorization': f'Bearer {token}', 'apikey': SUPABASE_ANON_KEY}
                    )
                    resp = urllib.request.urlopen(req, timeout=5)
                    user = json.loads(resp.read())
                    OAuthCallbackHandler.email = user.get('email', '')
                except:
                    pass
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
    
    def log_message(self, format, *args):
        pass  # Suppress logs


# ===== Selection Overlay =====
class SelectionOverlay(QWidget):
    region_selected = pyqtSignal(QRect)
    
    def __init__(self):
        super().__init__()
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool) if PYQT6 else (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowFlags(flags)
        attr = Qt.WidgetAttribute.WA_TranslucentBackground if PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(attr)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.start_pos = None
        self.end_pos = None
        self.selecting = False
        cursor = Qt.CursorShape.CrossCursor if PYQT6 else Qt.CrossCursor
        self.setCursor(QCursor(cursor))
    
    def mousePressEvent(self, e):
        btn = Qt.MouseButton.LeftButton if PYQT6 else Qt.LeftButton
        if e.button() == btn:
            self.start_pos = e.pos()
            self.end_pos = e.pos()
            self.selecting = True
            self.update()
    
    def mouseMoveEvent(self, e):
        if self.selecting:
            self.end_pos = e.pos()
            self.update()
    
    def mouseReleaseEvent(self, e):
        btn = Qt.MouseButton.LeftButton if PYQT6 else Qt.LeftButton
        if e.button() == btn and self.selecting:
            self.selecting = False
            self.end_pos = e.pos()
            if self.start_pos and self.end_pos:
                rect = QRect(self.start_pos, self.end_pos).normalized()
                if rect.width() > 10 and rect.height() > 10:
                    self.region_selected.emit(rect)
            self.hide()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.start_pos and self.end_pos and self.selecting:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            clear_mode = QPainter.CompositionMode.CompositionMode_Clear if PYQT6 else QPainter.CompositionMode_Clear
            source_mode = QPainter.CompositionMode.CompositionMode_SourceOver if PYQT6 else QPainter.CompositionMode_SourceOver
            
            p.setCompositionMode(clear_mode)
            p.fillRect(rect, QColor(0, 0, 0, 0))
            p.setCompositionMode(source_mode)
            
            pen = QPen(QColor(139, 92, 246), 2)
            p.setPen(pen)
            p.drawRect(rect)
            
            # Size label
            p.setFont(QFont('Inter', 10))
            p.setPen(QColor(200, 200, 200, 200))
            p.drawText(rect.x(), rect.y() - 8, f"{rect.width()} × {rect.height()}")
        
        if not self.selecting:
            align = Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter
            p.setFont(QFont('Inter', 16))
            p.setPen(QColor(255, 255, 255, 180))
            p.drawText(self.rect(), align, "Drag to select a region · Esc to cancel")
        
        p.end()
    
    def keyPressEvent(self, e):
        key = Qt.Key.Key_Escape if PYQT6 else Qt.Key_Escape
        if e.key() == key:
            self.hide()


# ===== Result Overlay =====
class ResultOverlay(QWidget):
    update_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    
    STYLE = f"""
        QWidget#resultWindow {{
            background-color: {SURFACE};
            border: 1px solid rgba(139,92,246,0.3);
            border-radius: 16px;
            color: {TEXT};
            font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
        }}
    """
    
    def __init__(self):
        super().__init__()
        self.setObjectName("resultWindow")
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool) if PYQT6 else (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowFlags(flags)
        
        self.setFixedWidth(440)
        self.setMinimumHeight(260)
        self.setMaximumHeight(560)
        self.setStyleSheet(self.STYLE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("📸 SnapShotAI")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {PURPLE}; border: none; background: transparent;")
        header.addWidget(title)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {CAPTION}; border: none; background: transparent;")
        header.addWidget(self.status_label)
        header.addStretch()
        
        dash_btn = QPushButton("👤")
        dash_btn.setFixedSize(28, 28)
        dash_btn.setToolTip("Open Dashboard")
        dash_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(139,92,246,0.12); border: none; border-radius: 14px; color: {PURPLE}; font-size: 13px; }}
            QPushButton:hover {{ background: rgba(139,92,246,0.25); }}
        """)
        dash_btn.clicked.connect(lambda: webbrowser.open("https://snapshotai-beta.vercel.app/dashboard"))
        header.addWidget(dash_btn)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(248,113,113,0.12); border: none; border-radius: 14px; color: #f87171; font-size: 14px; }}
            QPushButton:hover {{ background: rgba(248,113,113,0.3); }}
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)
        
        # Response
        self.response = QTextEdit()
        self.response.setReadOnly(True)
        self.response.setStyleSheet(f"""
            QTextEdit {{
                background: {BG}; border: 1px solid rgba(139,92,246,0.12);
                border-radius: 10px; color: {TEXT}; font-size: 13px; padding: 12px; line-height: 1.6;
            }}
        """)
        layout.addWidget(self.response)
        
        # Input
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask a follow-up question...")
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG}; border: 1px solid rgba(139,92,246,0.2);
                border-radius: 10px; color: {TEXT}; font-size: 13px; padding: 10px 14px;
            }}
            QLineEdit:focus {{ border-color: {PURPLE}; }}
        """)
        self.input.returnPressed.connect(self.ask)
        input_row.addWidget(self.input)
        
        send_btn = QPushButton("→")
        send_btn.setFixedSize(40, 38)
        send_btn.setStyleSheet(f"""
            QPushButton {{ background: {PURPLE}; border: none; border-radius: 10px; color: white; font-size: 16px; font-weight: bold; }}
            QPushButton:hover {{ background: {PURPLE_DARK}; }}
        """)
        send_btn.clicked.connect(self.ask)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)
        
        self.image_b64 = ""
        self.token = ""
        self._drag = None
        
        self.update_signal.connect(lambda t: self.response.setText(t))
        self.status_signal.connect(lambda t: self.status_label.setText(t))
    
    def analyze(self, image_b64, token):
        self.image_b64 = image_b64
        self.token = token
        self.response.setText("⏳ Analyzing screenshot...")
        self.status_label.setText("")
        self.show()
        self.raise_()
        self.activateWindow()
        # Stealth temporarily disabled for debugging
        # make_window_stealth(self)
        
        cursor = QCursor.pos()
        screen = QApplication.primaryScreen().geometry()
        x = min(cursor.x() + 20, screen.width() - 460)
        y = min(cursor.y() + 20, screen.height() - 580)
        self.move(max(0, x), max(0, y))
        
        threading.Thread(target=self._run_analysis,
                        args=("What's on this screen? Explain it clearly. If it's code, explain what it does and flag any bugs. If it's an error, explain how to fix it. If it's homework, help solve it step by step.",),
                        daemon=True).start()
    
    def _run_analysis(self, question):
        result = api_call('screenshot', 'POST',
                         {'image': self.image_b64, 'question': question},
                         self.token)
        if 'error' in result:
            self.update_signal.emit(f"❌ {result['error']}")
        else:
            self.update_signal.emit(result.get('result', 'No response'))
            rem = result.get('remaining', '?')
            self.status_signal.emit("⚡ Pro" if rem == 'unlimited' else f"{rem} left today")
    
    def ask(self):
        q = self.input.text().strip()
        if not q or not self.image_b64:
            return
        self.input.clear()
        self.response.setText("⏳ Thinking...")
        threading.Thread(target=self._run_analysis, args=(q,), daemon=True).start()
    
    def mousePressEvent(self, e):
        btn = Qt.MouseButton.LeftButton if PYQT6 else Qt.LeftButton
        if e.button() == btn:
            self._drag = (e.globalPosition().toPoint() if PYQT6 else e.globalPos()) - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, e):
        if self._drag:
            self.move((e.globalPosition().toPoint() if PYQT6 else e.globalPos()) - self._drag)
    
    def mouseReleaseEvent(self, e):
        self._drag = None


# ===== Login Window =====
class LoginWindow(QWidget):
    login_success = pyqtSignal(str, str)  # token, email
    
    def __init__(self):
        super().__init__()
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint) if PYQT6 else (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(flags)
        self.setFixedSize(400, 520)
        self.setStyleSheet(f"QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif; }}")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)
        
        # Logo
        logo = QLabel("📸 SnapShotAI")
        logo.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {PURPLE};")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(logo)
        
        tagline = QLabel("AI-powered screen capture")
        tagline.setStyleSheet(f"font-size: 14px; color: {CAPTION};")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(tagline)
        
        layout.addSpacing(20)
        
        # Google Sign In
        google_btn = QPushButton("🔑  Sign in with Google")
        google_btn.setFixedHeight(46)
        google_btn.setStyleSheet("""
            QPushButton { background: white; border: none; border-radius: 12px; color: #333; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #f0f0f0; }
        """)
        google_btn.clicked.connect(self.google_signin)
        layout.addWidget(google_btn)
        
        # Divider
        divider = QLabel("─── or use email ───")
        divider.setStyleSheet(f"font-size: 12px; color: {CAPTION};")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(divider)
        
        # Email
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setFixedHeight(42)
        input_style = f"""
            QLineEdit {{
                background: {SURFACE}; border: 1px solid rgba(139,92,246,0.2);
                border-radius: 10px; color: {TEXT}; font-size: 13px; padding: 0 14px;
            }}
            QLineEdit:focus {{ border-color: {PURPLE}; }}
        """
        self.email.setStyleSheet(input_style)
        layout.addWidget(self.email)
        
        # Password
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password if PYQT6 else QLineEdit.Password)
        self.password.setFixedHeight(42)
        self.password.setStyleSheet(input_style)
        self.password.returnPressed.connect(self.email_signin)
        layout.addWidget(self.password)
        
        # Sign in / Sign up buttons
        btn_row = QHBoxLayout()
        
        signin_btn = QPushButton("Sign In")
        signin_btn.setFixedHeight(44)
        signin_btn.setStyleSheet(f"""
            QPushButton {{ background: {PURPLE}; border: none; border-radius: 10px; color: white; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background: {PURPLE_DARK}; }}
        """)
        signin_btn.clicked.connect(self.email_signin)
        btn_row.addWidget(signin_btn)
        
        signup_btn = QPushButton("Sign Up")
        signup_btn.setFixedHeight(44)
        signup_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid rgba(139,92,246,0.3); border-radius: 10px; color: {TEXT}; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background: rgba(139,92,246,0.05); border-color: {PURPLE}; }}
        """)
        signup_btn.clicked.connect(self.email_signup)
        btn_row.addWidget(signup_btn)
        layout.addLayout(btn_row)
        
        # Error/status
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        
        layout.addStretch()
        
        # Footer
        footer = QLabel(f"Free: 15 captures/day · Pro: $5.99/mo unlimited")
        footer.setStyleSheet(f"font-size: 11px; color: {CAPTION};")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(footer)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(248,113,113,0.12); border: none; border-radius: 14px; color: #f87171; font-size: 13px; }}
            QPushButton:hover {{ background: rgba(248,113,113,0.3); }}
        """)
        close_btn.clicked.connect(self._on_close)
        close_btn.move(364, 8)
        close_btn.setParent(self)
        
        self._drag = None
        self._oauth_server = None
    
    def _on_close(self):
        # If not logged in, quit app
        config = load_config()
        if not config.get('token'):
            QApplication.quit()
        else:
            self.hide()
    
    def google_signin(self):
        """Start Google OAuth flow"""
        self.error_label.setText("Opening browser for sign-in...")
        self.error_label.setStyleSheet(f"font-size: 12px; color: {PURPLE};")
        
        # Start local callback server
        threading.Thread(target=self._start_oauth_server, daemon=True).start()
        
        # Open Google OAuth via Supabase
        redirect = f"http://localhost:{OAUTH_PORT}"
        url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={urllib.parse.quote(redirect)}"
        webbrowser.open(url)
        
        # Poll for token
        self._poll_oauth()
    
    def _start_oauth_server(self):
        OAuthCallbackHandler.token = None
        OAuthCallbackHandler.email = None
        server = http.server.HTTPServer(('localhost', OAUTH_PORT), OAuthCallbackHandler)
        server.timeout = 120
        while OAuthCallbackHandler.token is None:
            server.handle_request()
        server.server_close()
    
    def _poll_oauth(self):
        if OAuthCallbackHandler.token:
            self.login_success.emit(OAuthCallbackHandler.token, OAuthCallbackHandler.email or '')
        else:
            QTimer.singleShot(500, self._poll_oauth)
    
    def email_signin(self):
        email = self.email.text().strip()
        pw = self.password.text().strip()
        if not email or not pw:
            self.error_label.setText("Enter email and password")
            self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
            return
        self.error_label.setText("Signing in...")
        self.error_label.setStyleSheet(f"font-size: 12px; color: {CAPTION};")
        threading.Thread(target=self._do_auth, args=(email, pw, 'login'), daemon=True).start()
    
    def email_signup(self):
        email = self.email.text().strip()
        pw = self.password.text().strip()
        if not email or not pw:
            self.error_label.setText("Enter email and password")
            self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
            return
        if len(pw) < 6:
            self.error_label.setText("Password must be at least 6 characters")
            self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
            return
        self.error_label.setText("Creating account...")
        self.error_label.setStyleSheet(f"font-size: 12px; color: {CAPTION};")
        threading.Thread(target=self._do_auth, args=(email, pw, 'signup'), daemon=True).start()
    
    def _do_auth(self, email, pw, action):
        result = supabase_auth(email, pw, action)
        if result.get('access_token'):
            self.login_success.emit(result['access_token'], email)
        elif result.get('error_description'):
            self.error_label.setText(result['error_description'])
            self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
        elif result.get('msg'):
            # Signup success — check email
            self.error_label.setText("Check your email to confirm your account!")
            self.error_label.setStyleSheet(f"font-size: 12px; color: #34d399;")
        else:
            self.error_label.setText(str(result.get('error', 'Unknown error')))
            self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171;")
    
    def mousePressEvent(self, e):
        btn = Qt.MouseButton.LeftButton if PYQT6 else Qt.LeftButton
        if e.button() == btn:
            self._drag = (e.globalPosition().toPoint() if PYQT6 else e.globalPos()) - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, e):
        if self._drag:
            self.move((e.globalPosition().toPoint() if PYQT6 else e.globalPos()) - self._drag)
    
    def mouseReleaseEvent(self, e):
        self._drag = None


# ===== Main App =====
class SnapShotAI:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName(APP_NAME)
        
        self.config = load_config()
        self.token = self.config.get('token', '')
        self.email = self.config.get('email', '')
        
        # Widgets
        self.selection = SelectionOverlay()
        self.result = ResultOverlay()
        self.login = LoginWindow()
        
        # Signals
        self.selection.region_selected.connect(self.on_capture)
        self.login.login_success.connect(self.on_login)
        
        # Tray
        self._setup_tray()
        
        # Register global hotkeys
        self._setup_hotkeys()
    
    def _setup_tray(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(PURPLE))
        self.tray = QSystemTrayIcon(QIcon(pixmap))
        self.tray.setToolTip(f"{APP_NAME} — {CAPTURE_HOTKEY} for full screen, {REGION_HOTKEY} for region")
        
        menu = QMenu()
        full_cap = menu.addAction("📸 Full Screen Capture (invisible)")
        full_cap.triggered.connect(self.full_capture)
        region_cap = menu.addAction("🔲 Region Capture")
        region_cap.triggered.connect(self.start_capture)
        menu.addSeparator()
        
        if self.email:
            user = menu.addAction(f"👤 {self.email}")
            user.setEnabled(False)
            signout = menu.addAction("Sign Out")
            signout.triggered.connect(self.sign_out)
        
        menu.addSeparator()
        quit_act = menu.addAction("❌ Quit")
        quit_act.triggered.connect(self.quit)
        
        self.tray.setContextMenu(menu)
        self.tray.show()
    
    def start_capture(self):
        print("[DEBUG] >>> start_capture() (region) triggered!")
        if not self.token:
            QTimer.singleShot(0, self._show_login)
            return
        QTimer.singleShot(0, self._show_selection)
    
    def full_capture(self):
        """Capture entire screen — completely invisible, no overlay shown"""
        print("[DEBUG] >>> full_capture() triggered!")
        if not self.token:
            QTimer.singleShot(0, self._show_login)
            return
        QTimer.singleShot(0, self._do_full_capture)
    
    def _do_full_capture(self):
        try:
            print("[Capture] Taking full screen capture...")
            screen = QApplication.primaryScreen()
            geometry = screen.geometry()
            print(f"[Capture] Screen: {geometry.width()}x{geometry.height()}")
            img = ImageGrab.grab(bbox=(geometry.x(), geometry.y(), 
                                       geometry.x() + geometry.width(), 
                                       geometry.y() + geometry.height()))
            buf = io.BytesIO()
            img.save(buf, format='PNG', optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            print(f"[Capture] Image size: {len(b64) // 1024}KB base64")
            print("[Capture] Sending to analysis server...")
            self.result.analyze(b64, self.token)
        except Exception as e:
            print(f"[Capture] Full capture error: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_selection(self):
        self.selection.showFullScreen()
        make_window_stealth(self.selection)
    
    def on_capture(self, rect):
        try:
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            buf = io.BytesIO()
            img.save(buf, format='PNG', optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            self.result.analyze(b64, self.token)
        except Exception as e:
            print(f"Capture error: {e}")
    
    def _show_login(self):
        screen = QApplication.primaryScreen().geometry()
        self.login.move((screen.width() - 400) // 2, (screen.height() - 520) // 2)
        self.login.show()
        self.login.raise_()
    
    def on_login(self, token, email):
        self.token = token
        self.email = email
        self.config['token'] = token
        self.config['email'] = email
        save_config(self.config)
        self.login.hide()
        self._setup_tray()
        
        msg_icon = QSystemTrayIcon.MessageIcon.Information if PYQT6 else QSystemTrayIcon.Information
        self.tray.showMessage(APP_NAME, f"Welcome! Press {CAPTURE_HOTKEY} to capture.", msg_icon, 3000)
    
    def sign_out(self):
        self.token = ''
        self.email = ''
        self.config.pop('token', None)
        self.config.pop('email', None)
        save_config(self.config)
        self._setup_tray()
        self._show_login()
    
    def _setup_hotkeys(self):
        """Register global hotkeys using pynput key listener"""
        try:
            from pynput import keyboard as pynput_kb
            
            self._pressed_keys = set()
            
            def on_press(key):
                try:
                    # Normalize key
                    if hasattr(key, 'vk'):
                        self._pressed_keys.add(key.vk)
                    if key == pynput_kb.Key.ctrl_l or key == pynput_kb.Key.ctrl_r:
                        self._pressed_keys.add('ctrl')
                    elif key == pynput_kb.Key.shift or key == pynput_kb.Key.shift_l or key == pynput_kb.Key.shift_r:
                        self._pressed_keys.add('shift')
                    elif hasattr(key, 'char') and key.char:
                        self._pressed_keys.add(key.char.lower())
                    
                    # Check combos
                    if 'ctrl' in self._pressed_keys and 'shift' in self._pressed_keys:
                        if 's' in self._pressed_keys:
                            self._pressed_keys.clear()
                            QTimer.singleShot(0, self.full_capture)
                        elif 'a' in self._pressed_keys:
                            self._pressed_keys.clear()
                            QTimer.singleShot(0, self.start_capture)
                        elif 'q' in self._pressed_keys:
                            self._pressed_keys.clear()
                            QTimer.singleShot(0, self.quit)
                except:
                    pass
            
            def on_release(key):
                try:
                    if hasattr(key, 'vk') and key.vk in self._pressed_keys:
                        self._pressed_keys.discard(key.vk)
                    if key == pynput_kb.Key.ctrl_l or key == pynput_kb.Key.ctrl_r:
                        self._pressed_keys.discard('ctrl')
                    elif key == pynput_kb.Key.shift or key == pynput_kb.Key.shift_l or key == pynput_kb.Key.shift_r:
                        self._pressed_keys.discard('shift')
                    elif hasattr(key, 'char') and key.char:
                        self._pressed_keys.discard(key.char.lower())
                except:
                    pass
            
            self._key_listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
            self._key_listener.start()
            print("[Hotkeys] ✅ Registered via pynput Listener:")
            print("[Hotkeys]   Ctrl+Shift+S → Full screen capture")
            print("[Hotkeys]   Ctrl+Shift+A → Region capture") 
            print("[Hotkeys]   Ctrl+Shift+Q → Quit")
        except Exception as e:
            print(f"[Hotkeys] pynput failed: {e}, trying keyboard library...")
            try:
                import keyboard
                keyboard.add_hotkey('ctrl+shift+s', lambda: QTimer.singleShot(0, self.full_capture))
                keyboard.add_hotkey('ctrl+shift+a', lambda: QTimer.singleShot(0, self.start_capture))
                keyboard.add_hotkey('ctrl+shift+q', lambda: QTimer.singleShot(0, self.quit))
                print("[Hotkeys] Registered via keyboard library (fallback)")
            except Exception as e2:
                print(f"[Hotkeys] All methods failed: {e2}")
    
    def quit(self):
        try:
            if hasattr(self, '_key_listener'):
                self._key_listener.stop()
        except:
            pass
        self.tray.hide()
        self.app.quit()
    
    def run(self):
        print(f"\n{'='*50}")
        print(f"  📸 {APP_NAME} v{APP_VERSION}")
        print(f"  Full Screen: {CAPTURE_HOTKEY} (invisible)")
        print(f"  Region:      {REGION_HOTKEY}")
        print(f"  Quit:        {QUIT_HOTKEY}")
        print(f"{'='*50}\n")
        
        if not self.token:
            QTimer.singleShot(300, self._show_login)
        else:
            msg_icon = QSystemTrayIcon.MessageIcon.Information if PYQT6 else QSystemTrayIcon.Information
            self.tray.showMessage(APP_NAME, f"Ready! Press {CAPTURE_HOTKEY} to capture.", msg_icon, 2000)
        
        sys.exit(self.app.exec() if PYQT6 else self.app.exec_())


if __name__ == '__main__':
    app = SnapShotAI()
    app.run()
