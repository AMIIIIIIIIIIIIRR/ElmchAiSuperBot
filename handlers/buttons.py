from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.memory import clear_history_command
from handlers.ai import status_command
from handlers.base import help_command

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
        await clear_history_command(update, context)
    elif data == "help_btn":
        await help_command(update, context)
