import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OTP_VALIDITY_MINUTES = 10
user_emails = {}

app = Flask(__name__)

# ---------------- TEMP MAIL FUNCTIONS ---------------- #
def generate_email():
    try:
        return requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1", timeout=10).json()[0]
    except:
        return None

def get_messages(login, domain):
    try:
        return requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}", timeout=10).json()
    except:
        return []

def read_message(login, domain, msg_id):
    try:
        return requests.get(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}", timeout=10).json()
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

# ---------------- TELEGRAM APPLICATION ---------------- #
app_bot = ApplicationBuilder().token(TOKEN).build()
app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(CallbackQueryHandler(buttons))

# ---------------- FLASK ROUTES ---------------- #
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_bot.bot)
    app_bot.create_task(app_bot.process_update(update))
    return "ok"

@app.route("/")
def home():
    return "Bot is running!"

# ---------------- STARTUP ---------------- #
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app_bot.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}"))
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)