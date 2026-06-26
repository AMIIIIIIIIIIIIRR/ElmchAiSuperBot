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

# ===== تنظیمات حافظه =====
SHORT_TERM_MEMORY = 5  # فقط ۵ پیام آخر برای بافت مکالمه

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ===== دیتابیس =====
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    # جدول تاریخچه‌ی مکالمه (کوتاه‌مدت)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # ===== جدول جدید: یادداشت‌های بلندمدت کاربر =====
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            user_id TEXT,
            memory TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.close()
    logging.info("✅ دیتابیس PostgreSQL آماده است.")

# ===== توابع تاریخچه (کوتاه‌مدت) =====
async def save_message(user_id: str, role: str, content: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
        user_id, role, content
    )
    await conn.close()

async def get_recent_history(user_id: str, limit: int = SHORT_TERM_MEMORY):
    """دریافت ۵ پیام آخر برای بافت مکالمه"""
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT role, content FROM chat_history WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
        user_id, limit * 2  # چون هر مکالمه ۲ پیام دارد
    )
    await conn.close()
    return list(reversed(rows))

async def clear_history(user_id: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)
    await conn.close()

# ===== توابع حافظه‌ی بلندمدت (یادداشت‌ها) =====
async def save_memory(user_id: str, memory: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO user_memories (user_id, memory) VALUES ($1, $2)",
        user_id, memory
    )
    await conn.close()

async def get_memories(user_id: str):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT memory FROM user_memories WHERE user_id = $1 ORDER BY timestamp DESC",
        user_id
    )
    await conn.close()
    return [row["memory"] for row in rows]

async def clear_memories(user_id: str):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM user_memories WHERE user_id = $1", user_id)
    await conn.close()

async def delete_memory(user_id: str, memory_text: str):
    """حذف یک یادداشت خاص"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "DELETE FROM user_memories WHERE user_id = $1 AND memory = $2",
        user_id, memory_text
    )
    await conn.close()

# ===== دستور /start =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "کاربر عزیز"
    
    welcome_text = f"""
🌟 **به ربات هوشمند خوش آمدید، {user_name}!** 🌟

🧠 **سیستم حافظه‌ی هوشمند:**
• 📝 **حافظه‌ی کوتاه‌مدت**: ۵ پیام آخر را برای بافت مکالمه نگه می‌دارم
• 💾 **حافظه‌ی بلندمدت**: اطلاعات مهم را با دستورات زیر ذخیره می‌کنم

📌 **دستورات حافظه:**
• `/remember [متن]` – یک نکته را در حافظه‌ی بلندمدت ذخیره کن
• `/memories` – نمایش همه‌ی یادداشت‌های ذخیره‌شده
• `/forget [متن]` – یک یادداشت خاص را حذف کن
• `/clear_memories` – پاک کردن همه‌ی یادداشت‌ها
• `/clear` – پاک کردن حافظه‌ی کوتاه‌مدت (مکالمه)

✨ **سایر قابلیت‌ها:**
• 📊 نمایش وضعیت مدل‌ها با `/status`
• 🤖 نمایش نام مدل پاسخ‌دهنده در انتهای هر پیام

💡 فقط سوال خود را بپرسید!
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="status_btn")],
        [InlineKeyboardButton("🧹 پاک کردن حافظه", callback_data="clear_btn")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== دستور /remember =====
async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متنی را که می‌خواهید ذخیره کنم بنویسید.\n"
            "مثال: `/remember نام من علی است`"
        )
        return
    
    await save_memory(user_id, memory_text)
    await update.message.reply_text(
        f"✅ **یادداشت ذخیره شد:**\n\n"
        f"📝 {memory_text}\n\n"
        f"💡 این نکته را همیشه در پاسخ‌هایم در نظر می‌گیرم."
    )

# ===== دستور /memories =====
async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    
    if not memories:
        await update.message.reply_text(
            "📭 **هیچ یادداشتی ذخیره نشده است.**\n\n"
            "با دستور `/remember` می‌توانید نکات مهم را به من بگویید."
        )
        return
    
    reply = "📚 **یادداشت‌های ذخیره‌شده:**\n\n"
    for i, memory in enumerate(memories, 1):
        reply += f"{i}. {memory}\n"
    
    await update.message.reply_text(reply)

# ===== دستور /forget =====
async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متنی که می‌خواهید حذف کنید را بنویسید.\n"
            "مثال: `/forget نام من علی است`"
        )
        return
    
    await delete_memory(user_id, memory_text)
    await update.message.reply_text(
        f"✅ **یادداشت حذف شد:**\n\n"
        f"📝 {memory_text}"
    )

