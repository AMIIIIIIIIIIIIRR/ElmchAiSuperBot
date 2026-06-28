import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_web_search_status, set_web_search_status

async def websearch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args

    if not args:
        status = await get_web_search_status(user_id)
        status_text = "🟢 **روشن**" if status else "🔴 **خاموش**"
        await update.message.reply_text(
            f"🌐 **وضعیت جستجوی خودکار اینترنت:**\n\n"
            f"{status_text}\n\n"
            f"📌 **دستورات:**\n"
            f"• `/websearch on` → روشن\n"
            f"• `/websearch off` → خاموش\n\n"
            f"💡 وقتی روشن باشد، ربات در صورت نیاز از اینترنت استفاده می‌کند."
        )
        return

    action = args[0].lower()
    if action == "on":
        await set_web_search_status(user_id, True)
        await update.message.reply_text(
            "✅ **جستجوی خودکار اینترنت روشن شد!**\n\n"
            "🌐 از این به بعد، ربات در صورت نیاز از اینترنت استفاده می‌کند."
        )
    elif action == "off":
        await set_web_search_status(user_id, False)
        await update.message.reply_text(
            "❌ **جستجوی خودکار اینترنت خاموش شد!**\n\n"
            "📚 از این به بعد، ربات فقط از دانش خودش استفاده می‌کند."
        )
    else:
        await update.message.reply_text(
            "❌ دستور نامعتبر.\n\n"
            "📌 **دستورات صحیح:**\n"
            "• `/websearch on` → روشن\n"
            "• `/websearch off` → خاموش\n"
            "• `/websearch` → نمایش وضعیت"
        )

async def websearch_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    user_id = str(update.effective_user.id)
    status = await get_web_search_status(user_id)
    status_text = "🟢 روشن" if status else "🔴 خاموش"

    keyboard = [
        [
            InlineKeyboardButton("🟢 روشن", callback_data="websearch_on"),
            InlineKeyboardButton("🔴 خاموش", callback_data="websearch_off"),
        ],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"🌐 **جستجوی خودکار اینترنت**\n\n"
        f"وضعیت فعلی: {status_text}\n\n"
        f"برای تغییر وضعیت، یکی از دکمه‌های زیر را انتخاب کنید:"
    )

    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def websearch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    data = query.data

    if data == "websearch_on":
        await set_web_search_status(user_id, True)
        await query.edit_message_text(
            "✅ **جستجوی خودکار اینترنت روشن شد!**\n\n"
            "🌐 ربات در صورت نیاز از اینترنت استفاده می‌کند."
        )
    elif data == "websearch_off":
        await set_web_search_status(user_id, False)
        await query.edit_message_text(
            "❌ **جستجوی خودکار اینترنت خاموش شد!**\n\n"
            "📚 ربات فقط از دانش خودش استفاده می‌کند."
        )
