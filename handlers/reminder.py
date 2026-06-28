from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user_reminders, delete_reminder, get_reminder_by_id
import re
import logging
from datetime import datetime, timedelta

# ===== کمکی: تبدیل زمان =====
def parse_time(text: str):
    text = text.lower().strip()
    total_seconds = 0
    patterns = [
        (r'(\d+)\s*h', 3600),
        (r'(\d+)\s*m', 60),
        (r'(\d+)\s*s', 1),
        (r'(\d+)\s*day', 86400),
        (r'(\d+)\s*week', 604800),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            total_seconds += int(match.group(1)) * multiplier
    return timedelta(seconds=total_seconds) if total_seconds > 0 else None

# ===== منوی یادآوری =====
REMINDER_MENU = [
    [InlineKeyboardButton("⏰ تنظیم یادآوری", callback_data="reminder_set")],
    [InlineKeyboardButton("📋 لیست یادآوری‌ها", callback_data="reminder_list")],
    [InlineKeyboardButton("❌ لغو یک یادآوری", callback_data="reminder_cancel")],
    [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_main")],
]

async def show_reminder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    text = """
⏰ **مدیریت یادآوری‌ها**

🔔 **این بخش به شما کمک می‌کند هیچ کاری را فراموش نکنید.**

| گزینه | توضیح |
| :--- | :--- |
| ⏰ **تنظیم یادآوری** | یک یادآوری جدید بسازید |
| 📋 **لیست یادآوری‌ها** | یادآوری‌های فعال خود را ببینید |
| ❌ **لغو یک یادآوری** | یک یادآوری را لغو کنید |

💡 **مثال:** «10min جلسه با تیم» یا «1h ناهار خوردن»
"""
    reply_markup = InlineKeyboardMarkup(REMINDER_MENU)
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== عملیات‌ها =====
async def reminder_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "reminder_text"
    await query.edit_message_text(
        "⏰ **تنظیم یادآوری**\n\n"
        "لطفاً به این شکل بنویسید:\n"
        "`10min جلسه با تیم`\n\n"
        "⏳ زمان‌های قابل استفاده:\n"
        "• `10s`, `30s` – ثانیه\n"
        "• `5min`, `30min` – دقیقه\n"
        "• `1h`, `2h30m` – ساعت و دقیقه\n"
        "• `1day`, `2days` – روز",
        parse_mode="Markdown"
    )

async def reminder_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    reminders = await get_user_reminders(user_id)
    if not reminders:
        await query.edit_message_text("📭 هیچ یادآوری فعالی ندارید.")
        return
    reply = "📋 **یادآوری‌های فعال:**\n\n"
    for r in reminders:
        remind_at = r["remind_at"].strftime("%Y-%m-%d %H:%M")
        reply += f"🆔 {r['id']} • {r['message']}\n   ⏰ {remind_at}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی یادآوری", callback_data="menu_reminder")]]
    await query.edit_message_text(reply, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def reminder_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    reminders = await get_user_reminders(user_id)
    if not reminders:
        await query.edit_message_text("📭 هیچ یادآوری فعالی برای لغو وجود ندارد.")
        return
    buttons = []
    for r in reminders:
        buttons.append([InlineKeyboardButton(f"🆔 {r['id']} • {r['message'][:20]}...", callback_data=f"cancel_rem_{r['id']}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_reminder")])
    await query.edit_message_text(
        "❌ **کدام یادآوری را لغو می‌خواهید؟**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def reminder_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    reminder_id = int(query.data.split("_")[2])
    reminder = await get_reminder_by_id(reminder_id, user_id)
    if not reminder:
        await query.edit_message_text("❌ یادآوری یافت نشد.")
        return
    job_id = reminder["job_id"]
    if job_id:
        jobs = context.job_queue.jobs()
        for job in jobs:
            if job.name == job_id:
                job.schedule_removal()
                break
    await delete_reminder(reminder_id, user_id)
    await query.edit_message_text(f"✅ یادآوری شماره {reminder_id} لغو شد.")

async def handle_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    text = update.message.text

    time_match = re.match(r'^(\d+[hms]+\s*)+', text)
    if not time_match:
        await update.message.reply_text(
            "❌ زمان را در ابتدای دستور مشخص کنید.\nمثال: `10min جلسه مهم`",
            parse_mode="Markdown"
        )
        return
    time_str = time_match.group(0)
    reminder_message = text[len(time_str):].strip()
    if not reminder_message:
        reminder_message = "⏰ یادآوری"

    delta = parse_time(time_str)
    if not delta or delta.total_seconds() < 10:
        await update.message.reply_text("❌ زمان نامعتبر است یا کمتر از ۱۰ ثانیه است.")
        return

    remind_at = datetime.now() + delta
    job_id = f"reminder_{user_id}_{int(remind_at.timestamp())}"
    reminder_id = await save_reminder(user_id, chat_id, reminder_message, remind_at, job_id)

    job = context.job_queue.run_once(
        send_reminder,
        when=delta,
        chat_id=chat_id,
        user_id=user_id,
        reminder_id=reminder_id,
        job_id=job_id,
        name=job_id,
        data={
            "reminder_id": reminder_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message": reminder_message,
            "job_id": job_id
        }
    )

    await update.message.reply_text(
        f"✅ **یادآوری ثبت شد!**\n\n"
        f"📝 {reminder_message}\n"
        f"⏰ {remind_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🆔 شماره: {reminder_id}"
    )
    context.user_data.pop("waiting_for", None)

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    message = job_data["message"]
    reminder_id = job_data["reminder_id"]

    await delete_reminder(reminder_id, user_id)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ **یادآوری!**\n\n{message}\n\n🆔 شماره: {reminder_id}"
        )
    except Exception as e:
        logging.error(f"Failed to send reminder: {e}")

# ===== توابع دیتابیس برای یادآوری (این توابع را به database.py اضافه کنید) =====
# (اگر قبلاً اضافه نکرده‌اید، این‌ها را به database.py اضافه کنید)
async def save_reminder(user_id, chat_id, message, remind_at, job_id):
    from database import db_pool
    async with db_pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO reminders (user_id, chat_id, message, remind_at, job_id) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, chat_id, message, remind_at, job_id
        )
