from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import safe_reply

# ===== منوی اصلی =====
MAIN_MENU = [
    [InlineKeyboardButton("🤖 هوش مصنوعی", callback_data="menu_ai")],
    [InlineKeyboardButton("🧠 حافظه", callback_data="menu_memory")],
    [InlineKeyboardButton("⏰ یادآوری", callback_data="menu_reminder")],
    [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="menu_status")],
    [InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
]

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    """نمایش منوی اصلی با توضیح کامل ربات"""
    text = """
🤖 **به ربات هوشمند خوش آمدید!** 🌟

من یک دستیار شخصی هستم که با استفاده از **هوش مصنوعی** به شما کمک می‌کنم.

---

### 🧠 **چه کارهایی می‌توانم انجام دهم؟**

| بخش | توضیح |
| :--- | :--- |
| 🤖 **هوش مصنوعی** | سوالات خود را بپرسید و پاسخ بگیرید |
| 🧠 **حافظه** | نکات مهم را ذخیره کنید و هر زمان نیاز داشتید، بازیابی کنید |
| ⏰ **یادآوری** | یادآوری‌های خود را تنظیم کنید و سر وقت دریافت کنید |
| 📊 **وضعیت** | وضعیت مدل‌های هوش مصنوعی را ببینید |

---

### 💡 **چگونه شروع کنم؟**

1️⃣ روی یکی از دکمه‌های زیر کلیک کنید.  
2️⃣ در هر بخش، دستورالعمل‌های مربوطه را دنبال کنید.  
3️⃣ برای بازگشت به این منو، همیشه دکمه‌ی **🔙 بازگشت** وجود دارد.

---

📌 **نکته:** من اطلاعات شما را در یک پایگاه داده امن ذخیره می‌کنم و فقط خودتان به آن دسترسی دارید.

✨ **پیشنهاد:** با دکمه‌ی **🧠 حافظه** شروع کنید و اولین یادداشت خود را ذخیره کنید!
"""
    reply_markup = InlineKeyboardMarkup(MAIN_MENU)
    
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await safe_reply(update.message, text, parse_mode="Markdown", reply_markup=reply_markup)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start – نمایش منوی اصلی با توضیح کامل"""
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /help – نمایش منوی اصلی یا راهنما"""
    await show_main_menu(update, context)
