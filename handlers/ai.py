import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import FREELLMAPI_KEY, FREELLMAPI_URL, BASE_URL, SHORT_TERM_MEMORY
from database import save_message, get_recent_history, get_memories

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text or ""
    if user_message.startswith("/"):
        return

    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")
    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    memories = await get_memories(user_id)

    system_prompt = f"""
شما یک دستیار هوشمند و حرفه‌ای هستید که به زبان فارسی پاسخ می‌دهید.

📌 **یادداشت‌های کاربر (اطلاعات مهم):**
{chr(10).join(f"• {m}" for m in memories) if memories else "هیچ یادداشتی ذخیره نشده است."}

🔹 **قوانین:**
1. همیشه به فارسی پاسخ دهید.
2. از یادداشت‌های کاربر در پاسخ‌های خود استفاده کنید.
3. پاسخ‌ها باید روان، ادبی و مفید باشند.
"""
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {FREELLMAPI_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": "auto", "messages": messages}

    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            await processing_msg.edit_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
            return

        ai_reply = choices[0]["message"]["content"]
        model_used = result.get("model", "نامشخص")
        await save_message(user_id, "user", user_message)
        await save_message(user_id, "assistant", ai_reply)
        await processing_msg.delete()

        full_reply = f"{ai_reply}\n\n---\n🤖 مدل: {model_used}"
        await update.message.reply_text(full_reply)
    except requests.exceptions.RequestException as e:
        logging.error(f"AI request error: {e}")
        await processing_msg.edit_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        await processing_msg.edit_text(f"❌ خطای غیرمنتظره: {str(e)[:100]}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await _render_status(update.callback_query.message, edit=True)
    else:
        await _render_status(update.message, edit=False)

async def _render_status(message_obj, edit: bool):
    if edit:
        status_msg = await message_obj.edit_text("⏳ در حال دریافت وضعیت مدل‌ها...")
    else:
        status_msg = await message_obj.reply_text("⏳ در حال دریافت وضعیت مدل‌ها...")

    try:
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"},
            timeout=10,
        )
        if response.status_code != 200:
            await status_msg.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
            return

        models = response.json().get("data", [])
        if not models:
            await status_msg.edit_text("❌ هیچ مدلی در دسترس نیست.")
            return

        available, unavailable, limited = [], [], []
        for model in models:
            model_id = model.get("id", "نامشخص")
            status = model.get("status", "unknown")
            if status in ("unavailable", "inactive"):
                unavailable.append(model_id)
            elif status in ("limited", "rate_limited"):
                limited.append(model_id)
            else:
                available.append(model_id)

        reply = "📊 **وضعیت لحظه‌ای مدل‌ها**\n" + "─" * 25 + "\n\n"
        if available:
            reply += "✅ **در دسترس:**\n" + "\n".join(f"• `{m}`" for m in available[:20]) + "\n\n"
        if limited:
            reply += "⚠️ **محدودیت خورده:**\n" + "\n".join(f"• `{m}`" for m in limited) + "\n\n"
        if unavailable:
            reply += "❌ **در دسترس نیست:**\n" + "\n".join(f"• `{m}`" for m in unavailable) + "\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_status")],
            [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_menu")],
        ]
        await status_msg.edit_text(reply, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await status_msg.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")
