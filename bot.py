import os
import requests
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- CONFIG ---------------- #
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables")

user_emails = {}
OTP_VALIDITY_MINUTES = 10

# ---------------- TEMPMAIL FUNCTIONS ---------------- #
def generate_email():
    try:
        resp = requests.get(
            "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1",
            timeout=10
        )
        data = resp.json()
        return data[0] if data else None
    except:
        return None

def get_messages(login, domain):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        return requests.get(url, timeout=10).json()
    except:
        return []

def read_message(login, domain, msg_id):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
        return requests.get(url, timeout=10).json()
    except:
        return {}

def is_email_valid(user_id):
    if user_id not in user_emails:
        return False
    created = user_emails[user_id]["created"]
    if datetime.utcnow() - created > timedelta(minutes=OTP_VALIDITY_MINUTES):
        del user_emails[user_id]
        return False
    return True

# ---------------- TELEGRAM HANDLERS ---------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("📧 Generate Email", callback_data="gen")]]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(kb))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "gen":
        email = generate_email()
        if not email:
            await query.edit_message_text("❌ Failed to generate email. Try again.")
            return
        user_emails[user_id] = {"email": email, "created": datetime.utcnow()}
        kb = [
            [InlineKeyboardButton("📥 Check Inbox", callback_data="check")],
            [InlineKeyboardButton("🗑 Delete Email", callback_data="delete")],
            [InlineKeyboardButton("🔄 New Email", callback_data="gen")]
        ]
        await query.edit_message_text(f"📧 Your Email:\n`{email}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "check":
        if not is_email_valid(user_id):
            await query.edit_message_text("⚠️ Email expired. Generate a new one.")
            return
        email = user_emails[user_id]["email"]
        login, domain = email.split("@")
        msgs = get_messages(login, domain)
        if not msgs:
            kb = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
                [InlineKeyboardButton("🔄 New Email", callback_data="gen")]
            ]
            await query.edit_message_text("📭 No messages yet.", reply_markup=InlineKeyboardMarkup(kb))
            return
        text = "📥 Inbox:\n\n"
        for msg in msgs:
            data = read_message(login, domain, msg["id"])
            sender = data.get("from", "Unknown")
            subject = data.get("subject", "No Subject")
            body = data.get("textBody", "No Content")
            text += f"From: {sender}\nSubject: {subject}\n\n{body}\n\n{'-'*20}\n"
        kb = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
            [InlineKeyboardButton("🗑 Delete Email", callback_data="delete")],
            [InlineKeyboardButton("🔄 New Email", callback_data="gen")]
        ]
        await query.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "delete":
        if user_id in user_emails:
            del user_emails[user_id]
            await query.edit_message_text("🗑 Email deleted. You can generate a new one.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📧 Generate Email", callback_data="gen")]]))
        else:
            await query.edit_message_text("⚠️ No email to delete. Generate a new one.")

# ---------------- FLASK SERVER ---------------- #
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ---------------- RUN BOT ---------------- #
def run_bot():
    tg_app = ApplicationBuilder().token(TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(button))
    print("✅ Telegram bot running...")
    tg_app.run_polling()

if __name__ == "__main__":
    # Start Flask server in separate thread
    Thread(target=run_flask).start()
    # Run Telegram bot
    run_bot()