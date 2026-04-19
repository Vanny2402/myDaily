import re
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# ==============================
# CONFIG
# ==============================
TOKEN = "8753319762:AAEfunhd45eHtyvS5Z7EaTZd0LkoJXcA8PI"
MY_USER_ID = None
DATA_FILE = "data.json"

CURRENCY_SYMBOL = {
    "KHR": "៛",
    "USD": "$"
}

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

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_month():
    return datetime.now().strftime("%Y-%m")

def get_user_key(user_id):
    return str(user_id)

# ==============================
# PARSER (៛ / $ ONLY)
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
# VALIDATION (៛ / $ ONLY)
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
# FORMATTERS
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
# HANDLER (ADD EXPENSE)
# ==============================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    text = update.message.text

    if MY_USER_ID and user.id != MY_USER_ID:
        return

    parsed = parse_message(text)
    error = validate(text, parsed)

    if error:
        await update.message.reply_text(error)
        return

    if not parsed:
        return

    user_key = get_user_key(user.id)
    add_expense(user_key, parsed)

    khr, usd = calculate(parsed)

    await update.message.reply_text(
        f"➕ បានបញ្ចូលជោគជ័យ: {khr:,.0f} ៛ | {usd:.2f} $ \n\nដើម្បីពិនិត្យទិន្នន័យថ្ងៃនេះ ចុច /today  \n\n ដើម្បីពិនិត្យទិន្នន័យខែនេះ/this_month"
    )

# ==============================
# COMMANDS
# ==============================
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_key = get_user_key(user.id)

    entries = get_today_entries(user_key)
    khr, usd = calculate(entries)

    msg = (
        f"📊 {user.first_name} (ថ្ងៃនេះ)\n\n"
        f"{format_entries(entries)}\n\n"
        f"{format_total(khr, usd)}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_this_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_key = get_user_key(user.id)

    entries = get_month_entries(user_key)
    khr, usd = calculate(entries)

    msg = (
        f"📊 {user.first_name} (ខែនេះ)\n\n"
        f"{format_entries(entries, show_date=True)}\n\n"
        f"{format_total(khr, usd)}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_key = get_user_key(update.message.from_user.id)

    if reset_today(user_key):
        await update.message.reply_text("🧹 ទិន្នន័យត្រូវបានសម្អាត.")
    else:
        await update.message.reply_text("Nothing to reset.")

async def cmd_reset_this_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_key = get_user_key(update.message.from_user.id)

    if reset_month(user_key):
        await update.message.reply_text("🧹 ទិន្នន័យខែនេះត្រូវបានសម្អាត.")
    else:
        await update.message.reply_text("Nothing to reset.")

# ==============================
# MAIN
# ==============================
def main():
    load_data()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("this_month", cmd_this_month))
    app.add_handler(CommandHandler("reset_today", cmd_reset_today))
    app.add_handler(CommandHandler("reset_this_month", cmd_reset_this_month))

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
