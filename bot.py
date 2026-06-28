import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
from config import TELEGRAM_TOKEN
from database import init_db, close_db
from handlers.base import start_command, help_command
from handlers.memory import (
    show_memory_menu, memory_save, memory_view, memory_delete,
    memory_delete_confirm, memory_clear, memory_clear_confirm,
    handle_memory_text
)
from handlers.reminder import (
    show_reminder_menu, reminder_new, reminder_list,
    reminder_cancel, reminder_cancel_confirm, handle_reminder_text,
    calendar_handler
)
from handlers.ai import handle_message, status_command
from handlers.buttons import button_handler

logging.basicConfig(level=logging.INFO)

async def post_init(application):
    # ===== مقداردهی دیتابیس =====
    await init_db()
    
    # ===== حذف Webhook برای جلوگیری از Conflict =====
    await application.bot.delete_webhook()
    
    # ===== ثبت کامندها =====
    commands = [
        ("start", "نمایش منوی اصلی"),
        ("help", "راهنما"),
        ("cancel", "لغو عملیات جاری"),
    ]
    await application.bot.set_my_commands(commands)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو عملیات جاری و پاک کردن وضعیت کاربر"""
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("reminder_data", None)
    context.user_data.pop("reminder_step", None)
    await update.message.reply_text("✅ عملیات لغو شد. می‌توانید سوال خود را بپرسید.")

def main():
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(close_db)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        waiting_for = context.user_data.get("waiting_for")
        if waiting_for == "reminder_text":
            await handle_reminder_text(update, context)
        elif waiting_for == "memory_text":
            await handle_memory_text(update, context)
        else:
            await handle_message(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 ربات با تقویم شمسی مرحله‌ای و Webhook حذف‌شده روشن شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
