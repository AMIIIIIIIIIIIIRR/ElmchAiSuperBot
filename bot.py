import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
from config import TELEGRAM_TOKEN
from database import init_db, close_db, get_all_pending_reminders
from handlers.base import start_command, help_command
from handlers.memory import (
    show_memory_menu, memory_save, memory_view, memory_delete,
    memory_delete_confirm, memory_clear, memory_clear_confirm,
    handle_memory_text
)
from handlers.reminder import (
    show_reminder_menu, reminder_new, reminder_list,
    reminder_cancel, reminder_cancel_confirm, handle_reminder_text,
    calendar_handler, send_reminder
)
from handlers.ai import handle_message, status_command
from handlers.buttons import button_handler
from handlers.personality import personality_command
from handlers.websearch import websearch_command
from handlers.vision import handle_photo
from handlers.files import handle_document
from handlers.imagegen import image_command, handle_pending_image_prompt
from handlers.voice import handle_voice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reschedule_pending_reminders(application: Application):
    if application.job_queue is None:
        logger.error("❌ JobQueue نصب نیست! requirements باید شامل python-telegram-bot[job-queue] باشد.")
        return

    rows = await get_all_pending_reminders()
    now = datetime.now()
    existing_names = {j.name for j in application.job_queue.jobs()}
    scheduled, fired_now = 0, 0

    for r in rows:
        job_id = r["job_id"] or f"reminder_{r['user_id']}_{int(r['remind_at'].timestamp())}"
        if job_id in existing_names:
            continue

        data = {
            "reminder_id": r["id"],
            "user_id": r["user_id"],
            "chat_id": r["chat_id"],
            "message": r["message"],
            "job_id": job_id,
        }

        delta = r["remind_at"] - now
        if delta.total_seconds() <= 0:
            application.job_queue.run_once(send_reminder, when=0, name=job_id, data=data)
            fired_now += 1
        else:
            application.job_queue.run_once(send_reminder, when=delta, name=job_id, data=data)
            scheduled += 1

    logger.info(f"🔁 Reschedule: {scheduled} آینده، {fired_now} عقب‌افتاده.")


async def post_init(application: Application):
    await init_db()
    await application.bot.delete_webhook()

    commands = [
        ("start", "نمایش منوی اصلی"),
        ("help", "راهنما"),
        ("personality", "تغییر شخصیت ربات"),
        ("image", "ساخت عکس با هوش مصنوعی"),
        ("cancel", "لغو عملیات جاری"),
        ("websearch", "روشن/خاموش جستجوی اینترنت"),
    ]
    await application.bot.set_my_commands(commands)
    await reschedule_pending_reminders(application)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("reminder_data", None)
    context.user_data.pop("reminder_step", None)
    context.user_data.pop("awaiting_image_prompt", None)
    await update.message.reply_text("✅ عملیات لغو شد. می‌توانید سوال خود را بپرسید.")


def main():
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(close_db)
        .build()
    )

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue در دسترس نیست. لطفاً 'python-telegram-bot[job-queue]' را نصب کنید."
        )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("personality", personality_command))
    application.add_handler(CommandHandler("websearch", websearch_command))
    application.add_handler(CommandHandler("image", image_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # اگر کاربر منتظر prompt برای ساخت عکس است
        if await handle_pending_image_prompt(update, context):
            return

        waiting_for = context.user_data.get("waiting_for")
        if waiting_for == "reminder_text":
            await handle_reminder_text(update, context)
        elif waiting_for == "memory_text":
            await handle_memory_text(update, context)
        else:
            await handle_message(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 ربات با تحلیل عکس/فایل و تولید تصویر روشن شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
