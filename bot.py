import logging
import requests
import os
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ===== تنظیمات از متغیرهای محیطی =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not all([TELEGRAM_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL]):
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL and DATABASE_URL must be set")

BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")
MAX_HISTORY = 20

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===== اتصال به دیتابیس =====
async def init_db():
    """ایجاد جدول history در دیتابیس (اگر وجود نداشته باشد)"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.close()
    logging.info("✅ دیتابیس PostgreSQL آماده است.")

async def save_message(user_id: str, role: str, content: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
        user_id, role, content
    )
    await conn.close()

async def get_history(user_id: str, limit: int = MAX_HISTORY):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT role, content FROM chat_history WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
        user_id, limit * 2
    )
    await conn.close()
    return list(reversed(rows))

async def clear_history(user_id: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)
    await conn.close()

# ===== دستورات =====
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    try:
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
            available = []
            unavailable = []
            limited = []
            for model in models:
                model_id = model.get("id", "نامشخص")
                status = model.get("status", "unknown")
                if status in ["available", "active"]:
                    available.append(model_id)
                elif status in ["unavailable", "inactive"]:
                    unavailable.append(model_id)
                elif status in ["limited", "rate_limited"]:
                    limited.append(model_id)
                else:
                    available.append(model_id)
            reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n\n"
            if available:
                reply += "✅ **در دسترس:**\n" + "\n".join([f"• {m}" for m in available[:20]]) + "\n\n"
            if limited:
                reply += "⚠️ **محدودیت خورده:**\n" + "\n".join([f"• {m}" for m in limited]) + "\n\n"
            if unavailable:
                reply += "❌ **در دسترس نیست:**\n" + "\n".join([f"• {m}" for m in unavailable]) + "\n\n"
            if not available and not limited and not unavailable:
                reply = "❌ هیچ اطلاعاتی از مدل‌ها در دسترس نیست."
            keyboard = [[InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_status")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await status_msg.edit_text(reply, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await status_msg.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await status_msg.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "refresh_status":
        await status_command(update, context)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    await update.message.reply_text("🧹 حافظه‌ی مکالمه شما پاک شد.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    if user_message.startswith('/'):
        return
    history = await get_history(user_id, MAX_HISTORY)
    messages = []
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    headers = {
        "Authorization": f"Bearer {FREELLMAPI_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "auto",
        "messages": messages
    }
    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            ai_reply = result["choices"][0]["message"]["content"]
            await save_message(user_id, "user", user_message)
            await save_message(user_id, "assistant", ai_reply)
            await update.message.reply_text(ai_reply)
        else:
            await update.message.reply_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")

# ===== تابع اصلی =====
async def main():
    # مقداردهی اولیه دیتابیس
    await init_db()
    
    # ساخت اپلیکیشن
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات با حافظه‌ی دائمی PostgreSQL روشن شد...")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
