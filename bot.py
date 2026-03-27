import os
import requests
import asyncio
import re
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- CONFIG ---------------- #
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

OTP_VALIDITY_MINUTES = 10
user_emails = {}

app = Flask(__name__)

# ---------------- TEMP MAIL ---------------- #
def generate_email():
    try:
        url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            return None

        data = res.json()
        if not data:
            return None

        return data[0]

    except Exception as e:
        print("Email error:", e)
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


def extract_otp(text):
    otp = re.findall(r"\b\d{4,8}\b", text)
    return otp[0] if otp else None


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
    await update.message.reply_text("🚀 Temp Mail Bot\n\nChoose option:", reply_markup=InlineKeyboardMarkup(kb))


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data == "gen":
        await q.edit_message_text("⏳ Generating email...")

        email = generate_email()

        if not email:
            await q.edit_message_text("❌ Failed (API issue)")
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
                [InlineKeyboardButton("🔄 Auto Check OTP", callback_data="auto")],
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
            await q.edit_message_text("📭 No messages yet")
            return

        text = ""
        for m in msgs:
            data = read_message(login, domain, m["id"])
            subject = data.get("subject", "")
            body = data.get("textBody", "")

            otp = extract_otp(body)

            if otp:
                text += f"🔑 OTP: `{otp}`\n\n"
            else:
                text += f"📩 {subject}\n{body}\n\n"

        await q.edit_message_text(text[:4000], parse_mode="Markdown")

    elif q.data == "auto":
        await q.edit_message_text("🔄 Checking OTP for 30 sec...")

        email = user_emails[user_id]["email"]
        login, domain = email.split("@")

        for _ in range(15):  # 30 sec (2 sec interval)
            msgs = get_messages(login, domain)

            for m in msgs:
                data = read_message(login, domain, m["id"])
                body = data.get("textBody", "")

                otp = extract_otp(body)
                if otp:
                    await q.edit_message_text(f"✅ OTP Found: `{otp}`", parse_mode="Markdown")
                    return

            await asyncio.sleep(2)

        await q.edit_message_text("❌ OTP not found")

    elif q.data == "del":
        user_emails.pop(user_id, None)
        await q.edit_message_text("🗑 Email deleted")


tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(buttons))

# ---------------- FLASK ---------------- #
@app.route("/")
def home():
    return "Bot is running!"


@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return "ok"

# ---------------- START ---------------- #
async def setup():
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    print("✅ Webhook set")


def main():
    asyncio.run(setup())

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()