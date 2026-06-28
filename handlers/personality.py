# -*- coding: utf-8 -*-
"""
هندلر انتخاب شخصیت ربات.
کاربر از منو یکی از شخصیت‌ها را انتخاب می‌کند و در DB ذخیره می‌شود.
حالت رکیک (rude) نیاز به تایید ۱۸+ دارد.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from personalities import PERSONALITIES, get_personality
from database import (
    get_user_personality, set_user_personality,
    get_nsfw_accepted, set_nsfw_accepted,
)


def _menu_keyboard(current: str) -> InlineKeyboardMarkup:
    rows = []
    for key, p in PERSONALITIES.items():
        mark = "✅ " if key == current else ""
        rows.append([InlineKeyboardButton(f"{mark}{p['name']}", callback_data=f"pers_set_{key}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


async def show_personality_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = True):
    user_id = str(update.effective_user.id)
    current = await get_user_personality(user_id)
    current_p = get_personality(current)

    text = (
        "🎭 **انتخاب شخصیت ربات**\n\n"
        f"شخصیت فعلی: **{current_p['name']}**\n"
        f"_{current_p['short']}_\n\n"
        "یکی از شخصیت‌های زیر را انتخاب کن. ربات تا وقتی خودت عوضش نکنی، "
        "با همین لحن باهات حرف می‌زنه.\n\n"
    )
    for p in PERSONALITIES.values():
        text += f"• **{p['name']}** — {p['short']}\n"

    markup = _menu_keyboard(current)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def personality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /personality"""
    await show_personality_menu(update, context, edit=False)


async def personality_set(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    """انتخاب یک شخصیت از روی callback_data = pers_set_<key>"""
    query = update.callback_query
    user_id = str(update.effective_user.id)

    p = PERSONALITIES.get(key)
    if not p:
        await query.answer("شخصیت نامعتبر است.", show_alert=True)
        return

    # برای شخصیت رکیک، نیاز به تایید ۱۸+
    if p.get("nsfw"):
        accepted = await get_nsfw_accepted(user_id)
        if not accepted:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ بله، ۱۸ سالم تموم شده", callback_data=f"pers_nsfw_yes_{key}")],
                [InlineKeyboardButton("❌ نه، بازگشت", callback_data="menu_personality")],
            ])
            await query.edit_message_text(
                "⚠️ **هشدار محتوای بزرگسال (۱۸+)**\n\n"
                "شخصیت «بی‌ادب و رکیک» از فحش‌های ناموسی، خانوادگی و الفاظ زشت "
                "استفاده می‌کند. این محتوا فقط مناسب افراد بالای ۱۸ سال است.\n\n"
                "آیا تأیید می‌کنی که بالای ۱۸ سال هستی و با آگاهی کامل این حالت را فعال می‌کنی؟",
                parse_mode="Markdown",
                reply_markup=kb,
            )
            return

    await set_user_personality(user_id, key)
    await query.answer(f"شخصیت تغییر کرد: {p['name']}", show_alert=False)
    await show_personality_menu(update, context, edit=True)


async def personality_nsfw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    """تایید ۱۸+ برای شخصیت رکیک."""
    user_id = str(update.effective_user.id)
    await set_nsfw_accepted(user_id, True)
    await set_user_personality(user_id, key)
    p = PERSONALITIES.get(key, {})
    await update.callback_query.answer(f"فعال شد: {p.get('name','')}", show_alert=False)
    await show_personality_menu(update, context, edit=True)
