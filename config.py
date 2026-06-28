import os

# ===== تنظیمات از متغیرهای محیطی =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not all([TELEGRAM_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL, DATABASE_URL]):
    raise ValueError("BOT_TOKEN, FREELLMAPI_KEY, FREELLMAPI_URL and DATABASE_URL must be set")

# ===== تنظیمات داخلی =====
BASE_URL = FREELLMAPI_URL.replace("/v1/chat/completions", "")
SHORT_TERM_MEMORY = 5
MAX_MESSAGE_LENGTH = 4000
