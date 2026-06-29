import logging
import requests
import jdatetime
from datetime import datetime

# ===== تنظیمات API (با کلید nerkh.io) =====
NERKH_API_KEY = "YOUR_API_KEY_HERE"  # ← کلید خود را اینجا قرار دهید
NERKH_API_URL = "https://api.nerkh.io/v1/prices/json/all"

def get_gold_price() -> str:
    """دریافت قیمت لحظه‌ای طلا از nerkh.io"""
    try:
        params = {"api_key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # ساختار پاسخ: {"gold": {"price": 2750000, ...}, "usd": {...}, ...}
            gold_data = data.get("gold", {})
            price = gold_data.get("price", "نامشخص")
            if price != "نامشخص" and isinstance(price, (int, float)):
                price = f"{price:,.0f}"
            return f"💰 **قیمت طلا (هر گرم):**\n{price} تومان"
        else:
            return f"⚠️ خطا در دریافت قیمت طلا (کد {response.status_code}). لطفاً بعداً امتحان کنید."
    except Exception as e:
        logging.error(f"Gold API error: {e}")
        return "⚠️ خطا در دریافت قیمت طلا. لطفاً بعداً امتحان کنید."

def get_usd_price() -> str:
    """دریافت قیمت لحظه‌ای دلار از nerkh.io"""
    try:
        params = {"api_key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            usd_data = data.get("usd", {})
            price = usd_data.get("price", "نامشخص")
            if price != "نامشخص" and isinstance(price, (int, float)):
                price = f"{price:,.0f}"
            return f"💵 **قیمت دلار:**\n{price} تومان"
        else:
            return f"⚠️ خطا در دریافت قیمت دلار (کد {response.status_code}). لطفاً بعداً امتحان کنید."
    except Exception as e:
        logging.error(f"USD API error: {e}")
        return "⚠️ خطا در دریافت قیمت دلار. لطفاً بعداً امتحان کنید."

def get_today_date() -> str:
    """دریافت تاریخ امروز به شمسی و میلادی"""
    try:
        today_jalali = jdatetime.date.today()
        today_gregorian = datetime.now()
        
        weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        weekday_name = weekdays[today_jalali.weekday()]
        
        return (
            f"📅 **تاریخ امروز:**\n"
            f"شمسی: {today_jalali.strftime('%Y/%m/%d')} ({weekday_name})\n"
            f"میلادی: {today_gregorian.strftime('%Y/%m/%d')}"
        )
    except Exception as e:
        logging.error(f"Date error: {e}")
        return "⚠️ خطا در دریافت تاریخ."
