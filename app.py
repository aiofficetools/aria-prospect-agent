import os
import json
import csv
import io
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# In-memory storage (persists while server is running)
prospects = {}
conversations = {}

SIGNALWIRE_PROJECT_ID = os.getenv("SIGNALWIRE_PROJECT_ID", "YOUR_PROJECT_ID")
SIGNALWIRE_TOKEN = os.getenv("SIGNALWIRE_TOKEN", "YOUR_API_TOKEN")
SIGNALWIRE_SPACE = os.getenv("SIGNALWIRE_SPACE", "YOUR_SPACE.signalwire.com")
SIGNALWIRE_NUMBER = os.getenv("SIGNALWIRE_NUMBER", "+1XXXXXXXXXX")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "aiofficetools@gmail.com")
NOTIFY_PHONE = os.getenv("NOTIFY_PHONE", "YOUR_PERSONAL_NUMBER")


OPENING_MESSAGE = """Hi {name}! This is ARIA from AI Office Tools. I'm an AI specialist serving businesses across Ontario. I help local {business_type} businesses get more customers and save money using AI tools — things like 24/7 phone answering, automatic booking, and Google review management. No pressure at all, just wondering if that's something you'd want to hear more about? 😊"""

SYSTEM_PROMPT = """You are ARIA, a friendly AI assistant for AI Office Tools — an agency that helps small trades businesses (plumbers, electricians, HVAC, salons) in the Belleville/Quinte West area of Ontario, Canada with:
- AI-built websites
- 24/7 AI phone agents (so they never miss a call)
- Automated booking
- Google review management

Your job is to have a natural, friendly SMS conversation to find out if this prospect is a good fit. Ask one question at a time. Keep messages SHORT (1-3 sentences max — this is SMS).

Qualifying questions to work through naturally:
1. Do they miss calls / lose leads because of it?
2. Do they have a website? Is it getting them leads?
3. Are they open to AI tools that save time and money?
4. Are they the owner / decision maker?

If they seem interested and are a decision maker, say something like:
"That's great! I'd love to have our founder Jasmyn reach out personally to show you what we can do. Can I pass along your info to her?"

If they say yes to that → respond with exactly: INTERESTED_CONFIRMED

If they are clearly not interested or say stop/unsubscribe → respond with exactly: NOT_INTERESTED

Otherwise keep the conversation going naturally. Never be pushy. Be warm and human."""


def send_sms(to_number, message):
    """Send SMS via SignalWire REST API"""
    import urllib.request
    import urllib.parse
    import base64

    url = f"https://{SIGNALWIRE_SPACE}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Messages.json"

    data = urllib.parse.urlencode({
        "From": SIGNALWIRE_NUMBER,
        "To": to_number,
        "Body": message
    }).encode()

    credentials = base64.b64encode(f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_TOKEN}".encode()).decode()

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {credentials}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"SMS send error: {e}")
        return None


def notify_jasmyn(prospect):
    """Send notification SMS to Jasmyn when a prospect is interested"""
    message = f"🔥 HOT LEAD! {prospect['name']} ({prospect['business_type']}) is INTERESTED!\nPhone: {prospect['phone']}\nBusiness: {prospect.get('business_name', 'N/A')}\nFollow up now!"
    send_sms(NOTIFY_PHONE, message)


def get_ai_response(phone, incoming_message):
    """Get AI response for an incoming SMS"""
    import urllib.request
    import urllib.parse
    import json

    if phone not in conversations:
        conversations[phone] = []

    conversations[phone].append({
        "role": "user",
        "content": incoming_message
    })

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": conversations[phone]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", os.getenv("ANTHROPIC_API_KEY", ""))
    req.add_header("anthropic-version", "2023-06-01")

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        reply = data["content"][0]["text"]

    conversations[phone].append({
        "role": "assistant",
        "content": reply
    })

    return reply


# ─── ROUTES ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(open("templates/index.html").read())


@app.route("/api/prospects", methods=["GET"])
def get_prospects():
    return jsonify(list(prospects.values()))


@app.route("/api/upload", methods=["POST"])
def upload_csv():
    """Upload GHL prospect export CSV"""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    content = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    added = 0
    for row in reader:
        # Try common GHL column names
        phone = (row.get("Phone") or row.get("phone") or row.get("Phone Number") or "").strip()
        name = (row.get("Contact Name") or row.get("Full Name") or row.get("name") or row.get("Name") or "there").strip()
        business = (row.get("Business Name") or row.get("Company") or row.get("company") or "").strip()
        biz_type = (row.get("Industry") or row.get("Tags") or row.get("Type") or "trades").strip()

        if not phone:
            continue

        # Normalize phone to E.164
        digits = "".join(filter(str.isdigit, phone))
        if len(digits) == 10:
            phone = f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            phone = f"+{digits}"

        if phone not in prospects:
            prospects[phone] = {
                "id": phone,
                "phone": phone,
                "name": name,
                "business_name": business,
                "business_type": biz_type,
                "status": "new",
                "added_at": datetime.now().isoformat(),
                "last_contact": None,
                "notes": ""
            }
            added += 1

    return jsonify({"message": f"Added {added} new prospects", "total": len(prospects)})


