import logging
import requests
from bs4 import BeautifulSoup
import html2text
from telegram import Update
from telegram.ext import ContextTypes

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /summarize - خلاصه‌سازی لینک یا متن"""
    text = " ".join(context.args)
    
    if not text:
        await update.message.reply_text(
            "📝 **راهنمای خلاصه‌سازی**\n\n"
            "• برای خلاصه‌سازی یک لینک:\n"
            "  `/summarize https://example.com`\n\n"
            "• برای خلاصه‌سازی یک متن:\n"
            "  `/summarize متن طولانی ...`\n\n"
            "💡 می‌توانید لینک یا متن را به‌صورت مستقیم نیز ارسال کنید."
        )
        return
    
    status_msg = await update.message.reply_text("⏳ در حال پردازش...")
    
    try:
        # تشخیص لینک
        if text.startswith("http://") or text.startswith("https://"):
            content = await extract_url_content(text)
            if not content:
                await status_msg.edit_text("❌ خطا در دریافت محتوای لینک. لطفاً لینک را بررسی کنید.")
                return
            source = "لینک"
        else:
            content = text
            source = "متن"
        
        # خلاصه‌سازی با FreeLLMAPI
        summary = await get_summary(content)
        
        await status_msg.delete()
        await update.message.reply_text(
            f"📝 **خلاصه‌سازی {source}:**\n\n{summary}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Summarize error: {e}")
        await status_msg.edit_text("❌ خطا در خلاصه‌سازی. لطفاً دوباره تلاش کنید.")

async def extract_url_content(url: str) -> str:
    """استخراج متن از لینک"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # حذف تگ‌های غیرضروری
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # استخراج متن اصلی
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_emphasis = True
        text = h.handle(str(soup))
        
        # تمیز کردن متن
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content = '\n'.join(lines)
        
        # محدود کردن طول متن
        if len(content) > 5000:
            content = content[:5000] + "..."
        
        return content
    except Exception as e:
        logging.error(f"Extract URL error: {e}")
        return ""

async def get_summary(content: str) -> str:
    """ارسال متن به FreeLLMAPI برای خلاصه‌سازی"""
    from config import FREELLMAPI_KEY, FREELLMAPI_URL
    
    headers = {"Authorization": f"Bearer {FREELLMAPI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "auto",
        "messages": [
            {"role": "user", "content": f"لطفاً متن زیر را به‌صورت خلاصه و مفید خلاصه کن:\n\n{content}"}
        ]
    }
    
    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result.get("choices"):
            return result["choices"][0]["message"]["content"]
        return "خطا در دریافت خلاصه."
    except Exception as e:
        logging.error(f"Summary API error: {e}")
        return "خطا در خلاصه‌سازی."
