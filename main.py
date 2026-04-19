import re
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query

# ==============================
# CONFIG
# ==============================
DATA_FILE = "data.json"
DEFAULT_USER_ID = "1"

CURRENCY_SYMBOL = {
    "KHR": "៛",
    "USD": "$"
}

app = FastAPI()

# ==============================
# STORAGE
# ==============================
data = {}

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
# HELPERS
# ==============================
def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_month():
    return datetime.now().strftime("%Y-%m")

def get_user_key(user_id):
    return str(user_id or DEFAULT_USER_ID)

# ==============================
# PARSER
# ==============================
def parse_message(text):
    pattern = r"([^\d]+?)\s*(\d+(?:[.,]\d+)?)\s*(៛|\$)"
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
# VALIDATION
# ==============================
def validate(text, parsed):
    if parsed:
        return None

    has_number = re.search(r"\d+", text)
    has_symbol = re.search(r"(៛|\$)", text)

    if has_number and not has_symbol:
        return "⚠️ ទិន្នន័យមិនត្រូវបានបញ្ចូល។ សូមពិនត្យសញ្ញាឡើងវិញ (៛ ឬ $)\n\nឧទាហរណ៍: ទិញបាយ 2$ ឬ ទិញបាយ 8000៛"

    return None

# ==============================
# DATA OPERATIONS
# ==============================
def add_expense(user_key, entries):
    today = get_today()

    data.setdefault(user_key, {})
    data[user_key].setdefault(today, [])

    data[user_key][today].extend(entries)
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

def reset_today(user_key):
    today = get_today()
    if user_key in data and today in data[user_key]:
        data[user_key][today] = []
        save_data()
        return True
    return False

def reset_month(user_key):
    month = get_month()
    if user_key in data:
        keys = [d for d in data[user_key] if d.startswith(month)]
        for k in keys:
            del data[user_key][k]
        save_data()
        return True
    return False

# ==============================
# FORMATTERS (KHMER PRESERVED)
# ==============================
def format_entries(entries, show_date=False):
    lines = []

    for e in entries:
        symbol = CURRENCY_SYMBOL.get(e["currency"], e["currency"])

        amount = f"{e['amount']:,.0f}" if isinstance(e["amount"], int) else f"{e['amount']:.2f}"

        if show_date:
            lines.append(f"{e['date']} - {e['category']} {amount} {symbol}")
        else:
            lines.append(f"{e['category']} {amount} {symbol}")

    return "\n".join(lines) if lines else "មិនមានទិន្នន័យ!"

def format_total(khr, usd):
    return f"**💰 សរុប: {khr:,.0f} ៛ | {usd:.2f} $**"

# ==============================
# CORE LOGIC (REUSABLE)
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
# API ENDPOINTS
# ==============================

@app.post("/add")
def api_add(
    text: str,
    user_id: str = Query(default=DEFAULT_USER_ID)
):
    user_key = get_user_key(user_id)

    parsed = parse_message(text)
    error = validate(text, parsed)

    if error:
        raise HTTPException(status_code=400, detail=error)

    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid input")

    add_expense(user_key, parsed)

    khr, usd = calculate(parsed)

    return {
        "message": f"➕ បានបញ្ចូលជោគជ័យ: {khr:,.0f} ៛ | {usd:.2f} $",
        "hint": "ដើម្បីពិនិត្យទិន្នន័យថ្ងៃនេះ → /today | ខែនេះ → /this_month"
    }


@app.get("/today")
def api_today(user_id: str = Query(default=DEFAULT_USER_ID)):
    user_key = get_user_key(user_id)

    return {
        "report": build_today_report(user_key)
    }


@app.get("/this_month")
def api_this_month(user_id: str = Query(default=DEFAULT_USER_ID)):
    user_key = get_user_key(user_id)

    return {
        "report": build_month_report(user_key)
    }


@app.delete("/reset_today")
def api_reset_today(user_id: str = Query(default=DEFAULT_USER_ID)):
    user_key = get_user_key(user_id)

    if reset_today(user_key):
        return {"message": "🧹 ទិន្នន័យត្រូវបានសម្អាត."}

    raise HTTPException(status_code=404, detail="Nothing to reset")


@app.delete("/reset_this_month")
def api_reset_this_month(user_id: str = Query(default=DEFAULT_USER_ID)):
    user_key = get_user_key(user_id)

    if reset_month(user_key):
        return {"message": "🧹 ទិន្នន័យខែនេះត្រូវបានសម្អាត."}

    raise HTTPException(status_code=404, detail="Nothing to reset")


# ==============================
# STARTUP
# ==============================
@app.on_event("startup")
def startup():
    load_data()
