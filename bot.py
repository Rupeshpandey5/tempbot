import os
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_emails = {}


# ---------------- API ---------------- #
def generate_email():
    try:
        r = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1", timeout=10)
        return r.json()[0]
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


# ---------------- HANDLERS ---------------- #
@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Generate Email", callback_data="gen")]
    ])

    await message.answer("Choose option:", reply_markup=kb)


@dp.callback_query()
async def buttons(call: types.CallbackQuery):
    user_id = call.from_user.id

    # GENERATE EMAIL
    if call.data == "gen":
        email = generate_email()

        if not email:
            await call.message.edit_text("❌ Error generating email")
            return

        user_emails[user_id] = email

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Check Inbox", callback_data="check")],
            [InlineKeyboardButton(text="🔄 New Email", callback_data="gen")]
        ])

        await call.message.edit_text(f"📧 Your Email:\n`{email}`", reply_markup=kb, parse_mode="Markdown")

    # CHECK INBOX
    elif call.data == "check":
        if user_id not in user_emails:
            await call.message.edit_text("⚠️ Generate email first")
            return

        email = user_emails[user_id]
        login, domain = email.split("@")

        msgs = get_messages(login, domain)

        if not msgs:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Refresh", callback_data="check")],
                [InlineKeyboardButton(text="📧 New Email", callback_data="gen")]
            ])
            await call.message.edit_text("📭 No messages yet", reply_markup=kb)
            return

        text = "📥 Inbox:\n\n"

        for msg in msgs:
            data = read_message(login, domain, msg["id"])
            text += f"From: {data.get('from')}\nSubject: {data.get('subject')}\n\n{data.get('textBody')}\n\n---\n"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="check")],
            [InlineKeyboardButton(text="📧 New Email", callback_data="gen")]
        ])

        await call.message.edit_text(text[:4000], reply_markup=kb)


# ---------------- MAIN ---------------- #
async def main():
    print("✅ Bot running (Python 3.14)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())