import logging
import requests
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import FREELLMAPI_KEY, FREELLMAPI_URL, BASE_URL, SHORT_TERM_MEMORY
from database import (
    save_message, get_recent_history, get_memories,
    get_web_search_status
)
from ddgs import DDGS

# ===== تنظیمات جستجو =====
SEARCH_TIMEOUT = 8
MAX_SEARCH_RESULTS = 3

# ===== کلمات کلیدی با وزن =====
def calculate_search_weight(text: str) -> int:
    text_lower = text.lower()
    weight = 0

    high_weight = ["قیمت", "ارز", "دلار", "یورو", "طلا", "سکه", "بیت‌کوین"]
    for w in high_weight:
        if w in text_lower:
            weight += 3

    mid_weight = ["امروز", "الان", "همین الان", "اخبار", "جدید", "آخرین"]
    for w in mid_weight:
        if w in text_lower:
            weight += 2

    low_weight = ["بهترین", "برترین", "موفق‌ترین", "معروف‌ترین"]
    for w in low_weight:
        if w in text_lower:
            weight += 1

    if text_lower.endswith("؟") or "چیست" in text_lower or "چند" in text_lower:
        weight += 1

    return weight

def needs_search(text: str) -> bool:
    if any(word in text for word in ["جستجو", "اینترنت", "آنلاین"]):
        return True
    return calculate_search_weight(text) >= 3

def perform_search(query: str, max_results: int = MAX_SEARCH_RESULTS):
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logging.error(f"Search error: {e}")
        return []

async def get_search_results(query: str):
    try:
        loop = asyncio.get_event_loop()
        results = await asyncio.wait_for(
            loop.run_in_executor(None, perform_search, query, MAX_SEARCH_RESULTS),
            timeout=SEARCH_TIMEOUT
        )
        return results
    except asyncio.TimeoutError:
        logging.warning(f"Search timed out for: {query}")
        return []
    except Exception as e:
        logging.error(f"Search exception: {e}")
        return []

def build_search_context(query: str, results: list) -> str:
    if not results:
        return f"سوال کاربر: {query}\n\n(نتیجه‌ای پیدا نشد.)"
    text = f"سوال کاربر: {query}\n\nنتایج جستجو:\n"
    for i, r in enumerate(results, 1):
        title = r.get("title", "بدون عنوان")
        body = r.get("body", "توضیحی در دسترس نیست")
        link = r.get("href", "#")
        text += f"{i}. عنوان: {title}\n   لینک: {link}\n   خلاصه: {body[:300]}\n\n"
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text or ""
    if user_message.startswith('/'):
        return

    processing_msg = await update.message.reply_text("🤔 در حال پردازش...")

    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    memories = await get_memories(user_id)

    web_search_enabled = await get_web_search_status(user_id)
    use_search = False
    search_results = None
    search_footer = ""

    if web_search_enabled and needs_search(user_message):
        await processing_msg.edit_text("🔍 در حال جستجو و تحلیل...")
        search_results = await get_search_results(user_message)
        if search_results:
            search_footer = "\n\n🌐 این پاسخ با استفاده از جستجوی اینترنت تهیه شده است."
        else:
            search_footer = "\n\n⚠️ جستجو انجام نشد (عدم دسترسی یا زمان‌بر بودن)."

    base_system = """
شما یک دستیار هوشمند و حرفه‌ای هستید که به زبان فارسی پاسخ می‌دهید.

📌 **یادداشت‌های کاربر (اطلاعات مهم):**
{memories}

🔹 **قوانین:**
1. همیشه به فارسی پاسخ دهید.
2. از یادداشت‌های کاربر در پاسخ‌های خود استفاده کنید.
3. پاسخ‌ها باید روان، ادبی و مفید باشند.
"""

    if use_search and search_results:
        search_context = build_search_context(user_message, search_results)
        system_prompt = base_system.format(memories="\n".join(f"• {m}" for m in memories) if memories else "هیچ یادداشتی ذخیره نشده است.")
        system_prompt += f"\n\n🔍 **اطلاعات به‌روز از جستجوی وب:**\n{search_context}"
        system_prompt += "\n\nلطفاً بر اساس اطلاعات بالا و دانش خود، پاسخی جامع و مفید به کاربر بدهید. در صورت استفاده از اطلاعات جستجو، حتماً به منابع اشاره کنید."
    else:
        system_prompt = base_system.format(memories="\n".join(f"• {m}" for m in memories) if memories else "هیچ یادداشتی ذخیره نشده است.")

    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    payload = {"model": "auto", "messages": messages}

    try:
        # ===== درخواست اول =====
        response = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            await processing_msg.edit_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
            return

        ai_reply = choices[0]["message"]["content"]
        model_used = result.get("model", "نامشخص")

        # ===== حلقه: اگر owl-alpha بود، دوباره امتحان کن (حداکثر ۳ بار) =====
        retry_count = 0
        while "openrouter/owl-alpha" in model_used and retry_count < 3:
            logging.warning(f"⚠️ مدل {model_used} شناسایی شد. تلاش مجدد {retry_count + 1}...")
            await processing_msg.edit_text(f"🔄 مدل نامناسب شناسایی شد، تلاش مجدد... ({retry_count + 1}/3)")
            
            response = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            choices = result.get("choices") or []
            if not choices:
                break
            ai_reply = choices[0]["message"]["content"]
            model_used = result.get("model", "نامشخص")
            retry_count += 1

        if "openrouter/owl-alpha" in model_used:
            logging.warning(f"⚠️ بعد از ۳ تلاش، همچنان {model_used} است. پاسخ با همان مدل ارسال می‌شود.")
            search_footer += "\n\n⚠️ مدل مناسب در دسترس نبود، پاسخ با مدل موجود ارسال شد."

        await save_message(user_id, "user", user_message)
        await save_message(user_id, "assistant", ai_reply)
        await processing_msg.delete()

        full_reply = f"{ai_reply}{search_footer}\n\n---\n🤖 مدل: {model_used}"
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
    try:
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"},
            timeout=10,
        )
        if response.status_code != 200:
            await message_obj.edit_text(f"❌ خطا در دریافت وضعیت: {response.status_code}")
            return

        models = response.json().get("data", [])
        if not models:
            await message_obj.edit_text("❌ هیچ مدلی در دسترس نیست.")
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

        await message_obj.edit_text(reply, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        await message_obj.edit_text(f"❌ خطا در ارتباط با سرور: {str(e)[:100]}")
