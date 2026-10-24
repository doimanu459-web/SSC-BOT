import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ---- Environment variables (Render ke Environment page me set karo) ----
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ssc12345")   # koi bhi secret word
WA_TOKEN = os.environ["WA_TOKEN"]                            # Meta WhatsApp access token
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]              # Meta dashboard se
GROQ_API_KEY = os.environ["GROQ_API_KEY"]                    # console.groq.com se free key
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# ---- Apni coaching ki details yahan bharo ----
COACHING_INFO = """
Coaching ka naam: <APNI COACHING KA NAAM>
Courses: SSC CGL, CHSL, MTS, GD, CPO
Batch timing: <TIMING>
Fees: <FEES>
Address: <ADDRESS>
Contact: <PHONE NUMBER>
Demo class: <DETAILS>
"""

SYSTEM_PROMPT = f"""Tum ek SSC coaching ke helpful WhatsApp assistant ho.
Hinglish ya Hindi me chhote, simple jawab do (WhatsApp style).
Neeche di gayi coaching info ke basis par hi fees, batch, timing batao.
Agar info nahi hai to guess mat karo, bolo ki "Hamari team aapko call karegi".
SSC exam ke general doubts (syllabus, pattern, strategy) me madad kar sakte ho.
Admission ke liye invite kar sakte ho, par zyada pushy mat bano.

{COACHING_INFO}
"""

# Simple in-memory history (server restart par reset ho jayegi)
history = {}


def ask_llm(user_id, text):
    turns = history.setdefault(user_id, [])
    turns.append({"role": "user", "content": text})
    turns[:] = turns[-8:]  # last 8 messages hi rakho

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + turns
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": GROQ_MODEL, "messages": messages},
            timeout=30,
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        # API key header me jati hai, isliye log me key nahi aati
        print("LLM error:", e)
        return "Abhi thodi technical problem hai. Kripya thodi der baad try karein."

    turns.append({"role": "assistant", "content": reply})
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
        print("WhatsApp send error:", r.status_code, r.text)


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
                reply = ask_llm(sender, msg["text"]["body"])
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
