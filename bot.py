import logging
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")  # مثل http://reliable-solace.railway.internal:8080/v1/chat/completions

# آدرس پایه برای درخواست‌های GET (بدون /v1/chat/completions)
BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")

if not TELEGRAM_TOKEN or not FREELLMAPI_KEY or not FREELLMAPI_URL:
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY and FREELLMAPI_URL must be set")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===== دستور /status =====
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    
    try:
        # دریافت لیست مدل‌ها از FreeLLMAPI
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            
            if not models:
                await status_msg.edit_text("❌ هیچ مدلی در دسترس نیست.")
                return
            
            # دسته‌بندی مدل‌ها بر اساس وضعیت
            available = []
            unavailable = []
            limited = []
            
            for model in models:
                model_id = model.get("id", "نامشخص")
                # وضعیت می‌تواند در فیلدهای مختلف باشد (بستگی به پیاده‌سازی FreeLLMAPI دارد)
                status = model.get("status", "unknown")
                
                if status == "available" or status == "active":
                    available.append(model_id)
                elif status == "unavailable" or status == "inactive":
                    unavailable.append(model_id)
                elif status == "limited" or status == "rate_limited":
                    limited.append(model_id)
                else:
                    # اگر وضعیت مشخص نبود، آن را در دسترس در نظر بگیریم
                    available.append(model_id)
            
            # ساخت پیام وضعیت
            reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n\n"
            
            if available:
                reply += "✅ **در دسترس:**\n" + "\n".join([f"• {m}" for m in available[:20]]) + "\n\n"
            if limited:
                reply += "⚠️ **محدودیت خورده:**\n" + "\n".join([f"• {m}" for m in limited]) + "\n\n"
            if unavailable:
                reply += "❌ **در دسترس نیست:**\n" + "\n".join([f"• {m}" for m in unavailable]) + "\n\n"
            
            if not available and not limited and not unavailable:
                reply = "❌ هیچ اطلاعاتی از مدل‌ها در دسترس نیست."
            
            # دکمه‌ی به‌روزرسانی
            keyboard = [[InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_status")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(reply, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await status_msg.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
            
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await status_msg.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")

# ===== مدیریت کلیک روی دکمه‌ی به‌روزرسانی =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh_status":
        # دوباره وضعیت را بگیر و نمایش بده (همان تابع status_command)
        await status_command(update, context)

# ===== تابع اصلی =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    if user_message.startswith('/'):
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
            await update.message.reply_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات روشن شد...")
    application.run_polling()

if __name__ == "__main__":
    main()
