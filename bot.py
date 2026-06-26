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
PORT = int(os.getenv("PORT", 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # باید در Railway تنظیم شود

if not all([TELEGRAM_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL, WEBHOOK_URL]):
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL and WEBHOOK_URL must be set")

BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")
SHORT_TERM_MEMORY = 5

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
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            user_id TEXT,
            memory TEXT,
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

async def get_recent_history(user_id: str, limit: int = SHORT_TERM_MEMORY):
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
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "DELETE FROM user_memories WHERE user_id = $1 AND memory = $2",
        user_id, memory_text
    )
    await conn.close()

# ===== دستورات =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "کاربر عزیز"
    welcome_text = f"""
🌟 **به ربات هوشمند خوش آمدید، {user_name}!** 🌟

🧠 **سیستم حافظه‌ی هوشمند:**
• 📝 **حافظه‌ی کوتاه‌مدت**: ۵ پیام آخر برای بافت مکالمه
• 💾 **حافظه‌ی بلندمدت**: ذخیره اطلاعات مهم با دستورات

📌 **دستورات حافظه:**
• `/remember [متن]` – ذخیره در حافظه‌ی بلندمدت
• `/memories` – نمایش یادداشت‌ها
• `/forget [متن]` – حذف یک یادداشت
• `/clear_memories` – پاک کردن همه‌ی یادداشت‌ها
• `/clear` – پاک کردن حافظه‌ی کوتاه‌مدت

✨ **سایر قابلیت‌ها:**
• `/status` – وضعیت مدل‌ها
• `/help` – راهنما

💡 فقط سوال خود را بپرسید!
    """
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="status_btn")],
        [InlineKeyboardButton("🧹 پاک کردن حافظه", callback_data="clear_btn")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text("❌ لطفاً متنی را برای ذخیره وارد کنید.\nمثال: `/remember نام من علی است`")
        return
    await save_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ **یادداشت ذخیره شد:**\n\n📝 {memory_text}")

async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    if not memories:
        await update.message.reply_text("📭 **هیچ یادداشتی ذخیره نشده است.**")
        return
    reply = "📚 **یادداشت‌های ذخیره‌شده:**\n\n" + "\n".join([f"{i+1}. {m}" for i, m in enumerate(memories)])
    await update.message.reply_text(reply)

async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text("❌ لطفاً متن یادداشت را برای حذف وارد کنید.\nمثال: `/forget نام من علی است`")
        return
    await delete_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ **یادداشت حذف شد:**\n\n📝 {memory_text}")

async def clear_memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_memories(user_id)
    await update.message.reply_text("🧹 **همه‌ی یادداشت‌های شما پاک شدند.**")

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
        response = requests.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"}, timeout=10)
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
            reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n" + "─" * 25 + "\n\n"
            if available:
                reply += "✅ **در دسترس:**\n" + "\n".join([f"• `{m}`" for m in available[:20]]) + "\n\n"
            if limited:
                reply += "⚠️ **محدودیت خورده:**\n" + "\n".join([f"• `{m}`" for m in limited]) + "\n\n"
            if unavailable:
                reply += "❌ **در دسترس نیست:**\n" + "\n".join([f"• `{m}`" for m in unavailable]) + "\n\n"
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

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🧹 **حافظه‌ی کوتاه‌مدت پاک شد!**\n\n💡 یادداشت‌های بلندمدت شما همچنان ذخیره شده‌اند.", parse_mode="Markdown", reply_markup=reply_markup)

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
• `/status` – وضعیت مدل‌ها
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
        await query.edit_message_text("🏠 **منوی اصلی**\n\nیک گزینه را انتخاب کنید:", parse_mode="Markdown", reply_markup=reply_markup)
    elif query.data == "status_btn":
        await status_command(update, context)
    elif query.data == "clear_btn":
        user_id = str(update.effective_user.id)
        await clear_history(user_id)
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🧹 **حافظه‌ی کوتاه‌مدت پاک شد!**", parse_mode="Markdown", reply_markup=reply_markup)
    elif query.data == "help_btn":
        await help_command(update, context)

# ===== تابع پاسخ‌دهی =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text
    if user_message.startswith('/'):
        return
    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")
    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    memories = await get_memories(user_id)
    system_prompt = f"""
شما یک دستیار هوشمند و حرفه‌ای هستید که به زبان فارسی پاسخ می‌دهید.

📌 **یادداشت‌های کاربر (اطلاعات مهم):**
{chr(10).join([f"• {m}" for m in memories]) if memories else "هیچ یادداشتی ذخیره نشده است."}

🔹 **قوانین:**
1. همیشه به فارسی پاسخ دهید.
2. از یادداشت‌های کاربر در پاسخ‌های خود استفاده کنید.
3. پاسخ‌ها باید روان، ادبی و مفید باشند.
"""
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    data = {"model": "auto", "messages": messages}
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

# ===== تابع اصلی (با Webhook و close_loop=False) =====
async def main():
    await init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
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
    
    # ===== حذف Webhook قبلی (در صورت وجود) =====
    await application.bot.delete_webhook()
    
    # ===== تنظیم Webhook جدید =====
    await application.bot.set_webhook(WEBHOOK_URL)
    
    # ===== اجرا با Webhook و غیرفعال کردن بسته شدن حلقه =====
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL,
        close_loop=False  # ← این خط اضافه شد
    )

if __name__ == "__main__":
    asyncio.run(main())
