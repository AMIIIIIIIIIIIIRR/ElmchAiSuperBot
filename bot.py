import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from database import init_db, close_db
from handlers.base import start_command, help_command
from handlers.memory import (
    remember_command, memories_command, forget_command,
    clear_memories_command, clear_history_command
)
from handlers.ai import handle_message, status_command
from handlers.buttons import button_handler

logging.basicConfig(level=logging.INFO)

async def post_init(application):
    await init_db()
    commands = [
        ("start", "نمایش منوی اصلی"),
        ("remember", "ذخیره یک نکته در حافظه‌ی بلندمدت"),
        ("memories", "نمایش یادداشت‌های ذخیره‌شده"),
        ("forget", "حذف یک یادداشت"),
        ("clear_memories", "پاک کردن همه‌ی یادداشت‌ها"),
        ("clear", "پاک کردن حافظه‌ی کوتاه‌مدت"),
        ("status", "وضعیت مدل‌های هوش مصنوعی"),
        ("help", "راهنمای ربات"),
    ]
    await application.bot.set_my_commands(commands)

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
    application.add_handler(CommandHandler("remember", remember_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("forget", forget_command))
    application.add_handler(CommandHandler("clear_memories", clear_memories_command))
    application.add_handler(CommandHandler("clear", clear_history_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 ربات با ساختار ماژولار روشن شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
