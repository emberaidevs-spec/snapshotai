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
BG = '#09090b'
SURFACE = '#0f0f13'
SURFACE_2 = '#16161c'
TEXT = '#f4f4f5'
BODY = '#a1a1aa'
CAPTION = '#71717a'
# Embedded logo (base64 PNG, 64x64)
LOGO_B64_DATA = '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'

# Embedded logo (base64 PNG, 64x64)
LOGO_B64_DATA = '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'

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
        make_window_stealth(self)
        
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground if PYQT6 else Qt.WA_TranslucentBackground)
        
        # Main container with border
        container = QFrame(self)
        container.setFixedSize(400, 520)
        container.setStyleSheet(f"""
            QFrame {{
                background: {BG};
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)
        
        # Ghost logo image
        logo_img = QLabel()
        logo_pixmap = QPixmap()
        logo_pixmap.loadFromData(base64.b64decode(LOGO_B64_DATA))
        logo_img.setPixmap(logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio if PYQT6 else Qt.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation if PYQT6 else Qt.SmoothTransformation))
        logo_img.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        logo_img.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(logo_img)
        
        layout.addSpacing(4)
        
        # Logo text
        logo = QLabel("SnapShotAI")
        logo.setStyleSheet(f"font-size: 20px; font-weight: 500; color: {TEXT}; border: none; background: transparent;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(logo)
        
        tagline = QLabel("AI-powered screen capture")
        tagline.setStyleSheet(f"font-size: 13px; color: {CAPTION}; border: none; background: transparent;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(tagline)
        
        layout.addSpacing(24)
        
        # Google Sign In
        google_btn = QPushButton("Sign in with Google")
        google_btn.setFixedHeight(40)
        google_btn.setStyleSheet(f"""
            QPushButton {{ background: {TEXT}; border: none; border-radius: 8px; color: {BG}; font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: #e4e4e7; }}
        """)
        google_btn.clicked.connect(self.google_signin)
        layout.addWidget(google_btn)
        
        # Divider
        divider = QLabel("or continue with email")
        divider.setStyleSheet(f"font-size: 12px; color: {CAPTION}; border: none; background: transparent;")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(divider)
        
        layout.addSpacing(4)
        
        # Email
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setFixedHeight(40)
        input_style = f"""
            QLineEdit {{
                background: {SURFACE}; border: 1px solid rgba(255,255,255,0.06);
                border-radius: 8px; color: {TEXT}; font-size: 13px; padding: 0 14px;
            }}
            QLineEdit:focus {{ border-color: rgba(255,255,255,0.12); }}
        """
        self.email.setStyleSheet(input_style)
        layout.addWidget(self.email)
        
        # Password
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password if PYQT6 else QLineEdit.Password)
        self.password.setFixedHeight(40)
        self.password.setStyleSheet(input_style)
        self.password.returnPressed.connect(self.email_signin)
        layout.addWidget(self.password)
        
        layout.addSpacing(4)
        
        # Sign in / Sign up buttons
        btn_row = QHBoxLayout()
        
        signin_btn = QPushButton("Sign in")
        signin_btn.setFixedHeight(40)
        signin_btn.setStyleSheet(f"""
            QPushButton {{ background: {PURPLE}; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ background: {PURPLE_DARK}; }}
        """)
        signin_btn.clicked.connect(self.email_signin)
        btn_row.addWidget(signin_btn)
        
        signup_btn = QPushButton("Sign up")
        signup_btn.setFixedHeight(40)
        signup_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; color: {BODY}; font-size: 13px; font-weight: 600; }}
            QPushButton:hover {{ border-color: rgba(255,255,255,0.12); color: {TEXT}; }}
        """)
        signup_btn.clicked.connect(self.email_signup)
        btn_row.addWidget(signup_btn)
        layout.addLayout(btn_row)
        
        # Error/status
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"font-size: 12px; color: #f87171; border: none; background: transparent;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        
        layout.addStretch()
        
        # Footer
        footer = QLabel(f"Free: 15 captures/day  ·  Pro: $5.99/mo")
        footer.setStyleSheet(f"font-size: 11px; color: {CAPTION}; border: none; background: transparent;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter if PYQT6 else Qt.AlignCenter)
        layout.addWidget(footer)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 14px; color: {CAPTION}; font-size: 14px; }}
            QPushButton:hover {{ color: #f87171; background: rgba(248,113,113,0.1); }}
        """)
        close_btn.clicked.connect(self._on_close)
        close_btn.move(366, 8)
        close_btn.setParent(container)
        
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
        if not self.token:
            QTimer.singleShot(0, self._show_login)
            return
        QTimer.singleShot(0, self._show_selection)
    
    def full_capture(self):
        """Capture entire screen — completely invisible, no overlay shown"""
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
        """Register global hotkeys by polling Windows key state directly"""
        if platform.system() == 'Windows':
            self._hotkey_timer = QTimer()
            self._hotkey_timer.timeout.connect(self._poll_hotkeys)
            self._hotkey_timer.start(100)  # Check every 100ms
            self._hotkey_cooldown = False
            print("[Hotkeys] ✅ Polling via GetAsyncKeyState (100ms):")
            print("[Hotkeys]   Ctrl+Shift+S → Full screen capture")
            print("[Hotkeys]   Ctrl+Shift+A → Region capture")
            print("[Hotkeys]   Ctrl+Shift+Q → Quit")
        else:
            try:
                from pynput import keyboard as pynput_kb
                self._hotkey_listener = pynput_kb.GlobalHotKeys({
                    '<ctrl>+<shift>+s': lambda: QTimer.singleShot(0, self.full_capture),
                    '<ctrl>+<shift>+a': lambda: QTimer.singleShot(0, self.start_capture),
                    '<ctrl>+<shift>+q': lambda: QTimer.singleShot(0, self.quit),
                })
                self._hotkey_listener.start()
                print("[Hotkeys] Registered via pynput")
            except:
                print("[Hotkeys] Could not register hotkeys")
    
    def _poll_hotkeys(self):
        """Poll keyboard state using Win32 GetAsyncKeyState"""
        if self._hotkey_cooldown:
            return
        
        user32 = ctypes.windll.user32
        # Check if Ctrl AND Shift are held (high bit = 0x8000 means pressed)
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000   # VK_CONTROL
        shift = user32.GetAsyncKeyState(0x10) & 0x8000   # VK_SHIFT
        
        if ctrl and shift:
            s_key = user32.GetAsyncKeyState(0x53) & 0x8000  # S
            a_key = user32.GetAsyncKeyState(0x41) & 0x8000  # A
            q_key = user32.GetAsyncKeyState(0x51) & 0x8000  # Q
            
            if s_key:
                print("[Hotkey] Ctrl+Shift+S detected!")
                self._hotkey_cooldown = True
                QTimer.singleShot(1000, self._reset_cooldown)
                self.full_capture()
            elif a_key:
                print("[Hotkey] Ctrl+Shift+A detected!")
                self._hotkey_cooldown = True
                QTimer.singleShot(1000, self._reset_cooldown)
                self.start_capture()
            elif q_key:
                print("[Hotkey] Ctrl+Shift+Q detected!")
                self.quit()
    
    def _reset_cooldown(self):
        self._hotkey_cooldown = False
    
    def quit(self):
        try:
            if hasattr(self, '_hotkey_timer'):
                self._hotkey_timer.stop()
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
