import logging
import requests
import os
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, MessageHandler, filters, ContextTypes,
    CommandHandler, CallbackQueryHandler,
)

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not all([TELEGRAM_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL]):
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL and DATABASE_URL must be set")

BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")
SHORT_TERM_MEMORY = 5

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ===== دیتابیس (با Pool) =====
db_pool: asyncpg.Pool | None = None


async def init_db(app: Application):
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
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
    logging.info("✅ دیتابیس PostgreSQL آماده است.")


async def close_db(app: Application):
    if db_pool:
        await db_pool.close()


async def save_message(user_id: str, role: str, content: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
            user_id, role, content,
        )


async def get_recent_history(user_id: str, limit: int = SHORT_TERM_MEMORY):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM chat_history WHERE user_id = $1 "
            "ORDER BY timestamp DESC LIMIT $2",
            user_id, limit * 2,
        )
    return list(reversed(rows))


async def clear_history(user_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)


async def save_memory(user_id: str, memory: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_memories (user_id, memory) VALUES ($1, $2)",
            user_id, memory,
        )


async def get_memories(user_id: str):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT memory FROM user_memories WHERE user_id = $1 ORDER BY timestamp DESC",
            user_id,
        )
    return [row["memory"] for row in rows]


async def clear_memories(user_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM user_memories WHERE user_id = $1", user_id)


async def delete_memory(user_id: str, memory_text: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_memories WHERE user_id = $1 AND memory = $2",
            user_id, memory_text,
        )


# ===== کمکی: ارسال امن با Markdown =====
async def safe_reply(message, text, **kwargs):
    """اگر Markdown parse خطا داد، بدون parse_mode می‌فرستد."""
    try:
        await message.reply_text(text, **kwargs)
    except Exception as e:
        logging.warning(f"Markdown parse failed, retrying plain: {e}")
        kwargs.pop("parse_mode", None)
        await message.reply_text(text, **kwargs)


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
        [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")],
    ]
    await safe_reply(
        update.message, welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متنی را برای ذخیره وارد کنید.\nمثال: /remember نام من علی است"
        )
        return
    await save_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ یادداشت ذخیره شد:\n\n📝 {memory_text}")


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    if not memories:
        await update.message.reply_text("📭 هیچ یادداشتی ذخیره نشده است.")
        return
    reply = "📚 یادداشت‌های ذخیره‌شده:\n\n" + "\n".join(
        f"{i + 1}. {m}" for i, m in enumerate(memories)
    )
    await update.message.reply_text(reply)


async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متن یادداشت را برای حذف وارد کنید.\nمثال: /forget نام من علی است"
        )
        return
    await delete_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ یادداشت حذف شد:\n\n📝 {memory_text}")


async def clear_memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_memories(user_id)
    await update.message.reply_text("🧹 همه‌ی یادداشت‌های شما پاک شدند.")


