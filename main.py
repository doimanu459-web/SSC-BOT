import os
import requests
from flask import Flask, request

# Optional official Gemini client (recommended if installed)
try:
    import google.generativeai as genai
except Exception:
    genai = None

app = Flask(__name__)

# ---- Environment variables (hosting dashboard me set karo) ----
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ssc123")       # koi bhi secret word
WA_TOKEN = os.environ["WA_TOKEN"]                              # Meta WhatsApp access token
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]                # Meta dashboard se
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")              # aistudio.google.com se free key
# Use a supported model name to avoid runtime errors. Recommended: gemini-1.5-flash or gemini-1.5-pro
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# If the google.generativeai package is available, configure it (safe no-op if not installed)
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        # don't fail startup if client configuration fails
        pass

# ---- Apni coaching ki details yahan bharo ----
COACHING_INFO = """
Coaching ka naam: HARENDRA CLASSESS JAIPUR
Courses: SSC CGL, CHSL, MTS, GD
Batch timing: MORNING 9 TO 12 AND EVENING 3 TO 6
Fees: ₹12,000 FOR ONE YEAR
Address: JAIPUR
Contact: <PHONE NUMBER>
Demo class: <DETAILS>
"""

SYSTEM_PROMPT = f"""Tum ek SSC coaching ke helpful WhatsApp assistant ho.
Hinglish ya Hindi me chhote, simple jawab do (WhatsApp style).
Neeche di gayi coaching info ke basis par hi fees, batch, timing batao.
Agar info nahi hai to guess mat karo, bolo ki "Hamari team aapko call karegi".
SSC exam ke general doubts (syllabus, pattern, strategy) me madad kar sakte ho.
Har jawab ke end me admission ke liye invite kar sakte ho, par zyada pushy mat bano.

{COACHING_INFO}
"""

# Simple in-memory history (restart par reset ho jayegi)
history = {}


def ask_gemini(user_id, text):
    turns = history.setdefault(user_id, [])
    turns.append({"role": "user", "parts": [{"text": text}]})
    turns[:] = turns[-8:]  # last 8 messages hi rakho

    # Preferred: if the official client is available you can switch to it.
    # The REST endpoint below continues to work; ensure model name is supported (gemini-1.5-flash / gemini-1.5-pro).
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": turns,
    }

    try:
        # If the official client is installed you may prefer to use it instead of the REST call.
        # Example (provided by Gemini):
        # import google.generativeai as genai
        # genai.configure(api_key=GEMINI_API_KEY)
        # model = genai.GenerativeModel('gemini-1.5-flash')
        # response = model.generate(...)
        # But to keep compatibility without requiring the client, we call the REST endpoint here.
        r = requests.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=30)
        r.raise_for_status()
        reply = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("Gemini error:", e)
        return "Abhi thodi technical problem hai. Kripya thodi der baad try karein."

    turns.append({"role": "model", "parts": [{"text": reply}]})
    return reply


def send_whatsapp(to, text):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:4000]},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code >= 400:
        print("WhatsApp send error:", r.text)


@app.route("/webhook", methods=["GET"])
def verify():
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def incoming():
    data = request.get_json(silent=True) or {}
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages")
        if messages:
            msg = messages[0]
            sender = msg["from"]
            if msg.get("type") == "text":
                reply = ask_gemini(sender, msg["text"]["body"])
            else:
                reply = "Abhi main sirf text message samajh sakta hoon. Apna sawal likh kar bhejein."
            send_whatsapp(sender, reply)
    except Exception as e:
        print("Webhook error:", e)
    return "OK", 200


@app.route("/")
def home():
    return "SSC bot is running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
