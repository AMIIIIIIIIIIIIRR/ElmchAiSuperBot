from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.helpers import safe_reply

# ===== منوی اصلی =====
MAIN_MENU = [
    [InlineKeyboardButton("🤖 هوش مصنوعی", callback_data="menu_ai")],
    [InlineKeyboardButton("🎭 شخصیت", callback_data="menu_personality")],
    [InlineKeyboardButton("🧠 حافظه", callback_data="menu_memory")],
    [InlineKeyboardButton("⏰ یادآوری", callback_data="menu_reminder")],
    [InlineKeyboardButton("🌐 جستجوی اینترنت", callback_data="menu_websearch")],
    [InlineKeyboardButton("📊 اطلاعات مالی", callback_data="menu_market")],
    [InlineKeyboardButton("📊 وضعیت مدل‌ها", callback_data="menu_status")],
    [InlineKeyboardButton("❓ راهنما", callback_data="menu_help")],
]

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    text = """
🤖 **به ربات هوشمند خوش آمدید!** 🌟

من یک دستیار شخصی هستم که با استفاده از **هوش مصنوعی** به شما کمک می‌کنم.

---

### 🧠 **چه کارهایی می‌توانم انجام دهم؟**

| بخش | توضیح |
| :--- | :--- |
| 🤖 **هوش مصنوعی** | سوالات خود را بپرسید و پاسخ بگیرید |
| 🎭 **شخصیت** | لحن ربات را عوض کن (ادبی، کول، رکیک ۱۸+، جدی) |
| 🧠 **حافظه** | نکات مهم را ذخیره و بازیابی کنید |
| ⏰ **یادآوری** | یادآوری‌ها را تنظیم کنید |
| 🌐 **جستجوی اینترنت** | روشن/خاموش کردن جستجوی خودکار اینترنت |
| 📊 **وضعیت** | وضعیت مدل‌های هوش مصنوعی را ببینید |

---

💡 شخصیت انتخاب‌شده تا وقتی خودت عوضش نکنی ثابت می‌مونه.
"""
    reply_markup = InlineKeyboardMarkup(MAIN_MENU)

    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await safe_reply(update.message, text, parse_mode="Markdown", reply_markup=reply_markup)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)
