import logging
import requests
import os
import asyncpg
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not all([TELEGRAM_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL]):
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL and DATABASE_URL must be set")

BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")
MAX_HISTORY = 20

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===== دیتابیس =====
async def init_db():
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

# ===== دستور /start =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "کاربر عزیز"
    
    welcome_text = f"""
🌟 **به ربات هوشمند خوش آمدید، {user_name}!** 🌟

🤖 من یک دستیار قدرتمند هستم که با استفاده از هوش مصنوعی به سوالات شما پاسخ می‌دهم.

✨ **قابلیت‌های من:**
• 💬 پاسخ به سوالات شما به زبان فارسی
• 🧠 حافظه‌ی دائمی برای هر کاربر (تا ۲۰ پیام آخر)
• 📊 نمایش وضعیت مدل‌های هوش مصنوعی
• 🔄 انتخاب خودکار بهترین مدل توسط FreeLLMAPI
• 🤖 نمایش نام مدل پاسخ‌دهنده در انتهای هر پیام

📌 **دستورات مفید:**
• `/status` – وضعیت مدل‌های موجود
• `/clear` – پاک کردن حافظه‌ی مکالمه
• `/start` – نمایش این پیام

💡 فقط کافی است سوال خود را بپرسید و من پاسخ می‌دهم!
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="status_btn")],
        [InlineKeyboardButton("🧹 پاک کردن حافظه", callback_data="clear_btn")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== دستور /status =====
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تشخیص اینکه از پیام عادی اومده یا از دکمه
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        edit_mode = True
    else:
        message = update.message
        edit_mode = False
    
    if edit_mode:
        status_msg = await message.edit_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    else:
        status_msg = await message.reply_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    
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
            
            available, unavailable, limited = [], [], []
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
            
            reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n"
            reply += "─" * 25 + "\n\n"
            
            if available:
                reply += "✅ **در دسترس:**\n"
                reply += "\n".join([f"• `{m}`" for m in available[:20]]) + "\n\n"
            if limited:
                reply += "⚠️ **محدودیت خورده:**\n"
                reply += "\n".join([f"• `{m}`" for m in limited]) + "\n\n"
            if unavailable:
                reply += "❌ **در دسترس نیست:**\n"
                reply += "\n".join([f"• `{m}`" for m in unavailable]) + "\n\n"
            if not available and not limited and not unavailable:
                reply = "❌ هیچ اطلاعاتی از مدل‌ها در دسترس نیست."
            
            keyboard = [
                [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_status")],
                [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(reply, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await status_msg.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await status_msg.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")

# ===== دستور /clear =====
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🧹 **حافظه‌ی مکالمه شما با موفقیت پاک شد!**\n\n✨ از این به بعد همه‌چیز را از اول شروع می‌کنیم.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ===== دستور /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **راهنمای ربات**

🤖 این ربات با استفاده از هوش مصنوعی به سوالات شما پاسخ می‌دهد.

🔹 **نحوه استفاده:**
• هر سوالی دارید، به‌صورت عادی بپرسید.
• من تاریخچه‌ی مکالمه را به خاطر می‌سپارم.

🔹 **دستورات:**
• `/start` – نمایش منوی اصلی
• `/status` – وضعیت مدل‌های هوش مصنوعی
• `/clear` – پاک کردن حافظه‌ی مکالمه
• `/help` – نمایش این راهنما

🔹 **ویژگی‌ها:**
• انتخاب خودکار بهترین مدل
• حافظه‌ی دائمی برای هر کاربر
• پاسخ‌های روان و فارسی
• **نمایش نام مدل پاسخ‌دهنده در انتهای هر پیام**

💡 فقط سوال خود را بپرسید!
    """
    
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== مدیریت دکمه‌ها =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh_status":
        # ارسال به status_command با callback_query
        await status_command(update, context)
    
    elif query.data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="status_btn")],
            [InlineKeyboardButton("🧹 پاک کردن حافظه", callback_data="clear_btn")],
            [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏠 **منوی اصلی**\n\nیک گزینه را انتخاب کنید یا سوال خود را بپرسید:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    elif query.data == "status_btn":
        await status_command(update, context)
    
    elif query.data == "clear_btn":
        user_id = str(update.effective_user.id)
        await clear_history(user_id)
        
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🧹 **حافظه‌ی مکالمه شما با موفقیت پاک شد!**",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    elif query.data == "help_btn":
        await help_command(update, context)

# ===== تابع اصلی پاسخ‌دهی =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    
    if user_message.startswith('/'):
        return
    
    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")
    
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
            model_used = result.get("model", "نامشخص")
            
            await save_message(user_id, "user", user_message)
            await save_message(user_id, "assistant", ai_reply)
            
            await processing_msg.delete()
            
            reply_with_model = f"{ai_reply}\n\n---\n🤖 **مدل:** `{model_used}`"
            await update.message.reply_text(reply_with_model, parse_mode="Markdown")
        else:
            await processing_msg.edit_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error: {e}")
        await processing_msg.edit_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")

# ===== تابع اصلی =====
def main():
    asyncio.run(init_db())
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ===== تنظیم منوی کامندها (نمایش در کنار ورودی) =====
    commands = [
        BotCommand("start", "نمایش منوی اصلی"),
        BotCommand("status", "وضعیت مدل‌های هوش مصنوعی"),
        BotCommand("clear", "پاک کردن حافظه‌ی مکالمه"),
        BotCommand("help", "راهنمای ربات")
    ]
    application.bot.set_my_commands(commands)
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات با منوی کامندها و دکمه‌های اصلاح‌شده روشن شد...")
    application.run_polling()

if __name__ == "__main__":
    main()
