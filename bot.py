import logging
import requests
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ===== تنظیمات از متغیرهای محیطی =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")

if not TELEGRAM_TOKEN or not FREELLMAPI_KEY or not FREELLMAPI_URL:
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY and FREELLMAPI_URL must be set")

# ===== لیست مدل‌ها (با نام‌های نمایشی) =====
MODELS = {
    "gemini-1.5-pro": "🧠 Gemini 1.5 Pro (پیش‌فرض)",
    "gemini-2.0-flash": "⚡ Gemini 2.0 Flash (سریع)",
    "openrouter/owl-alpha": "🦉 OpenRouter OWL Alpha",
    "llama-3.3-70b": "🦙 Llama 3.3 70B",
    "qwen-2.5-coder": "💻 Qwen 2.5 Coder",
    "mistral-large": "🌊 Mistral Large",
    "auto": "🤖 Auto (انتخاب خودکار)"
}

DEFAULT_MODEL = "gemini-1.5-pro"
MODEL_KEYS = list(MODELS.keys())

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

user_models = {}

# ===== دستور /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_models[user_id] = DEFAULT_MODEL
    
    keyboard = [[InlineKeyboardButton("🧠 انتخاب مدل", callback_data="select_model")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 سلام! من دستیار هوشمند شما هستم.\n"
        f"مدل فعلی: {MODELS.get(user_models.get(user_id, DEFAULT_MODEL), DEFAULT_MODEL)}\n\n"
        f"برای تغییر مدل، روی دکمه زیر کلیک کنید:",
        reply_markup=reply_markup
    )

# ===== دستور /model (لیست مدل‌ها) =====
async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_model = user_models.get(user_id, DEFAULT_MODEL)
    
    keyboard = []
    for key, name in MODELS.items():
        check = "✅ " if key == current_model else ""
        keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"setmodel_{key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📋 لیست مدل‌ها:\n"
        f"مدل فعلی: {MODELS.get(current_model, current_model)}\n\n"
        f"یک مدل را انتخاب کنید:",
        reply_markup=reply_markup
    )

# ===== مدیریت کلیک روی دکمه‌ها =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == "select_model":
        current_model = user_models.get(user_id, DEFAULT_MODEL)
        keyboard = []
        for key, name in MODELS.items():
            check = "✅ " if key == current_model else ""
            keyboard.append([InlineKeyboardButton(f"{check}{name}", callback_data=f"setmodel_{key}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"📋 لیست مدل‌ها:\nمدل فعلی: {MODELS.get(current_model, current_model)}",
            reply_markup=reply_markup
        )
        
    elif query.data.startswith("setmodel_"):
        model_key = query.data.replace("setmodel_", "")
        if model_key in MODELS:
            user_models[user_id] = model_key
            await query.edit_message_text(
                text=f"✅ مدل شما به **{MODELS[model_key]}** تغییر کرد.",
                reply_markup=None
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ مدل شما به **{MODELS[model_key]}** تغییر کرد.\n"
                     f"از این به بعد از این مدل برای پاسخ‌گویی استفاده می‌شود."
            )
        else:
            await query.edit_message_text("❌ مدل نامعتبر است.")

# ===== تابع پاسخ به پیام‌ها =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if user_message.startswith('/'):
        return
    
    if user_id not in user_models:
        user_models[user_id] = DEFAULT_MODEL
    
    selected_model = user_models[user_id]
    
    time.sleep(1)
    
    headers = {
        "Authorization": f"Bearer {FREELLMAPI_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": selected_model,
        "messages": [{"role": "user", "content": user_message}]
    }
    
    try:
        response = requests.post(FREELLMAPI_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            ai_reply = result["choices"][0]["message"]["content"]
            await update.message.reply_text(ai_reply)
        else:
            await update.message.reply_text("❌ خطا در دریافت پاسخ از هوش مصنوعی.")
            
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            # ===== خطای محدودیت =====
            keyboard = [[InlineKeyboardButton("🧠 تغییر مدل", callback_data="select_model")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ مدل **{MODELS.get(selected_model, selected_model)}** به محدودیت درخواست رسیده است.\n\n"
                f"لطفاً یکی از مدل‌های زیر را انتخاب کنید یا روی دکمه کلیک کنید:\n"
                f"{chr(10).join([f'• {name}' for key, name in list(MODELS.items())[:5]])}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"⚠️ خطا در ارتباط با سرور: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ سرور هوش مصنوعی در دسترس نیست. لطفاً بعداً امتحان کنید.")

# ===== تابع اصلی =====
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("model", model_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 ربات روشن شد...")
    application.run_polling()

if __name__ == "__main__":
    main()
