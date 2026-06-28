from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user_reminders, delete_reminder, get_reminder_by_id, save_reminder
import logging
from datetime import datetime, timedelta
import jdatetime

# ===== وضعیت‌های کاربر برای تقویم =====
class ReminderState:
    SELECTING_YEAR = "selecting_year"
    SELECTING_MONTH = "selecting_month"
    SELECTING_DAY = "selecting_day"
    SELECTING_HOUR = "selecting_hour"
    SELECTING_MINUTE = "selecting_minute"
    CONFIRMING = "confirming"
    ENTERING_TEXT = "entering_text"

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

# ===== توابع کمکی تقویم =====
def jalali_to_gregorian(year, month, day, hour=0, minute=0):
    """تبدیل تاریخ شمسی به میلادی"""
    jalali_date = jdatetime.date(year, month, day)
    gregorian_date = jalali_date.togregorian()
    return datetime(gregorian_date.year, gregorian_date.month, gregorian_date.day, hour, minute)

def get_current_jalali():
    """دریافت تاریخ شمسی فعلی"""
    now = jdatetime.datetime.now()
    return now.year, now.month, now.day, now.hour, now.minute

def build_calendar_keyboard(year, month, day, hour, minute):
    """ساخت دکمه‌های تقویم با مقادیر فعلی"""
    # دکمه‌های انتخاب سال
    year_buttons = [
        InlineKeyboardButton(f"📆 سال: {year}", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cal_inc_year"),
        InlineKeyboardButton("➖", callback_data=f"cal_dec_year"),
    ]
    
    # دکمه‌های انتخاب ماه
    month_names = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                   "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    month_buttons = [
        InlineKeyboardButton(f"📆 ماه: {month_names[month-1]}", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cal_inc_month"),
        InlineKeyboardButton("➖", callback_data=f"cal_dec_month"),
    ]
    
    # دکمه‌های انتخاب روز
    day_buttons = [
        InlineKeyboardButton(f"📆 روز: {day}", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cal_inc_day"),
        InlineKeyboardButton("➖", callback_data=f"cal_dec_day"),
    ]
    
    # دکمه‌های انتخاب ساعت
    hour_buttons = [
        InlineKeyboardButton(f"🕐 ساعت: {hour:02d}", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cal_inc_hour"),
        InlineKeyboardButton("➖", callback_data=f"cal_dec_hour"),
    ]
    
    # دکمه‌های انتخاب دقیقه
    minute_buttons = [
        InlineKeyboardButton(f"🕐 دقیقه: {minute:02d}", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"cal_inc_minute"),
        InlineKeyboardButton("➖", callback_data=f"cal_dec_minute"),
    ]
    
    # دکمه‌های اقدام
    action_buttons = [
        InlineKeyboardButton("✅ ثبت یادآوری", callback_data="cal_confirm"),
        InlineKeyboardButton("❌ انصراف", callback_data="menu_reminder"),
    ]
    
    keyboard = [
        year_buttons,
        month_buttons,
        day_buttons,
        hour_buttons,
        minute_buttons,
        action_buttons,
    ]
    return InlineKeyboardMarkup(keyboard)

def get_days_in_jalali_month(year, month):
    """تعداد روزهای یک ماه شمسی"""
    if month <= 6:
        return 31
    elif month <= 11:
        return 30
    else:
        # سال کبیسه شمسی
        # کبیسه‌های شمسی: سال‌هایی که بر ۴ بخش‌پذیر هستند، اما سال‌های ۳۳ ساله استثنا دارند
        # استفاده از کتابخانه jdatetime برای دقت بیشتر
        try:
            # ایجاد تاریخ ۱ ماه بعد و تفریق یک روز
            if month == 12:
                next_month = jdatetime.date(year + 1, 1, 1)
            else:
                next_month = jdatetime.date(year, month + 1, 1)
            last_day = next_month - timedelta(days=1)
            return last_day.day
        except:
            return 30

def validate_date(year, month, day):
    """بررسی معتبر بودن تاریخ شمسی"""
    try:
        jdatetime.date(year, month, day)
        return True
    except:
        return False

def format_jalali_datetime(year, month, day, hour, minute):
    """فرمت‌دهی تاریخ شمسی برای نمایش"""
    month_names = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                   "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{day} {month_names[month-1]} {year} - {hour:02d}:{minute:02d}"

# ===== شروع تنظیم یادآوری جدید =====
async def reminder_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    # تنظیم مقادیر پیش‌فرض به تاریخ و زمان فعلی
    year, month, day, hour, minute = get_current_jalali()
    
    # ذخیره در context.user_data برای هر کاربر
    if "reminder_data" not in context.user_data:
        context.user_data["reminder_data"] = {}
    context.user_data["reminder_data"]["year"] = year
    context.user_data["reminder_data"]["month"] = month
    context.user_data["reminder_data"]["day"] = day
    context.user_data["reminder_data"]["hour"] = hour
    context.user_data["reminder_data"]["minute"] = minute
    
    text = f"""
📅 **تنظیم یادآوری با تقویم شمسی**

⏰ تاریخ و زمان انتخاب‌شده:
{format_jalali_datetime(year, month, day, hour, minute)}

🔹 با دکمه‌های ➕ و ➖ مقدار هر بخش را تغییر دهید.
🔹 بعد از تنظیم، روی **✅ ثبت یادآوری** کلیک کنید.

📌 **سپس متن یادآوری را وارد کنید.**
"""
    reply_markup = build_calendar_keyboard(year, month, day, hour, minute)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== مدیریت دکمه‌های تقویم =====
async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    user_id = str(update.effective_user.id)
    if "reminder_data" not in context.user_data:
        context.user_data["reminder_data"] = {}
    
    data_dict = context.user_data["reminder_data"]
    year = data_dict.get("year", 1400)
    month = data_dict.get("month", 1)
    day = data_dict.get("day", 1)
    hour = data_dict.get("hour", 0)
    minute = data_dict.get("minute", 0)
    
    changed = False
    
    if data == "cal_inc_year":
        year += 1
        changed = True
    elif data == "cal_dec_year":
        year -= 1
        changed = True
    elif data == "cal_inc_month":
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        changed = True
    elif data == "cal_dec_month":
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
        changed = True
    elif data == "cal_inc_day":
        max_day = get_days_in_jalali_month(year, month)
        if day < max_day:
            day += 1
        else:
            day = 1
        changed = True
    elif data == "cal_dec_day":
        if day > 1:
            day -= 1
        else:
            max_day = get_days_in_jalali_month(year, month)
            day = max_day
        changed = True
    elif data == "cal_inc_hour":
        hour = (hour + 1) % 24
        changed = True
    elif data == "cal_dec_hour":
        hour = (hour - 1) % 24
        changed = True
    elif data == "cal_inc_minute":
        minute = (minute + 1) % 60
        changed = True
    elif data == "cal_dec_minute":
        minute = (minute - 1) % 60
        changed = True
    elif data == "cal_confirm":
        # ذخیره زمان و رفتن به مرحله دریافت متن
        context.user_data["waiting_for"] = "reminder_text"
        context.user_data["reminder_data"]["year"] = year
        context.user_data["reminder_data"]["month"] = month
        context.user_data["reminder_data"]["day"] = day
        context.user_data["reminder_data"]["hour"] = hour
        context.user_data["reminder_data"]["minute"] = minute
        
        await query.edit_message_text(
            f"✅ **زمان انتخاب شد:**\n{format_jalali_datetime(year, month, day, hour, minute)}\n\n"
            "📝 **لطفاً متن یادآوری را بنویسید:**"
        )
        return
    else:
        # noop یا نامعتبر
        await query.answer()
        return
    
    if changed:
        # اعتبارسنجی تاریخ
        if not validate_date(year, month, day):
            # برگرداندن به مقادیر معتبر
            year, month, day, hour, minute = get_current_jalali()
            data_dict["year"] = year
            data_dict["month"] = month
            data_dict["day"] = day
            data_dict["hour"] = hour
            data_dict["minute"] = minute
            await query.edit_message_text(
                "❌ تاریخ نامعتبر است! به تاریخ فعلی برگشتیم.",
                reply_markup=build_calendar_keyboard(year, month, day, hour, minute)
            )
            return
        
        data_dict["year"] = year
        data_dict["month"] = month
        data_dict["day"] = day
        data_dict["hour"] = hour
        data_dict["minute"] = minute
        
        text = f"""
📅 **تنظیم یادآوری با تقویم شمسی**

⏰ تاریخ و زمان انتخاب‌شده:
{format_jalali_datetime(year, month, day, hour, minute)}

🔹 با دکمه‌های ➕ و ➖ مقدار هر بخش را تغییر دهید.
🔹 بعد از تنظیم، روی **✅ ثبت یادآوری** کلیک کنید.

📌 **سپس متن یادآوری را وارد کنید.**
"""
        reply_markup = build_calendar_keyboard(year, month, day, hour, minute)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== دریافت متن یادآوری =====
async def handle_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()
    
    if not text:
        await update.message.reply_text("❌ متن نمی‌تواند خالی باشد. لطفاً دوباره بنویسید.")
        return
    
    # دریافت زمان از context
    data_dict = context.user_data.get("reminder_data", {})
    year = data_dict.get("year")
    month = data_dict.get("month")
    day = data_dict.get("day")
    hour = data_dict.get("hour", 0)
    minute = data_dict.get("minute", 0)
    
    if not year or not month or not day:
        await update.message.reply_text("❌ خطا در دریافت تاریخ. لطفاً دوباره تلاش کنید.")
        context.user_data.pop("waiting_for", None)
        return
    
    # تبدیل به میلادی
    remind_at = jalali_to_gregorian(year, month, day, hour, minute)
    
    # بررسی اینکه زمان آینده باشد
    now = datetime.now()
    if remind_at <= now:
        await update.message.reply_text(
            "⏰ **زمان وارد شده گذشته است!**\n\n"
            f"زمان فعلی: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"زمان انتخاب‌شده: {remind_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            "لطفاً یک زمان آینده انتخاب کنید."
        )
        return
    
    # ذخیره در دیتابیس
    job_id = f"reminder_{user_id}_{int(remind_at.timestamp())}"
    reminder_id = await save_reminder(user_id, chat_id, text, remind_at, job_id)
    
    # ثبت در JobQueue
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
    
    # پاک کردن وضعیت
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("reminder_data", None)
    
    # نمایش پیام موفقیت
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
