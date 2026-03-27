# bot.py
import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# -------------------------------
# Environment Variables
TOKEN = os.environ.get("BOT_TOKEN")  # your bot token
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://tempbot-1-q0wo.onrender.com
PORT = int(os.environ.get("PORT", 10000))  # Render port

# -------------------------------
# Flask App
app = Flask(__name__)

# -------------------------------
# Telegram Bot Application
application = Application.builder().token(TOKEN).build()
bot = Bot(TOKEN)

# -------------------------------
# Command Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is working 🚀")

application.add_handler(CommandHandler("start", start))

# -------------------------------
# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """Receive updates from Telegram."""
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "OK"

# -------------------------------
# Run webhook on Render
if __name__ == "__main__":
    # Set webhook once
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}"))
    print(f"Webhook set at {WEBHOOK_URL}/{TOKEN}")

    # Start Flask server
    app.run(host="0.0.0.0", port=PORT)