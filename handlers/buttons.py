from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.base import show_main_menu
from handlers.memory import show_memory_menu, memory_save, memory_view, memory_delete, memory_delete_confirm, memory_clear, memory_clear_confirm
from handlers.reminder import show_reminder_menu, reminder_set, reminder_list, reminder_cancel, reminder_cancel_confirm
from handlers.ai import status_command
from handlers.base import help_command  # یا همان show_main_menu

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ===== منوی اصلی =====
    if data == "back_main":
        await show_main_menu(update, context, edit=True)

    elif data == "menu_ai":
        await query.edit_message_text(
            "🤖 **حالت هوش مصنوعی**\n\n"
            "🎯 هر سوالی دارید، از من بپرسید.\n"
            "من با استفاده از مدل‌های پیشرفته هوش مصنوعی به شما پاسخ می‌دهم.\n\n"
            "📌 **نکات:**\n"
            "• برای پرسیدن سوال، فقط پیام خود را بنویسید.\n"
            "• من تاریخچه‌ی مکالمه را به خاطر می‌سپارم.\n"
            "• برای بازگشت به منو، دستور `/start` را بزنید.\n\n"
            "💬 **سوال خود را بپرسید:**",
            parse_mode="Markdown"
        )

    elif data == "menu_memory":
        await show_memory_menu(update, context, edit=True)

    elif data == "menu_reminder":
        await show_reminder_menu(update, context, edit=True)

    elif data == "menu_status":
        await status_command(update, context)

    elif data == "menu_help":
        # می‌توانید یک help ساده نمایش دهید یا همان منوی اصلی
        await query.edit_message_text(
            "❓ **راهنما**\n\n"
            "برای شروع از دکمه‌های منو استفاده کنید.\n"
            "هر بخش توضیحات مخصوص خود را دارد.\n"
            "همیشه می‌توانید با دکمه‌ی 🔙 به منوی اصلی بازگردید.",
            parse_mode="Markdown"
        )

    # ===== منوی حافظه =====
    elif data == "memory_save":
        await memory_save(update, context)
    elif data == "memory_view":
        await memory_view(update, context)
    elif data == "memory_delete":
        await memory_delete(update, context)
    elif data.startswith("delete_mem_"):
        await memory_delete_confirm(update, context)
    elif data == "memory_clear":
        await memory_clear(update, context)
    elif data == "memory_clear_confirm":
        await memory_clear_confirm(update, context)

    # ===== منوی یادآوری =====
    elif data == "reminder_set":
        await reminder_set(update, context)
    elif data == "reminder_list":
        await reminder_list(update, context)
    elif data == "reminder_cancel":
        await reminder_cancel(update, context)
    elif data.startswith("cancel_rem_"):
        await reminder_cancel_confirm(update, context)
        # در handlers/buttons.py، در بخش منوی یادآوری اضافه کنید:
    elif data == "reminder_new":
        await reminder_new(update, context)
    elif data.startswith("cal_"):
        await calendar_handler(update, context)
