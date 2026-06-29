import logging
import requests
import jdatetime
from datetime import datetime
import os

# ===== تنظیمات API =====
NERKH_API_KEY = os.getenv("NERKH_API_KEY", "YOUR_API_KEY_HERE")
NERKH_API_URL = "https://api.nerkh.io/v1/prices/json/all"

# ===== نام‌های فارسی برای انواع طلا =====
GOLD_LABELS = {
    "GOLD18K": "طلای ۱۸ عیار",
    "GOLD24K": "طلای ۲۴ عیار",
    "SEKE_EMAMI": "سکه امامی",
    "SEKE_BAHAR": "سکه تمام بهار",
    "OUNCE": "انس طلا",
    "MAZANEH": "مظنه طلا",
    "SEKE_NIM": "سکه نیم",
    "SEKE_ROB": "سکه ربع",
    "SEKE_1G": "سکه ۱ گرمی",
}

def get_gold_price() -> str:
    """دریافت قیمت لحظه‌ای انواع طلا از nerkh.io با نام‌های فارسی"""
    try:
        params = {"x-api-key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            gold_data = data.get("data", {}).get("gold", {})
            
            if not gold_data:
                return "⚠️ اطلاعات طلا در دسترس نیست."
            
            result = "💰 **قیمت طلا:**\n"
            found = False
            
            for gold_key, label in GOLD_LABELS.items():
                if gold_key in gold_data:
                    found = True
                    item = gold_data[gold_key]
                    price = item.get("current", "نامشخص")
                    update_time = item.get("update", "")
                    
                    # فرمت قیمت با جداکننده هزارگان
                    if price != "نامشخص" and isinstance(price, (int, float, str)):
                        try:
                            price_int = int(price)
                            price = f"{price_int:,}"
                        except:
                            pass
                    
                    result += f"• {label}: {price} تومان"
                    if update_time:
                        result += f" (🕐 {update_time})"
                    result += "\n"
            
            if not found:
                return "⚠️ هیچ نوع طلایی در پاسخ یافت نشد."
            return result
        else:
            return f"⚠️ خطا در دریافت قیمت طلا (کد {response.status_code})."
    except Exception as e:
        logging.error(f"Gold API error: {e}")
        return "⚠️ خطا در دریافت قیمت طلا. لطفاً بعداً امتحان کنید."

def get_usd_price() -> str:
    """دریافت قیمت لحظه‌ای دلار از nerkh.io"""
    try:
        params = {"x-api-key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            usd_data = data.get("data", {}).get("currency", {}).get("USD", {})
            
            if not usd_data:
                return "⚠️ اطلاعات دلار در دسترس نیست."
            
            price = usd_data.get("current", "نامشخص")
            update_time = usd_data.get("update", "")
            
            if price != "نامشخص" and isinstance(price, (int, float, str)):
                try:
                    price_int = int(price)
                    price = f"{price_int:,}"
                except:
                    pass
            
            result = f"💵 **قیمت دلار آمریکا:**\n{price} تومان"
            if update_time:
                result += f"\n🕐 {update_time}"
            return result
        else:
            return f"⚠️ خطا در دریافت قیمت دلار (کد {response.status_code})."
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
