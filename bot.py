import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN")

user_emails = {}


# ------------------ API FUNCTIONS ------------------ #
def generate_email():
    try:
        resp = requests.get(
            "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1",
            timeout=10
        )
        data = resp.json()
        return data[0] if data else None
    except Exception as e:
        print("Email generate error:", e)
        return None


def get_messages(login, domain):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        return requests.get(url, timeout=10).json()
    except Exception as e:
        print("Get messages error:", e)
        return []


def read_message(login, domain, msg_id):
    try:
        url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
        return requests.get(url, timeout=10).json()
    except Exception as e:
        print("Read message error:", e)
        return {}


# ------------------ HANDLERS ------------------ #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📧 Generate Email", callback_data="gen")]
    ]

    await update.effective_message.reply_text(
        "Choose option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # -------- GENERATE EMAIL -------- #
    if query.data == "gen":
        email = generate_email()

        if not email:
            await query.edit_message_text("❌ Error generating email. Try again.")
            return

        user_emails[user_id] = email

        keyboard = [
            [InlineKeyboardButton("📥 Check Inbox", callback_data="check")],
            [InlineKeyboardButton("🔄 New Email", callback_data="gen")]
        ]

        await query.edit_message_text(
            f"📧 Your Email:\n`{email}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # -------- CHECK INBOX -------- #
    elif query.data == "check":
        if user_id not in user_emails:
            await query.edit_message_text("⚠️ Generate email first.")
            return

        email = user_emails[user_id]
        login, domain = email.split("@")

        msgs = get_messages(login, domain)

        if not msgs:
            await query.edit_message_text(
                "📭 No messages yet.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
                    [InlineKeyboardButton("📧 New Email", callback_data="gen")]
                ])
            )
            return

        text = "📥 Inbox:\n\n"

        for msg in msgs:
            data = read_message(login, domain, msg["id"])

            sender = data.get("from", "Unknown")
            subject = data.get("subject", "No Subject")
            body = data.get("textBody", "No Content")

            text += f"From: {sender}\nSubject: {subject}\n\n{body}\n\n{'-'*20}\n"

        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
                [InlineKeyboardButton("📧 New Email", callback_data="gen")]
            ])
        )


# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("BOT_TOKEN not set in environment variables")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("✅ Bot running...")
    app.run_polling()