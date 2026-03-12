# 📸 SnapShotAI

AI-powered screen capture. Select anything on your screen, get instant AI explanations.

## Architecture

```
snapshotai/
├── app/                  # Desktop client (Python + PyQt6)
│   ├── snapshotai.py     # Main app
│   ├── requirements.txt  # Python deps
│   └── build.py          # PyInstaller build script
├── api/                  # Vercel serverless backend
│   └── screenshot.py     # Screenshot analysis endpoint
├── landing/              # Marketing landing page
│   └── index.html        # Static landing page
└── assets/               # Icons, images
```

## How It Works

1. **Desktop app** runs in system tray, listens for Ctrl+Shift+S
2. User drags to select screen region
3. Screenshot is sent as base64 to our **API**
4. API proxies to Gemini Flash Vision for analysis
5. Result displayed in floating overlay with follow-up chat

## Monetization

- **Free tier:** 15 captures/day
- **Pro ($5.99/mo):** Unlimited captures via Stripe

## Tech Stack

- **Client:** Python, PyQt6, PIL, keyboard
- **API:** Vercel serverless (Python)
- **AI:** Gemini 2.5 Flash (Vision)
- **Auth:** Supabase (Google OAuth + email)
- **Payments:** Stripe
- **Landing:** Static HTML/CSS

## Building

### Windows
```bash
cd app
pip install -r requirements.txt pyinstaller
python build.py
```

### macOS
```bash
cd app
pip install -r requirements.txt pyinstaller
python build.py
```

## Deploying API + Landing

```bash
cd .. && npx vercel --prod
```
