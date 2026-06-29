"""تولید عکس با FreeLLMAPI (endpoint سازگار با OpenAI: /v1/images/generations)."""
import base64
import logging
import requests
from telegram import Update
from telegram.ext import ContextTypes
from config import FREELLMAPI_KEY, BASE_URL

logger = logging.getLogger(__name__)

IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3-flash-image",
    "gemini-3.1-flash-image",
    "flux-schnell",
    "flux-dev",
    "sdxl",
    "dall-e-3",
]

IMAGE_ENDPOINT = f"{BASE_URL}/v1/images/generations"


def _call_image_api(prompt: str) -> tuple[bytes | None, str | None, str | None]:
    """خروجی: (image_bytes, model_used, error)"""
    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    last_err = None
    for model in IMAGE_MODELS:
        try:
            payload = {"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"}
            r = requests.post(IMAGE_ENDPOINT, headers=headers, json=payload, timeout=120)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data") or []
                if not items:
                    last_err = f"empty data on {model}"
                    continue
                item = items[0]
                if item.get("b64_json"):
                    return base64.b64decode(item["b64_json"]), model, None
                if item.get("url"):
                    img = requests.get(item["url"], timeout=60)
                    if img.status_code == 200:
                        return img.content, model, None
                    last_err = f"download fail {img.status_code} on {model}"
                else:
                    last_err = f"no image payload on {model}"
            elif r.status_code == 404:
                last_err = f"endpoint not found ({model})"
            else:
                last_err = f"{r.status_code} on {model}: {r.text[:120]}"
                logger.warning(last_err)
        except Exception as e:
            last_err = f"{model}: {e}"
            logger.warning(last_err)
    return None, None, last_err


async def _do_generate(update: Update, prompt: str):
    msg = update.effective_message
    processing = await msg.reply_text("🎨 در حال ساخت عکس... (ممکن است تا یک دقیقه طول بکشد)")
    img, model_used, err = _call_image_api(prompt)
    if not img:
        await processing.edit_text(
            "⚠️ ساخت عکس ناموفق بود.\n"
            f"خطا: {err or 'نامشخص'}\n\n"
            "اگر FreeLLMAPI شما تولید عکس را پشتیبانی نمی‌کند، این قابلیت کار نخواهد کرد."
        )
        return
    await processing.delete()
    await msg.reply_photo(photo=img, caption=f"🖼 prompt:\n«{prompt}»\n\n🤖 مدل: {model_used}")


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    prompt = " ".join(args).strip()
    if not prompt:
        context.user_data["awaiting_image_prompt"] = True
        await update.message.reply_text(
            "🎨 لطفاً توضیح عکسی که می‌خواهی بسازم را در پیام بعدی بفرست.\n"
            "مثال: «یک گربه فضانورد روی ماه با سبک کارتونی»\n\n"
            "برای لغو: /cancel"
        )
        return
    await _do_generate(update, prompt)


async def handle_pending_image_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگر کاربر در حالت انتظار prompt است، اینجا هندل کن. خروجی True یعنی هندل شد."""
    if not context.user_data.get("awaiting_image_prompt"):
        return False
    context.user_data.pop("awaiting_image_prompt", None)
    prompt = (update.message.text or "").strip()
    if not prompt:
        await update.message.reply_text("❌ متن خالی بود. عملیات لغو شد.")
        return True
    await _do_generate(update, prompt)
    return True
