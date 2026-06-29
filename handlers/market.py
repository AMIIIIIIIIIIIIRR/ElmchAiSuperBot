import logging
import requests
import jdatetime
from datetime import datetime
import os

# ===== تنظیمات API (بر اساس مستندات nerkh.io) =====
NERKH_API_KEY = os.getenv("NERKH_API_KEY", "YOUR_API_KEY_HERE")
NERKH_API_URL = "https://api.nerkh.io/v1/prices/json/all"

def get_gold_price() -> str:
    """دریافت قیمت لحظه‌ای انواع طلا از nerkh.io"""
    try:
        params = {"x-api-key": NERKH_API_KEY}  # ← طبق مستندات، x-api-key
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # ساختار پاسخ طبق مستندات: data.prices.gold
            prices = data.get("data", {}).get("prices", {})
            gold_data = prices.get("gold", {})
            
            # انواع طلاهای موجود
            gold_types = ["GOLD18K", "GOLD24K", "SEKE_EMAMI", "SEKE_BAHAR", "OUNCE"]
            result = "💰 **قیمت طلا:**\n"
            found = False
            for gold_type in gold_types:
                if gold_type in gold_data:
                    found = True
                    price = gold_data[gold_type].get("current", "نامشخص")
                    update_time = gold_data[gold_type].get("update", "")
                    result += f"• {gold_type}: {price:,} تومان" if price != "نامشخص" else f"• {gold_type}: {price}"
                    if update_time:
                        result += f" (🕐 {update_time})"
                    result += "\n"
            
            if not found:
                return "⚠️ اطلاعات طلا در دسترس نیست."
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
            prices = data.get("data", {}).get("prices", {})
            currency_data = prices.get("currency", {})
            usd_data = currency_data.get("USD", {})
            
            price = usd_data.get("current", "نامشخص")
            update_time = usd_data.get("update", "")
            
            result = f"💵 **قیمت دلار آمریکا:**\n"
            if price != "نامشخص":
                result += f"{price:,} تومان"
            else:
                result += f"{price}"
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