# ===== دستور /clear_memories =====
async def clear_memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_memories(user_id)
    await update.message.reply_text("🧹 **همه‌ی یادداشت‌های شما پاک شدند.**")

# ===== دستور /status =====
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        is_callback = True
    else:
        message = update.message
        is_callback = False
    
    if is_callback:
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

# ===== دستور /clear (پاک کردن تاریخچه‌ی کوتاه‌مدت) =====
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🧹 **حافظه‌ی کوتاه‌مدت پاک شد!**\n\n"
        "💡 یادداشت‌های بلندمدت شما همچنان ذخیره شده‌اند.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ===== دستور /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **راهنمای ربات**

🧠 **سیستم حافظه‌ی هوشمند:**

🔹 **حافظه‌ی کوتاه‌مدت (۵ پیام آخر)**
• برای بافت مکالمه استفاده می‌شود
• با دستور `/clear` پاک می‌شود

🔹 **حافظه‌ی بلندمدت (یادداشت‌ها)**
• `/remember [متن]` – ذخیره یک نکته
• `/memories` – نمایش همه‌ی یادداشت‌ها
• `/forget [متن]` – حذف یک یادداشت
• `/clear_memories` – پاک کردن همه‌ی یادداشت‌ها

🔹 **سایر دستورات:**
• `/start` – منوی اصلی
• `/status` – وضعیت مدل‌های هوش مصنوعی
• `/help` – این راهنما

💡 فقط سوال خود را بپرسید!
    """
    
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== مدیریت دکمه‌ها =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh_status":
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
            "🧹 **حافظه‌ی کوتاه‌مدت پاک شد!**\n\n💡 یادداشت‌های بلندمدت شما همچنان ذخیره شده‌اند.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    elif query.data == "help_btn":
        await help_command(update, context)

# ===== تابع اصلی پاسخ‌دهی با حافظه‌ی ترکیبی =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    
    if user_message.startswith('/'):
        return
    
    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")
    
    # ===== دریافت ۵ پیام آخر (حافظه‌ی کوتاه‌مدت) =====
    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    
    # ===== دریافت یادداشت‌های بلندمدت =====
    memories = await get_memories(user_id)
    
    # ===== ساخت لیست پیام‌ها با سیستم پرامپت =====
    system_prompt = f"""
شما یک دستیار هوشمند و حرفه‌ای هستید که به زبان فارسی پاسخ می‌دهید.

📌 **یادداشت‌های کاربر (اطلاعات مهم):**
{f"{chr(10)}".join([f"• {m}" for m in memories]) if memories else "هیچ یادداشتی ذخیره نشده است."}

🔹 **قوانین:**
1. همیشه به فارسی پاسخ دهید.
2. از یادداشت‌های کاربر در پاسخ‌های خود استفاده کنید.
3. اگر کاربر سوالی درباره‌ی اطلاعات شخصی خود پرسید، از یادداشت‌ها استفاده کنید.
4. پاسخ‌ها باید روان، ادبی و مفید باشند.
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # اضافه کردن ۵ پیام آخر (حافظه‌ی کوتاه‌مدت)
    for role, content in history:
        messages.append({"role": role, "content": content})
    
    # اضافه کردن پیام جدید کاربر
    messages.append({"role": "user", "content": user_message})
    
    # ===== ارسال به FreeLLMAPI =====
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
            
            # ذخیره در تاریخچه (برای ۵ پیام آخر بعدی)
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

# ===== تابع اصلی (اصلاح‌شده) =====
async def main():
    """تابع اصلی ناهمگام (async) برای راه‌اندازی ربات"""
    # مقداردهی اولیه دیتابیس
    await init_db()
    
    # ساخت اپلیکیشن
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ===== تنظیم منوی کامندها (با await) =====
    commands = [
        BotCommand("start", "نمایش منوی اصلی"),
        BotCommand("remember", "ذخیره یک نکته در حافظه‌ی بلندمدت"),
        BotCommand("memories", "نمایش یادداشت‌های ذخیره‌شده"),
        BotCommand("forget", "حذف یک یادداشت"),
        BotCommand("clear_memories", "پاک کردن همه‌ی یادداشت‌ها"),
        BotCommand("clear", "پاک کردن حافظه‌ی کوتاه‌مدت"),
        BotCommand("status", "وضعیت مدل‌های هوش مصنوعی"),
        BotCommand("help", "راهنمای ربات")
    ]
    await application.bot.set_my_commands(commands)
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(CommandHandler("clear_memories", clear_memories_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات با حافظه‌ی ترکیبی (۵ پیام + یادداشت‌ها) روشن شد...")
    
    # اجرای ربات با Polling (await)
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
