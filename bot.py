import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")  # secure way

user_emails = {}

def generate_email():
    resp = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1")
    return resp.json()[0]

def get_messages(login, domain):
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    return requests.get(url).json()

def read_message(login, domain, msg_id):
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    return requests.get(url).json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📧 Generate Email", callback_data="gen")],
    ]
    await update.message.reply_text("Choose option:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "gen":
        email = generate_email()
        user_emails[user_id] = email

        keyboard = [
            [InlineKeyboardButton("📥 Check Inbox", callback_data="check")],
            [InlineKeyboardButton("🔄 New Email", callback_data="gen")]
        ]

        await query.edit_message_text(
            f"Your Email:\n`{email}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "check":
        if user_id not in user_emails:
            await query.edit_message_text("Generate email first.")
            return

        email = user_emails[user_id]
        login, domain = email.split("@")

        msgs = get_messages(login, domain)

        if not msgs:
            await query.edit_message_text(
                "No messages yet.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
                    [InlineKeyboardButton("📧 New Email", callback_data="gen")]
                ])
            )
            return

        text = ""
        for msg in msgs:
            data = read_message(login, domain, msg["id"])
            text += f"From: {data['from']}\nSubject: {data['subject']}\n\n{data['textBody']}\n\n"

        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="check")],
                [InlineKeyboardButton("📧 New Email", callback_data="gen")]
            ])
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot running...")
    app.run_polling()
