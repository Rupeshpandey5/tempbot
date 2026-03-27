import os
import requests
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- CONFIG ---------------- #
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://tempbot-1-q0wo.onrender.com
OTP_VALIDITY_MINUTES = 10
user_emails = {}

# ---------------- FLASK APP ---------------- #
app = Flask(__name__)

# ---------------- TELEGRAM BOT ---------------- #
tg_app = Application.builder().token(TOKEN).build()

# ---------------- TEMP MAIL FUNCTIONS ---------------- #
def generate_email():
    try:
        url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        return requests.get(url, timeout=10).json()[0]
    except:
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

# ---------------- TELEGRAM HANDLERS ---------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("📧 Generate Email", callback_data="gen")]]
    await update.message.reply_text("🚀 Temp Mail Bot\nChoose option:", reply_markup=InlineKeyboardMarkup(kb))

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data == "gen":
        await q.edit_message_text("⏳ Generating email...")
        email = generate_email()
        if not email:
            await q.edit_message_text("❌ Failed to generate email")
            return
        user_emails[user_id] = {"email": email, "time": datetime.utcnow()}
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
            await q.edit_message_text("⚠️ Email expired")
            return
        email = user_emails[user_id]["email"]
        login, domain = email.split("@")
        msgs = get_messages(login, domain)
        if not msgs:
            await q.edit_message_text("📭 Inbox is empty")
            return
        text = ""
        for m in msgs:
            data = read_message(login, domain, m["id"])
            text += f"📬 {data.get('subject')}\n{data.get('textBody')}\n\n"
        await q.edit_message_text(text[:4000])

    elif q.data == "del":
        user_emails.pop(user_id, None)
        await q.edit_message_text("🗑 Email deleted")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(buttons))

# ---------------- FLASK ROUTES ---------------- #
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, tg_app.bot)
    asyncio.run(tg_app.process_update(update))
    return "ok"

@app.route("/")
def home():
    return "Bot is running!"

# ---------------- STARTUP ---------------- #
if __name__ == "__main__":
    asyncio.run(tg_app.initialize())
    asyncio.run(tg_app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}"))
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)