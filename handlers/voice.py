import logging
import requests
import os
from telegram import Update
from telegram.ext import ContextTypes

SPEACHES_URL = os.getenv("SPEACHES_URL")
SPEACHES_API_KEY = os.getenv("SPEACHES_API_KEY")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام صوتی و ارسال به Speaches برای تشخیص گفتار"""
    try:
        # دریافت فایل صوتی از تلگرام
        voice = await update.message.voice.get_file()
        file_path = f"voice_{update.effective_user.id}.ogg"
        await voice.download_to_drive(file_path)

        # ارسال پیام به کاربر
        status_msg = await update.message.reply_text("🎤 در حال تشخیص گفتار... لطفاً صبر کنید.")

        # ===== هدر Authorization =====
        headers = {}
        if SPEACHES_API_KEY:
            headers["Authorization"] = f"Bearer {SPEACHES_API_KEY}"

        # ===== ارسال به Speaches =====
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "audio/ogg")}
            data = {
                "model": "whisper-1",  # مدل پیش‌فرض
                "language": "fa",
            }
            response = requests.post(
                SPEACHES_URL,
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )

        # پاک کردن فایل موقت
        if os.path.exists(file_path):
            os.remove(file_path)

        # پردازش پاسخ
        if response.status_code == 200:
            result = response.json()
            transcribed_text = result.get("text", "").strip()

            if transcribed_text:
                await status_msg.edit_text(f"📝 **متن تشخیص‌داده‌شده:**\n\n{transcribed_text}")
            else:
                await status_msg.edit_text("❌ صدایی تشخیص داده نشد. لطفاً واضح‌تر صحبت کنید.")
        else:
            logging.error(f"Speaches error: {response.status_code} - {response.text}")
            await status_msg.edit_text("❌ خطا در تشخیص گفتار. لطفاً بعداً تلاش کنید.")

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏰ زمان تشخیص گفتار به پایان رسید. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logging.error(f"Voice handler error: {e}")
        await update.message.reply_text("❌ خطا در پردازش صدای شما.")
