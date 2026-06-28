from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import safe_reply

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
    await safe_reply(update.message, help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
