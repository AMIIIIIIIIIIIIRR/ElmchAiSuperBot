import logging
import requests
from bs4 import BeautifulSoup
import html2text

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
