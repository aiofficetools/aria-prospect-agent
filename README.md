# ARIA Prospect Agent — AI Office Tools

Automated SMS outreach agent for finding and qualifying leads for AI Office Tools.

## How It Works

1. Upload your GHL Prospecting export (CSV)
2. ARIA sends a personalized opening text to each prospect
3. AI handles the conversation — asks qualifying questions
4. When a prospect confirms interest → Jasmyn gets a text notification immediately
5. Dashboard tracks everyone's status in real time

## Setup

### 1. Clone & configure
```bash
git clone <your-repo>
cd prospect-agent
cp .env.example .env
# Fill in your credentials in .env
```

### 2. Run locally (for testing)
```bash
pip install -r requirements.txt
python app.py
```

### 3. Deploy to Render
- Connect this GitHub repo to Render.com
- Add all environment variables from .env.example in Render's dashboard
- Render gives you a public URL (e.g. https://aria-prospect-agent.onrender.com)

### 4. Configure SignalWire Webhook
- Go to SignalWire → Phone Numbers → your number
- Set the Messaging Webhook URL to:
  `https://your-render-url.onrender.com/webhook/sms`
- Method: HTTP POST

## Environment Variables

| Variable | Description |
|----------|-------------|
| SIGNALWIRE_PROJECT_ID | Your SignalWire Project ID |
| SIGNALWIRE_TOKEN | Your SignalWire API Token (PT...) |
| SIGNALWIRE_SPACE | e.g. easyai.signalwire.com |
| SIGNALWIRE_NUMBER | Your SignalWire phone number (+1...) |
| ANTHROPIC_API_KEY | Your Anthropic API key |
| NOTIFY_EMAIL | Email for lead notifications |
| NOTIFY_PHONE | Your personal phone for SMS notifications |

## GHL CSV Format

The app auto-detects these column names from GHL exports:
- Contact Name / Full Name / name
- Phone / Phone Number
- Business Name / Company
- Industry / Tags / Type
