"""تحلیل عکس با مدل‌های Vision از طریق FreeLLMAPI (سازگار با OpenAI)."""
import base64
import logging
import requests
from telegram import Update
from telegram.ext import ContextTypes
from config import FREELLMAPI_KEY, FREELLMAPI_URL, SHORT_TERM_MEMORY
from database import save_message, get_recent_history, get_user_personality
from personalities import get_system_prompt

logger = logging.getLogger(__name__)

# مدل‌های Vision به ترتیب اولویت (fallback)
VISION_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gpt-4o-mini",
    "gpt-4o",
    "llama-3.2-90b-vision",
    "llama-3.2-11b-vision",
]

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB


async def _download_telegram_file(file_obj, context: ContextTypes.DEFAULT_TYPE) -> bytes:
    tg_file = await context.bot.get_file(file_obj.file_id)
    bio = await tg_file.download_as_bytearray()
    return bytes(bio)


def _call_vision(messages: list) -> tuple[str | None, str | None, str | None]:
    """امتحان مدل‌های vision یکی یکی. خروجی: (reply, model_used, error)"""
    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    last_err = None
    for model in VISION_MODELS:
        try:
            payload = {"model": model, "messages": messages, "max_tokens": 1500}
            r = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=90)
            if r.status_code == 200:
                data = r.json()
                choices = data.get("choices") or []
                if choices:
                    return choices[0]["message"]["content"], data.get("model", model), None
                last_err = f"empty choices on {model}"
            else:
                last_err = f"{r.status_code} on {model}: {r.text[:120]}"
                logger.warning(last_err)
        except Exception as e:
            last_err = f"{model}: {e}"
            logger.warning(last_err)
    return None, None, last_err


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر عکس‌های ارسالی کاربر."""
    user_id = str(update.effective_user.id)
    msg = update.message
    if not msg or not msg.photo:
        return

    photo = msg.photo[-1]  # بزرگ‌ترین سایز
    if photo.file_size and photo.file_size > MAX_IMAGE_BYTES:
        await msg.reply_text("⚠️ حجم عکس بیش از حد مجاز (۸ مگابایت) است.")
        return

    caption = (msg.caption or "این عکس را به فارسی به‌طور دقیق توصیف و تحلیل کن.").strip()

    processing = await msg.reply_text("🖼 در حال تحلیل عکس...")

    try:
        img_bytes = await _download_telegram_file(photo, context)
    except Exception as e:
        logger.error(f"download photo error: {e}")
        await processing.edit_text("❌ خطا در دریافت عکس از تلگرام.")
        return

    b64 = base64.b64encode(img_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"

    personality_prompt = get_system_prompt(await get_user_personality(user_id))
    system_prompt = (
        f"{personality_prompt}\n\n"
        "تو یک تحلیل‌گر تصویر هستی. همیشه فارسی پاسخ بده و در توصیف عکس دقیق و کامل باش."
    )

    messages = [{"role": "system", "content": system_prompt}]
    # تاریخچه متنی کوتاه
    history = await get_recent_history(user_id, SHORT_TERM_MEMORY)
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": caption},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    })

    reply, model_used, err = _call_vision(messages)
    if not reply:
        await processing.edit_text(
            f"⚠️ هیچ‌کدام از مدل‌های Vision پاسخ نداد.\nخطا: {err or 'نامشخص'}"
        )
        return

    # ذخیره در history به صورت متنی
    await save_message(user_id, "user", f"[تصویر ارسال شد] {caption}")
    await save_message(user_id, "assistant", reply)

    await processing.delete()
    await msg.reply_text(f"{reply}\n\n---\n🤖 مدل: {model_used}")