async def _render_status(message_obj, edit: bool):
    """رندر وضعیت مدل‌ها روی پیام داده‌شده (edit یا reply)."""
    if edit:
        status_msg = await message_obj.edit_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    else:
        status_msg = await message_obj.reply_text("⏳ در حال دریافت وضعیت مدل‌ها...")

    try:
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"},
            timeout=10,
        )
        if response.status_code != 200:
            await status_msg.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
            return

        models = response.json().get("data", [])
        if not models:
            await status_msg.edit_text("❌ هیچ مدلی در دسترس نیست.")
            return

        available, unavailable, limited = [], [], []
        for model in models:
            model_id = model.get("id", "نامشخص")
            status = model.get("status", "unknown")
            if status in ("unavailable", "inactive"):
                unavailable.append(model_id)
            elif status in ("limited", "rate_limited"):
                limited.append(model_id)
            else:
                available.append(model_id)

        reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n" + "─" * 25 + "\n\n"
        if available:
            reply += "✅ **در دسترس:**\n" + "\n".join(f"• `{m}`" for m in available[:20]) + "\n\n"
        if limited:
            reply += "⚠️ **محدودیت خورده:**\n" + "\n".join(f"• `{m}`" for m in limited) + "\n\n"
        if unavailable:
            reply += "❌ **در دسترس نیست:**\n" + "\n".join(f"• `{m}`" for m in unavailable) + "\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_status")],
            [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")],
        ]
        try:
            await status_msg.edit_text(
                reply, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception:
            await status_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await status_msg.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        # answer قبلاً در button_handler صدا زده شده
        await _render_status(update.callback_query.message, edit=True)
    else:
        await _render_status(update.message, edit=False)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
    await update.message.reply_text(
        "🧹 حافظه‌ی کوتاه‌مدت پاک شد!\n\n💡 یادداشت‌های بلندمدت شما همچنان ذخیره شده‌اند.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


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
        try:
            await update.callback_query.edit_message_text(
                help_text, parse_mode="Markdown", reply_markup=reply_markup,
            )
        except Exception:
            await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup)
    else:
        await safe_reply(update.message, help_text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ("refresh_status", "status_btn"):
        await status_command(update, context)
    elif data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="status_btn")],
            [InlineKeyboardButton("🧹 پاک کردن حافظه", callback_data="clear_btn")],
            [InlineKeyboardButton("📖 راهنما", callback_data="help_btn")],
        ]
        await query.edit_message_text(
            "🏠 **منوی اصلی**\n\nیک گزینه را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data == "clear_btn":
        user_id = str(update.effective_user.id)
        await clear_history(user_id)
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "🧹 حافظه‌ی کوتاه‌مدت پاک شد!",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif data == "help_btn":
        await help_command(update, context)


# ===== تابع پاسخ‌دهی =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text or ""
    if user_message.startswith("/"):
        return

    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")
    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    memories = await get_memories(user_id)
    system_prompt = f"""
شما یک دستیار هوشمند و حرفه‌ای هستید که به زبان فارسی پاسخ می‌دهید.

📌 **یادداشت‌های کاربر (اطلاعات مهم):**
{chr(10).join(f"• {m}" for m in memories) if memories else "هیچ یادداشتی ذخیره نشده است."}

🔹 **قوانین:**
1. همیشه به فارسی پاسخ دهید.
2. از یادداشت‌های کاربر در پاسخ‌های خود استفاده کنید.
3. پاسخ‌ها باید روان، ادبی و مفید باشند.
"""
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {FREELLMAPI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": "auto", "messages": messages}

    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            await processing_msg.edit_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
            return

        ai_reply = choices[0]["message"]["content"]
        model_used = result.get("model", "نامشخص")
        await save_message(user_id, "user", user_message)
        await save_message(user_id, "assistant", ai_reply)
        await processing_msg.delete()

        full_reply = f"{ai_reply}\n\n---\n🤖 مدل: {model_used}"
        # بدون parse_mode تا کاراکترهای ناقص از طرف AI باعث خطا نشن
        await update.message.reply_text(full_reply)
    except requests.exceptions.RequestException as e:
        logging.error(f"AI request error: {e}")
        try:
            await processing_msg.edit_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")
        except Exception:
            pass
    except Exception as e:
        logging.exception(f"Unexpected error in handle_message: {e}")
        try:
            await processing_msg.edit_text(f"❌ خطای غیرمنتظره: {str(e)[:100]}")
        except Exception:
            pass


# ===== post_init: ثبت دستورات بعد از init =====
async def post_init(application: Application):
    await init_db(application)
    commands = [
        BotCommand("start", "نمایش منوی اصلی"),
        BotCommand("remember", "ذخیره یک نکته در حافظه‌ی بلندمدت"),
        BotCommand("memories", "نمایش یادداشت‌های ذخیره‌شده"),
        BotCommand("forget", "حذف یک یادداشت"),
        BotCommand("clear_memories", "پاک کردن همه‌ی یادداشت‌ها"),
        BotCommand("clear", "پاک کردن حافظه‌ی کوتاه‌مدت"),
        BotCommand("status", "وضعیت مدل‌های هوش مصنوعی"),
        BotCommand("help", "راهنمای ربات"),
    ]
    await application.bot.set_my_commands(commands)


# ===== تابع اصلی (SYNC، نه async) =====
def main():
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(close_db)
        .build()
    )

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
    # run_polling خودش loop رو می‌سازه و مدیریت می‌کنه
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
