import logging
import requests
import jdatetime
from datetime import datetime

# ===== تنظیمات API =====
# از nerkh.io استفاده می‌کنیم (رایگان و بدون نیاز به کلید)
GOLD_API = "https://api.nerkh.io/live/gold"
USD_API = "https://api.nerkh.io/live/usd"
# برای ارزهای دیگر می‌توانید از همین سرویس استفاده کنید

def get_gold_price() -> str:
    """دریافت قیمت لحظه‌ای طلا"""
    try:
        response = requests.get(GOLD_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        # ساختار پاسخ ممکن است بسته به API متفاوت باشد
        # اینجا فرض می‌کنیم پاسخ شامل فیلد "price" است
        price = data.get("price", "نامشخص")
        return f"💰 **قیمت طلا (هر گرم):**\n{price} تومان"
    except Exception as e:
        logging.error(f"Gold API error: {e}")
        return "⚠️ در حال حاضر نمی‌توانم قیمت طلا را دریافت کنم. لطفاً بعداً امتحان کنید."

def get_usd_price() -> str:
    """دریافت قیمت لحظه‌ای دلار"""
    try:
        response = requests.get(USD_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data.get("price", "نامشخص")
        return f"💵 **قیمت دلار:**\n{price} تومان"
    except Exception as e:
        logging.error(f"USD API error: {e}")
        return "⚠️ در حال حاضر نمی‌توانم قیمت دلار را دریافت کنم. لطفاً بعداً امتحان کنید."

def get_today_date() -> str:
    """دریافت تاریخ امروز به شمسی و میلادی"""
    try:
        today_jalali = jdatetime.date.today()
        today_gregorian = datetime.now()
        
        # نام روز هفته به فارسی
        weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        weekday_name = weekdays[today_jalali.weekday()]
        
        return (
            f"📅 **تاریخ امروز:**\n"
            f"شمسی: {today_jalali.strftime('%Y/%m/%d')} ({weekday_name})\n"
            f"میلادی: {today_gregorian.strftime('%Y/%m/%d')}\n"
            f"قمری: {today_jalali.strftime('%Y/%m/%d')}"  # در صورت نیاز
        )
    except Exception as e:
        logging.error(f"Date error: {e}")
        return "⚠️ خطا در دریافت تاریخ."
