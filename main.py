import re
import json
import os
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Query

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_TOKEN_HERE")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

DATA_FILE = "data.json"
DEFAULT_USER_ID = "1"

CURRENCY_SYMBOL = {
    "KHR": "៛",
    "USD": "$"
}

# Khmer button mapping (SAFE)
COMMAND_MAP = {
    "សរុបថ្ងៃនេះ": "/today",
    "សរុបខែនេះ": "/this_month"
}

app = FastAPI()
data = {}

# ==============================
# STORAGE
# ==============================
def load_data():
    global data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# ==============================
# TIME
# ==============================
def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_month():
    return datetime.now().strftime("%Y-%m")

def get_user_key(user_id):
    return str(user_id or DEFAULT_USER_ID)

# ==============================
# PARSER (KEEP ORIGINAL – STABLE)
# ==============================
def parse_message(text):
    text = text.replace(":", " ").replace("-", " ")

    pattern = r"(.+?)\s+(\d+(?:[.,]\d+)?)\s*(៛|\$)"
    matches = re.findall(pattern, text)

    results = []
    for cat, amt, symbol in matches:
        amt = float(amt.replace(",", ""))
        currency = "KHR" if symbol == "៛" else "USD"

        if amt.is_integer():
            amt = int(amt)

        results.append({
            "category": cat.strip(),
            "amount": amt,
            "currency": currency
        })

    return results

# ==============================
# VALIDATION (FIXED)
# ==============================
def validate(text, parsed):
    has_number = bool(re.search(r"\d+", text))
    has_currency = bool(re.search(r"(៛|\$)", text))

    if has_number and not has_currency:
        return "⚠️ សូមបញ្ចូលសញ្ញា ៛ ឬ $"

    if has_currency and not parsed:
        return "⚠️ ទិន្នន័យមិនត្រឹមត្រូវ"

    return None

# ==============================
# DATA OPS
# ==============================
def add_expense(user_key, entries):
    today = get_today()
    data.setdefault(user_key, {}).setdefault(today, []).extend(entries)
    save_data()

def get_today_entries(user_key):
    return data.get(user_key, {}).get(get_today(), [])

def get_month_entries(user_key):
    month = get_month()
    result = []

    for d, entries in data.get(user_key, {}).items():
        if d.startswith(month):
            for e in entries:
                item = e.copy()
                item["date"] = d
                result.append(item)

    return result

def calculate(entries):
    khr = sum(e["amount"] for e in entries if e["currency"] == "KHR")
    usd = sum(e["amount"] for e in entries if e["currency"] == "USD")
    return khr, usd

# ✅ FIXED RESET
def reset_today(user_key):
    today = get_today()
    entries = data.get(user_key, {}).get(today, [])

    if entries:
        data[user_key][today] = []
        save_data()
        return True
    return False

def reset_month(user_key):
    month = get_month()
    found = False

    if user_key in data:
        for d in list(data[user_key].keys()):
            if d.startswith(month):
                del data[user_key][d]
                found = True

    if found:
        save_data()

    return found

# ==============================
# FORMAT
# ==============================
def format_entries(entries, show_date=False):
    if not entries:
        return "មិនមានទិន្នន័យ!"

    lines = []
    for e in entries:
        symbol = CURRENCY_SYMBOL[e["currency"]]
        amount = f"{e['amount']:,.0f}" if isinstance(e["amount"], int) else f"{e['amount']:.2f}"

        if show_date:
            lines.append(f"{e['date']} - {e['category']} {amount} {symbol}")
        else:
            lines.append(f"{e['category']} {amount} {symbol}")

    return "\n".join(lines)

def format_total(khr, usd):
    return f"💰 សរុប: {khr:,.0f} ៛ | {usd:.2f} $"

# ==============================
# REPORT
# ==============================
def build_today_report(user_key):
    entries = get_today_entries(user_key)
    khr, usd = calculate(entries)
    return f"📊 ថ្ងៃនេះ\n\n{format_entries(entries)}\n\n{format_total(khr, usd)}"

def build_month_report(user_key):
    entries = get_month_entries(user_key)
    khr, usd = calculate(entries)
    return f"📊 ខែនេះ\n\n{format_entries(entries, True)}\n\n{format_total(khr, usd)}"

# ==============================
# TELEGRAM
# ==============================
def send_message(chat_id, text, buttons=False):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if buttons:
        payload["reply_markup"] = {
            "keyboard": [
                ["សរុបថ្ងៃនេះ", "សរុបខែនេះ"]
            ],
            "resize_keyboard": True
        }

    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

def extract_command(text):
    text = text.strip()

    if text.startswith("សរុបថ្ងៃនេះ"):
        return "/today"

    if text.startswith("សរុបខែនេះ"):
        return "/this_month"

    base = text.split()[0].split("@")[0]
    return base


# ==============================
# WEBHOOK
# ==============================
@app.post("/webhook")
async def telegram_webhook(req: Request):
    update = await req.json()
    message = update.get("message")

    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if not text:
        return {"ok": True}

    user_key = get_user_key(chat_id)
    command = extract_command(text)

    if command.startswith("/today"):
        send_message(chat_id, build_today_report(user_key), buttons=True)

    elif command.startswith("/this_month"):
        send_message(chat_id, build_month_report(user_key), buttons=True)

    elif command == "/reset_today":
        send_message(chat_id,
            "🧹 ទិន្នន័យថ្ងៃនេះត្រូវបានលុប!" if reset_today(user_key)
            else "មិនមានទិន្នន័យ!"
        )

    elif command == "/reset_this_month":
        send_message(chat_id,
            "🧹 ទិន្នន័យខែនេះត្រូវបានលុប!" if reset_month(user_key)
            else "មិនមានទិន្នន័យ!"
        )

    else:
        parsed = parse_message(text)
        error = validate(text, parsed)

        if error:
            send_message(chat_id, error)
            return {"ok": True}

        # ✅ IMPORTANT: no silent behavior
        if not parsed:
            send_message(chat_id, "⚠️ មិនអាចយល់ទិន្នន័យបាន")
            return {"ok": True}

        add_expense(user_key, parsed)
        khr, usd = calculate(parsed)

        send_message(
            chat_id,
            f"បន្ថែម {khr:,.0f} ៛ | {usd:.2f} $",
            buttons=True
        )

    return {"ok": True}

# ==============================
# API
# ==============================
@app.get("/")
def root():
    return {"status": "running"}

@app.get("/today")
def api_today(user_id: str = Query(default=DEFAULT_USER_ID)):
    return {"report": build_today_report(get_user_key(user_id))}

# ==============================
# STARTUP
# ==============================
@app.on_event("startup")
def startup():
    load_data()
