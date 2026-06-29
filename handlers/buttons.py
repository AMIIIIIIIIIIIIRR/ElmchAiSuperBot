from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.base import show_main_menu, help_command
from handlers.memory import (
    show_memory_menu, memory_save, memory_view, memory_delete,
    memory_delete_confirm, memory_clear, memory_clear_confirm
)
from handlers.reminder import (
    show_reminder_menu, reminder_new, reminder_list,
    reminder_cancel, reminder_cancel_confirm, calendar_handler
)
from handlers.ai import status_command
from handlers.personality import (
    show_personality_menu, personality_set, personality_nsfw_confirm,
)
from handlers.websearch import websearch_menu, websearch_callback
from handlers.market import get_gold_price, get_usd_price, get_today_date


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

    elif data == "menu_websearch":
        await websearch_menu(update, context, edit=True)

    elif data == "menu_market":
        keyboard = [
            [InlineKeyboardButton("💰 قیمت طلا", callback_data="market_gold")],
            [InlineKeyboardButton("💵 قیمت دلار/ارز", callback_data="market_usd")],
            [InlineKeyboardButton("📅 تاریخ امروز", callback_data="market_date")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 **اطلاعات مالی و تاریخ**\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif data == "market_gold":
        reply = get_gold_price()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_market")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(reply, parse_mode="Markdown", reply_markup=reply_markup)

    elif data == "market_usd":
        reply = get_usd_price()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_market")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(reply, parse_mode="Markdown", reply_markup=reply_markup)

    elif data == "market_date":
        reply = get_today_date()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="menu_market")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(reply, parse_mode="Markdown", reply_markup=reply_markup)

    elif data == "menu_status":
        await status_command(update, context)

    elif data == "menu_help":
        await help_command(update, context)

    # ===== منوی شخصیت =====
    elif data == "menu_personality":
        await show_personality_menu(update, context, edit=True)
    elif data.startswith("pers_nsfw_yes_"):
        key = data[len("pers_nsfw_yes_"):]
        await personality_nsfw_confirm(update, context, key)
    elif data.startswith("pers_set_"):
        key = data[len("pers_set_"):]
        await personality_set(update, context, key)

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
    elif data == "reminder_new":
        await reminder_new(update, context)
    elif data == "reminder_list":
        await reminder_list(update, context)
    elif data == "reminder_cancel":
        await reminder_cancel(update, context)
    elif data.startswith("cancel_rem_"):
        await reminder_cancel_confirm(update, context)
    elif data.startswith("rem_"):
        await calendar_handler(update, context)
    elif data.startswith("cal_"):
        await calendar_handler(update, context)

    # ===== جستجوی وب =====
    elif data in ("websearch_on", "websearch_off"):
        await websearch_callback(update, context)

    elif data == "refresh_status":
        await status_command(update, context)
