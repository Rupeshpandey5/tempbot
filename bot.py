import os
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ------------------ CONFIG ------------------ #
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables")

# Users storage
# Structure: {user_id: {"email": str, "created": datetime, "messages": list}}
user_emails = {}

OTP_VALIDITY_MINUTES = 10  # OTP/email expiry time


# ------------------ TEMPMAIL FUNCTIONS ------------------ #
def generate_email():
    """Generate a new temp email."""
    try:
        resp = requests.get(
            "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1",
            timeout=10
        )
        data = resp.json()
        return data[0] if data else None
    except Exception as e:
        print("Email generation error:", e)
        return None


def get_messages(login, domain):
    """Get messages for the temp email."""
    try:
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        return requests.get(url, timeout=10).json()
    except Exception as e:
        print("Get messages error:", e)
        return []


def read_message(login, domain, msg_id):
    """Read a single message."""
    try:
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
        return requests.get(url, timeout=10).json()
    except Exception as e:
        print("Read message error:", e)
        return {}


# ------------------ HELPERS ------------------ #
def is_email_valid(user_id):
    """Check if user's temp email is still valid (within OTP_VALIDITY_MINUTES)."""
    if user_id not in user_emails:
        return False
    created = user_emails[user_id]["created"]
    if datetime.utcnow() - created > timedelta(minutes=OTP_VALIDITY_MINUTES):
        del user_emails[user_id]
        return False
    return True


# ------------------ TELEGRAM HANDLERS ------------------ #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📧 Generate Email", callback_data="gen")]
    ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(kb))


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # -------- GENERATE NEW EMAIL -------- #
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
        await query.edit_message_text(f"📧 Your Email:\n`{email}`",
                                      parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(kb))

    # -------- CHECK INBOX -------- #
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

    # -------- DELETE EMAIL -------- #
    elif query.data == "delete":
        if user_id in user_emails:
            del user_emails[user_id]
            await query.edit_message_text("🗑 Email deleted. You can generate a new one.",
                                          reply_markup=InlineKeyboardMarkup(
                                              [[InlineKeyboardButton("📧 Generate Email", callback_data="gen")]]))
        else:
            await query.edit_message_text("⚠️ No email to delete. Generate a new one.")


# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    print("✅ Bot running...")
    app.run_polling()