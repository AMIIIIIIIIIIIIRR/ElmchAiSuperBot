from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user_reminders, delete_reminder, get_reminder_by_id, save_reminder
import logging
from datetime import datetime, timedelta
import jdatetime

# ===== منوی یادآوری =====
REMINDER_MENU = [
    [InlineKeyboardButton("📅 تنظیم یادآوری جدید", callback_data="reminder_new")],
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
| 📅 **تنظیم یادآوری جدید** | با تقویم شمسی تاریخ و ساعت را انتخاب کنید |
| 📋 **لیست یادآوری‌ها** | یادآوری‌های فعال خود را ببینید |
| ❌ **لغو یک یادآوری** | یک یادآوری را لغو کنید |

💡 **با انتخاب گزینه اول، یک تقویم شمسی باز می‌شود.**
"""
    reply_markup = InlineKeyboardMarkup(REMINDER_MENU)
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== توابع کمکی =====
def jalali_to_gregorian(year, month, day, hour=0, minute=0):
    jalali_date = jdatetime.date(year, month, day)
    gregorian_date = jalali_date.togregorian()
    return datetime(gregorian_date.year, gregorian_date.month, gregorian_date.day, hour, minute)

def get_current_jalali():
    now = jdatetime.datetime.now()
    return now.year, now.month, now.day, now.hour, now.minute

def get_days_in_jalali_month(year, month):
    try:
        if month == 12:
            next_month = jdatetime.date(year + 1, 1, 1)
        else:
            next_month = jdatetime.date(year, month + 1, 1)
        last_day = next_month - timedelta(days=1)
        return last_day.day
    except:
        return 30

def format_jalali_date(year, month, day):
    month_names = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                   "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{day} {month_names[month-1]} {year}"

def format_jalali_datetime(year, month, day, hour, minute):
    return f"{format_jalali_date(year, month, day)} - {hour:02d}:{minute:02d}"

def is_future_date(year, month, day, hour=0, minute=0):
    try:
        jalali_date = jdatetime.date(year, month, day)
        gregorian_date = jalali_date.togregorian()
        selected_dt = datetime(gregorian_date.year, gregorian_date.month, gregorian_date.day, hour, minute)
        return selected_dt > datetime.now()
    except:
        return False

def get_next_days(count=30):
    """دریافت تاریخ شمسی روزهای آینده به همراه سال و ماه و روز"""
    result = []
    current_jalali = jdatetime.datetime.now()
    for i in range(count):
        future_date = current_jalali + timedelta(days=i)
        result.append((future_date.year, future_date.month, future_date.day))
    return result

# ===== شروع تنظیم یادآوری (ورود مستقیم به انتخاب روز) =====
async def reminder_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if "reminder_data" not in context.user_data:
        context.user_data["reminder_data"] = {}
    
    context.user_data["reminder_step"] = "day"
    await show_day_selection(update, context, edit=True)

# ===== انتخاب روز (نمایش ۳۰ روز آینده) =====
async def show_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    days = get_next_days(30)
    current_year, current_month, current_day, _, _ = get_current_jalali()
    
    buttons = []
    for year, month, day in days:
        # اگر روز جاری است، با علامت ✅ مشخص شود
        label = format_jalali_date(year, month, day)
        if year == current_year and month == current_month and day == current_day:
            label += " ✅"
        buttons.append(InlineKeyboardButton(label, callback_data=f"rem_day_{year}_{month}_{day}"))
    
    # دکمه‌ها در ردیف‌های ۳ تایی
    keyboard = []
    for i in range(0, len(buttons), 3):
        keyboard.append(buttons[i:i+3])
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="menu_reminder")])
    
    text = """
📅 **مرحله ۱: انتخاب روز**

لطفاً روز مورد نظر را انتخاب کنید:
"""
    reply_markup = InlineKeyboardMarkup(keyboard)
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== انتخاب ساعت =====
async def show_hour_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    data = context.user_data["reminder_data"]
    year = data.get("year")
    month = data.get("month")
    day = data.get("day")
    
    if not year or not month or not day:
        await update.callback_query.edit_message_text("❌ خطا در دریافت تاریخ. لطفاً دوباره تلاش کنید.")
        return
    
    current_year, current_month, current_day, current_hour, _ = get_current_jalali()
    
    buttons = []
    for hour in range(0, 24):
        if year == current_year and month == current_month and day == current_day and hour < current_hour:
            label = f"{hour:02d} ❌"
            callback = "noop"
        else:
            label = f"{hour:02d}"
            callback = f"rem_hour_{hour}"
        buttons.append(InlineKeyboardButton(label, callback_data=callback))
    
    keyboard = []
    for i in range(0, len(buttons), 6):
        keyboard.append(buttons[i:i+6])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به روز", callback_data="rem_back_day")])
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="menu_reminder")])
    
    text = f"""
🕐 **مرحله ۲: انتخاب ساعت**

تاریخ انتخاب‌شده: {format_jalali_date(year, month, day)}
لطفاً ساعت مورد نظر را انتخاب کنید:
"""
    reply_markup = InlineKeyboardMarkup(keyboard)
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== انتخاب دقیقه (پله‌های ۵ دقیقه‌ای) =====
async def show_minute_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    data = context.user_data["reminder_data"]
    year = data.get("year")
    month = data.get("month")
    day = data.get("day")
    hour = data.get("hour")
    
    current_year, current_month, current_day, current_hour, current_minute = get_current_jalali()
    
    buttons = []
    for minute in range(0, 60, 5):
        if (year == current_year and month == current_month and day == current_day and 
            hour == current_hour and minute < current_minute):
            label = f"{minute:02d} ❌"
            callback = "noop"
        else:
            label = f"{minute:02d}"
            callback = f"rem_minute_{minute}"
        buttons.append(InlineKeyboardButton(label, callback_data=callback))
    
    keyboard = []
    for i in range(0, len(buttons), 6):
        keyboard.append(buttons[i:i+6])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به ساعت", callback_data="rem_back_hour")])
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="menu_reminder")])
    
    text = f"""
🕐 **مرحله ۳: انتخاب دقیقه**

تاریخ: {format_jalali_date(year, month, day)} - ساعت: {hour:02d}
لطفاً دقیقه مورد نظر را انتخاب کنید (پله‌های ۵ دقیقه‌ای):
"""
    reply_markup = InlineKeyboardMarkup(keyboard)
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== مرحله تأیید و دریافت متن =====
async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    data = context.user_data["reminder_data"]
    year = data.get("year")
    month = data.get("month")
    day = data.get("day")
    hour = data.get("hour")
    minute = data.get("minute")
    
    if not year or not month or not day or hour is None or minute is None:
        await update.callback_query.edit_message_text("❌ خطا در دریافت تاریخ. لطفاً دوباره تلاش کنید.")
        return
    
    if not is_future_date(year, month, day, hour, minute):
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به دقیقه", callback_data="rem_back_minute")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "❌ **تاریخ انتخاب‌شده گذشته است!**\n\n"
            f"تاریخ انتخاب‌شده: {format_jalali_datetime(year, month, day, hour, minute)}\n\n"
            "لطفاً یک زمان آینده انتخاب کنید.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return
    
    remind_at = jalali_to_gregorian(year, month, day, hour, minute)
    
    text = f"""
✅ **مرحله آخر: تأیید و وارد کردن متن**

📅 تاریخ و زمان انتخاب‌شده:
{format_jalali_datetime(year, month, day, hour, minute)}

📆 میلادی: {remind_at.strftime('%Y-%m-%d %H:%M')}

📝 **لطفاً متن یادآوری را بنویسید:**
"""
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت به دقیقه", callback_data="rem_back_minute")],
        [InlineKeyboardButton("❌ انصراف", callback_data="menu_reminder")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data["waiting_for"] = "reminder_text"
    
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== مدیریت دکمه‌های تقویم =====
async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # ===== انتخاب روز =====
    if data.startswith("rem_day_"):
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        
        context.user_data["reminder_data"]["year"] = year
        context.user_data["reminder_data"]["month"] = month
        context.user_data["reminder_data"]["day"] = day
        context.user_data["reminder_step"] = "hour"
        await show_hour_selection(update, context, edit=True)
    
    elif data == "rem_back_day":
        context.user_data["reminder_step"] = "day"
        await show_day_selection(update, context, edit=True)
    
    # ===== انتخاب ساعت =====
    elif data.startswith("rem_hour_"):
        hour = int(data.split("_")[2])
        context.user_data["reminder_data"]["hour"] = hour
        context.user_data["reminder_step"] = "minute"
        await show_minute_selection(update, context, edit=True)
    
    elif data == "rem_back_hour":
        context.user_data["reminder_step"] = "hour"
        await show_hour_selection(update, context, edit=True)
    
    # ===== انتخاب دقیقه =====
    elif data.startswith("rem_minute_"):
        minute = int(data.split("_")[2])
        context.user_data["reminder_data"]["minute"] = minute
        context.user_data["reminder_step"] = "confirm"
        await show_confirmation(update, context, edit=True)
    
    elif data == "rem_back_minute":
        context.user_data["reminder_step"] = "minute"
        await show_minute_selection(update, context, edit=True)
    
    elif data == "noop":
        pass

# ===== دریافت متن یادآوری =====
async def handle_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()
    
    if not text:
        await update.message.reply_text("❌ متن نمی‌تواند خالی باشد. لطفاً دوباره بنویسید.")
        context.user_data.pop("waiting_for", None)
        return
    
    data_dict = context.user_data.get("reminder_data", {})
    year = data_dict.get("year")
    month = data_dict.get("month")
    day = data_dict.get("day")
    hour = data_dict.get("hour", 0)
    minute = data_dict.get("minute", 0)
    
    if not year or not month or not day:
        await update.message.reply_text("❌ خطا در دریافت تاریخ. لطفاً دوباره تلاش کنید.")
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("reminder_data", None)
        return
    
    if not is_future_date(year, month, day, hour, minute):
        await update.message.reply_text(
            "❌ **تاریخ انتخاب‌شده گذشته است!**\n\n"
            f"تاریخ انتخاب‌شده: {format_jalali_datetime(year, month, day, hour, minute)}\n\n"
            "لطفاً دوباره تلاش کنید."
        )
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("reminder_data", None)
        return
    
    remind_at = jalali_to_gregorian(year, month, day, hour, minute)
    now = datetime.now()
    
    job_id = f"reminder_{user_id}_{int(remind_at.timestamp())}"
    reminder_id = await save_reminder(user_id, chat_id, text, remind_at, job_id)
    
    delta = remind_at - now
    context.job_queue.run_once(
        send_reminder,
        when=delta,
        name=job_id,
        data={
            "reminder_id": reminder_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message": text,
            "job_id": job_id
        }
    )
    
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("reminder_data", None)
    context.user_data.pop("reminder_step", None)
    
    await update.message.reply_text(
        f"✅ **یادآوری ثبت شد!**\n\n"
        f"📝 {text}\n"
        f"⏰ {remind_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🆔 شماره: {reminder_id}"
    )

# ===== سایر توابع (لیست، لغو، ارسال) =====
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
