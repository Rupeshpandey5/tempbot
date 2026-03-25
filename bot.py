import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- CONFIG ---------------- #
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com

OTP_VALIDITY_MINUTES = 10
user_emails = {}

app = Flask(__name__)

# ---------------- TEMP MAIL ---------------- #
def generate_email():
    try:
        url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        return requests.get(url, timeout=10).json()[0]
    except Exception as e:
        print("Email error:", e)
        return None


def get_messages(login, domain):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        return requests.get(url).json()
    except:
        return []


def read_message(login, domain, msg_id):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
        return requests.get(url).json()
    except:
        return {}


def is_valid(user_id):
    if user_id not in user_emails:
        return False

    if datetime.utcnow() - user_emails[user_id]["time"] > timedelta(minutes=OTP_VALIDITY_MINUTES):
        del user_emails[user_id]
        return False

    return True

# ---------------- TELEGRAM ---------------- #
tg_app = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("📧 Generate Email", callback_data="gen")]]
    await update.message.reply_text("Choose:", reply_markup=InlineKeyboardMarkup(kb))


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data == "gen":
        await q.edit_message_text("⏳ Generating...")

        email = generate_email()
        if not email:
            await q.edit_message_text("❌ Failed")
            return

        user_emails[user_id] = {
            "email": email,
            "time": datetime.utcnow()
        }

        await q.edit_message_text(
            f"📧 `{email}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Inbox", callback_data="check")],
                [InlineKeyboardButton("🗑 Delete", callback_data="del")]
            ])
        )

    elif q.data == "check":
        if not is_valid(user_id):
            await q.edit_message_text("⚠️ Expired")
            return

        email = user_emails[user_id]["email"]
        login, domain = email.split("@")

        msgs = get_messages(login, domain)

        if not msgs:
            await q.edit_message_text("📭 Empty")
            return

        text = ""
        for m in msgs:
            data = read_message(login, domain, m["id"])
            text += f"{data.get('subject')}\n{data.get('textBody')}\n\n"

        await q.edit_message_text(text[:4000])

    elif q.data == "del":
        user_emails.pop(user_id, None)
        await q.edit_message_text("🗑 Deleted")


tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(buttons))

# ---------------- FLASK ROUTES ---------------- #
@app.route("/")
def home():
    return "Bot is running!"

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return "ok"

# ---------------- STARTUP ---------------- #
async def setup_webhook():
    await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    print("✅ Webhook set!")

def main():
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(tg_app.initialize())
    loop.run_until_complete(setup_webhook())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()