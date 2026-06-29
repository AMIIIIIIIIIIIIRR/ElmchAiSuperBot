"""تحلیل فایل‌های آپلودی (PDF / DOCX / متن / کد) با FreeLLMAPI."""
import io
import logging
import requests
from telegram import Update
from telegram.ext import ContextTypes
from config import FREELLMAPI_KEY, FREELLMAPI_URL
from database import save_message, get_user_personality
from personalities import get_system_prompt

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 20 * 1024 * 1024  # 20MB
MAX_TEXT_CHARS = 30000

DOC_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "llama-3.3-70b",
    "mistral-large-3",
    "gpt-oss-120b-free",
]

TEXT_EXT = (".txt", ".md", ".csv", ".json", ".log", ".xml", ".yml", ".yaml",
            ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".java",
            ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php", ".sh", ".sql")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:50]:  # حداکثر ۵۰ صفحه
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts).strip()
    except Exception as e:
        logger.error(f"pdf parse error: {e}")
        return ""


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        return ""
    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
    except Exception as e:
        logger.error(f"docx parse error: {e}")
        return ""


def _extract_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "cp1256", "latin-1"):
        try:
            return data.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return ""


def _call_doc_model(messages: list) -> tuple[str | None, str | None, str | None]:
    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    last_err = None
    for model in DOC_MODELS:
        try:
            payload = {"model": model, "messages": messages, "max_tokens": 2000}
            r = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=90)
            if r.status_code == 200:
                d = r.json()
                ch = d.get("choices") or []
                if ch:
                    return ch[0]["message"]["content"], d.get("model", model), None
            else:
                last_err = f"{r.status_code} on {model}: {r.text[:120]}"
                logger.warning(last_err)
        except Exception as e:
            last_err = f"{model}: {e}"
            logger.warning(last_err)
    return None, None, last_err


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    msg = update.message
    if not msg or not msg.document:
        return

    doc = msg.document
    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "file").lower()

    # عکس‌هایی که به‌صورت سند ارسال شده‌اند → مسیر vision
    if mime.startswith("image/"):
        # ساده‌ترین کار: راهنمایی کاربر
        await msg.reply_text("📸 برای تحلیل عکس، آن را به‌صورت Photo (نه فایل) ارسال کنید.")
        return

    if doc.file_size and doc.file_size > MAX_FILE_BYTES:
        await msg.reply_text("⚠️ حجم فایل بیش از حد مجاز (۲۰ مگابایت) است.")
        return

    processing = await msg.reply_text("📄 در حال خواندن فایل...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        logger.error(f"download doc error: {e}")
        await processing.edit_text("❌ خطا در دریافت فایل از تلگرام.")
        return

    # استخراج متن
    if name.endswith(".pdf") or mime == "application/pdf":
        text = _extract_pdf(raw)
        kind = "PDF"
    elif name.endswith(".docx") or "wordprocessingml" in mime:
        text = _extract_docx(raw)
        kind = "Word"
    elif name.endswith(TEXT_EXT) or mime.startswith("text/") or mime in ("application/json", "application/xml"):
        text = _extract_text(raw)
        kind = "متن"
    else:
        await processing.edit_text(
            "⚠️ نوع فایل پشتیبانی نمی‌شود.\nفرمت‌های مجاز: PDF, DOCX, TXT, MD, CSV, JSON و فایل‌های کد."
        )
        return

    if not text:
        await processing.edit_text("❌ نتوانستم متنی از این فایل استخراج کنم (احتمالاً اسکن شده یا خالی است).")
        return

    truncated = False
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        truncated = True

    question = (msg.caption or "این فایل را به فارسی خلاصه و نکات کلیدی‌اش را استخراج کن.").strip()
    await processing.edit_text("🧠 در حال تحلیل محتوای فایل...")

    personality_prompt = get_system_prompt(await get_user_personality(user_id))
    system_prompt = (
        f"{personality_prompt}\n\n"
        "تو تحلیل‌گر سند هستی. همیشه فارسی پاسخ بده، ساختار پاسخ تمیز و خوانا باشد."
    )
    user_block = (
        f"📎 فایل: {doc.file_name} ({kind})\n\n"
        f"❓ درخواست کاربر:\n{question}\n\n"
        f"📄 محتوای فایل{' (بریده‌شده)' if truncated else ''}:\n---\n{text}\n---"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_block},
    ]

    reply, model_used, err = _call_doc_model(messages)
    if not reply:
        await processing.edit_text(f"⚠️ مدل‌ها پاسخ ندادند.\nخطا: {err or 'نامشخص'}")
        return

    await save_message(user_id, "user", f"[فایل {doc.file_name}] {question}")
    await save_message(user_id, "assistant", reply)

    note = "\n\n⚠️ به دلیل حجم زیاد، فقط بخشی از فایل تحلیل شد." if truncated else ""
    await processing.delete()
    full = f"{reply}{note}\n\n---\n🤖 مدل: {model_used}"
    # تلگرام محدودیت طول دارد
    if len(full) > 4000:
        for i in range(0, len(full), 4000):
            await msg.reply_text(full[i:i + 4000])
    else:
        await msg.reply_text(full)
