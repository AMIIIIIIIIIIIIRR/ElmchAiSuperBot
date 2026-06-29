import logging
import requests
import jdatetime
from datetime import datetime
import os
import json

NERKH_API_KEY = os.getenv("NERKH_API_KEY", "YOUR_API_KEY_HERE")
NERKH_API_URL = "https://api.nerkh.io/v1/prices/json/all"

def get_gold_price() -> str:
    try:
        params = {"x-api-key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        # ===== لاگ کامل پاسخ برای دیباگ =====
        logging.info(f"Nerkh API Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Nerkh API Response: {json.dumps(data, indent=2)[:500]}")  # فقط ۵۰۰ کاراکتر اول
        else:
            logging.error(f"Nerkh API Error: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            # بررسی اینکه آیا ساختار پاسخ با مستندات مطابقت دارد
            if "data" in data and "prices" in data["data"]:
                prices = data["data"]["prices"]
                gold_data = prices.get("gold", {})
                
                if gold_data:
                    result = "💰 **قیمت طلا:**\n"
                    gold_types = ["GOLD18K", "GOLD24K", "SEKE_EMAMI", "SEKE_BAHAR", "OUNCE"]
                    found = False
                    for gold_type in gold_types:
                        if gold_type in gold_data:
                            found = True
                            item = gold_data[gold_type]
                            price = item.get("current") or item.get("price")  # کلید ممکن است current یا price باشد
                            update_time = item.get("update", "")
                            result += f"• {gold_type}: {price:,} تومان" if price else f"• {gold_type}: نامشخص"
                            if update_time:
                                result += f" (🕐 {update_time})"
                            result += "\n"
                    if found:
                        return result
                    else:
                        return "⚠️ اطلاعات طلا در دسترس نیست (هیچ نوع طلایی یافت نشد)."
                else:
                    return "⚠️ اطلاعات طلا در دسترس نیست (بخش gold خالی است)."
            else:
                return f"⚠️ ساختار پاسخ نامعتبر است. کلیدهای موجود: {list(data.keys())}"
        else:
            return f"⚠️ خطا در دریافت قیمت طلا (کد {response.status_code})."
    except Exception as e:
        logging.error(f"Gold API error: {e}")
        return "⚠️ خطا در دریافت قیمت طلا. لطفاً بعداً امتحان کنید."

def get_usd_price() -> str:
    try:
        params = {"x-api-key": NERKH_API_KEY}
        response = requests.get(NERKH_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Nerkh API Response (USD): {json.dumps(data, indent=2)[:500]}")
            
            if "data" in data and "prices" in data["data"]:
                prices = data["data"]["prices"]
                currency_data = prices.get("currency", {})
                usd_data = currency_data.get("USD", {})
                
                if usd_data:
                    price = usd_data.get("current") or usd_data.get("price")
                    update_time = usd_data.get("update", "")
                    if price:
                        return f"💵 **قیمت دلار آمریکا:**\n{price:,} تومان" + (f"\n🕐 {update_time}" if update_time else "")
                    else:
                        return f"⚠️ قیمت دلار نامشخص است. داده: {usd_data}"
                else:
                    return "⚠️ اطلاعات دلار در دسترس نیست (USD یافت نشد)."
            else:
                return f"⚠️ ساختار پاسخ نامعتبر است. کلیدهای موجود: {list(data.keys())}"
        else:
            return f"⚠️ خطا در دریافت قیمت دلار (کد {response.status_code})."
    except Exception as e:
        logging.error(f"USD API error: {e}")
        return "⚠️ خطا در دریافت قیمت دلار. لطفاً بعداً امتحان کنید."

def get_today_date() -> str:
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
