import logging
import requests
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ===== تنظیمات از متغیرهای محیطی =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL", "https://your-freellmapi-service.onrender.com/v1/chat/completions")

# اگر توکن تنظیم نشده، خطا بده
if not TELEGRAM_TOKEN or not FREELLMAPI_KEY:
    raise ValueError("BOT_TOKEN and FREELLMAPI_KEY must be set in environment variables")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    if user_message.startswith('/'):
        await update.message.reply_text("سلام! من یک دستیار هوشمند هستم. هر سوالی داری، بپرس.")
        return

    headers = {
        "Authorization": f"Bearer {FREELLMAPI_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "auto",
        "messages": [{"role": "user", "content": user_message}]
    }

    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            ai_reply = result["choices"][0]["message"]["content"]
            await update.message.reply_text(ai_reply)
        else:
            await update.message.reply_text("خطایی در دریافت پاسخ از هوش مصنوعی رخ داد.")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to FreeLLMAPI: {e}")
        await update.message.reply_text("متاسفانه سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("ربات روشن شد...")
    application.run_polling()

if __name__ == "__main__":
    main()