@app.route("/api/send/<phone>", methods=["POST"])
def send_to_prospect(phone):
    """Send opening message to a single prospect"""
    if phone not in prospects:
        return jsonify({"error": "Prospect not found"}), 404

    prospect = prospects[phone]
    message = OPENING_MESSAGE.format(
        name=prospect["name"].split()[0] if prospect["name"] != "there" else "there",
        business_type=prospect["business_type"] or "business"
    )

    result = send_sms(phone, message)

    if result:
        prospects[phone]["status"] = "contacted"
        prospects[phone]["last_contact"] = datetime.now().isoformat()
        conversations[phone] = [{"role": "assistant", "content": message}]
        return jsonify({"success": True, "message": "Text sent!"})
    else:
        return jsonify({"error": "Failed to send SMS"}), 500


@app.route("/api/send-batch", methods=["POST"])
def send_batch():
    """Send opening message to all 'new' prospects"""
    sent = 0
    failed = 0
    for phone, prospect in prospects.items():
        if prospect["status"] == "new":
            message = OPENING_MESSAGE.format(
                name=prospect["name"].split()[0] if prospect["name"] != "there" else "there",
                business_type=prospect["business_type"] or "business"
            )
            result = send_sms(phone, message)
            if result:
                prospects[phone]["status"] = "contacted"
                prospects[phone]["last_contact"] = datetime.now().isoformat()
                conversations[phone] = [{"role": "assistant", "content": message}]
                sent += 1
            else:
                failed += 1

    return jsonify({"sent": sent, "failed": failed})


@app.route("/api/conversation/<phone>", methods=["GET"])
def get_conversation(phone):
    """Get conversation history for a prospect"""
    return jsonify(conversations.get(phone, []))


@app.route("/webhook/sms", methods=["POST"])
def sms_webhook():
    """SignalWire webhook — handles incoming SMS replies"""
    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()

    if not from_number or not body:
        return "", 200

    # Update prospect record
    if from_number in prospects:
        prospects[from_number]["last_contact"] = datetime.now().isoformat()

    # Get AI response
    reply = get_ai_response(from_number, body)

    if "INTERESTED_CONFIRMED" in reply:
        if from_number in prospects:
            prospects[from_number]["status"] = "interested"
        notify_jasmyn(prospects.get(from_number, {"name": "Unknown", "phone": from_number, "business_type": "Unknown", "business_name": "Unknown"}))
        final_reply = "Perfect! I'll have Jasmyn reach out to you personally very soon. Thanks so much for chatting! 😊"
        send_sms(from_number, final_reply)
        conversations[from_number].append({"role": "assistant", "content": final_reply})

    elif "NOT_INTERESTED" in reply:
        if from_number in prospects:
            prospects[from_number]["status"] = "not_interested"
        final_reply = "No worries at all! Have a great day 😊 Reply STOP anytime to opt out."
        send_sms(from_number, final_reply)
        conversations[from_number].append({"role": "assistant", "content": final_reply})

    else:
        send_sms(from_number, reply)

    return "", 200


@app.route("/api/prospect/<phone>/status", methods=["POST"])
def update_status(phone):
    """Manually update prospect status"""
    if phone not in prospects:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    prospects[phone]["status"] = data.get("status", prospects[phone]["status"])
    prospects[phone]["notes"] = data.get("notes", prospects[phone].get("notes", ""))
    return jsonify({"success": True})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    all_p = list(prospects.values())
    return jsonify({
        "total": len(all_p),
        "new": sum(1 for p in all_p if p["status"] == "new"),
        "contacted": sum(1 for p in all_p if p["status"] == "contacted"),
        "interested": sum(1 for p in all_p if p["status"] == "interested"),
        "not_interested": sum(1 for p in all_p if p["status"] == "not_interested"),
    })

@app.route("/api/add_prospect", methods=["POST"])
def add_prospect():   
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name = data.get("name", "Unknown")
    phone = data.get("phone", "")
    business_type = data.get("business_type", "")

    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    prospect_id = str(uuid.uuid4())[:8]
    prospects[prospect_id] = {
        "id": prospect_id,
        "name": name,
        "phone": phone,
        "business_type": business_type,
        "status": "new",
        "last_contact": None,
        "messages": []
    }

    return jsonify({"success": True, "id": prospect_id, "message": f"Prospect {name} added successfully"})

@app.route("/api/delete_prospect/<prospect_id>", methods=["DELETE"])
def delete_prospect(prospect_id):
    if prospect_id in prospects:
        name = prospects[prospect_id].get("name", "Unknown")
        del prospects[prospect_id]
        return jsonify({"success": True, "message": f"Prospect {name} deleted"})
    return jsonify({"error": "Prospect not found"}), 404
if __name__ == "__main__":
    os.makedirs("templates", exist_ok=True)
    app.run(debug=True, port=5000)
