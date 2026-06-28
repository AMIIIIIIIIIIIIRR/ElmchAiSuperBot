import asyncpg
from config import DATABASE_URL
from telegram.ext import Application  # برای type hint

db_pool: asyncpg.Pool | None = None

# ===== مقداردهی اولیه =====
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
        # ===== جدول تاریخچه مکالمه =====
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                user_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ===== جدول یادداشت‌های بلندمدت =====
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                user_id TEXT,
                memory TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ===== جدول یادآوری‌ها =====
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                chat_id TEXT,
                message TEXT,
                remind_at TIMESTAMP,
                job_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ===== جدول تنظیمات کاربر =====
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                personality TEXT NOT NULL DEFAULT 'default',
                nsfw_accepted BOOLEAN NOT NULL DEFAULT FALSE,
                web_search_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ===== اضافه کردن ستون در صورت عدم وجود (برای دیتابیس‌های قدیمی) =====
        await conn.execute("""
            ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS web_search_enabled BOOLEAN NOT NULL DEFAULT FALSE
        """)

        # ===== ایندکس‌ها =====
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at)")
    
    print("✅ دیتابیس PostgreSQL آماده است.")

async def close_db(app: Application = None):
    if db_pool:
        await db_pool.close()
        print("🔒 اتصالات دیتابیس بسته شد.")

# ============================================================
# ===== تاریخچه مکالمه =====
# ============================================================

async def save_message(user_id: str, role: str, content: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
            user_id, role, content,
        )

async def get_recent_history(user_id: str, limit: int = 5):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM chat_history WHERE user_id = $1 "
            "ORDER BY timestamp DESC LIMIT $2",
            user_id, limit * 2,
        )
    return list(reversed(rows))

async def clear_history(user_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)

# ============================================================
# ===== حافظه بلندمدت (یادداشت‌ها) =====
# ============================================================

async def save_memory(user_id: str, memory: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_memories (user_id, memory) VALUES ($1, $2)",
            user_id, memory,
        )

async def get_memories(user_id: str):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT memory FROM user_memories WHERE user_id = $1 ORDER BY timestamp DESC",
            user_id,
        )
    return [row["memory"] for row in rows]

async def clear_memories(user_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM user_memories WHERE user_id = $1", user_id)

async def delete_memory(user_id: str, memory_text: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_memories WHERE user_id = $1 AND memory = $2",
            user_id, memory_text,
        )

# ============================================================
# ===== یادآوری‌ها =====
# ============================================================

async def save_reminder(user_id: str, chat_id: str, message: str, remind_at, job_id: str):
    async with db_pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO reminders (user_id, chat_id, message, remind_at, job_id) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, chat_id, message, remind_at, job_id
        )

async def get_user_reminders(user_id: str):
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT id, message, remind_at, job_id FROM reminders "
            "WHERE user_id = $1 ORDER BY remind_at ASC",
            user_id,
        )

async def get_reminder_by_id(reminder_id: int, user_id: str):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM reminders WHERE id = $1 AND user_id = $2",
            reminder_id, user_id
        )

async def delete_reminder(reminder_id: int, user_id: str = None):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM reminders WHERE id = $1", reminder_id)

async def get_reminders(user_id: str):
    return await get_user_reminders(user_id)

async def get_all_pending_reminders():
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT id, user_id, chat_id, message, remind_at, job_id FROM reminders"
        )

# ============================================================
# ===== تنظیمات کاربر (شخصیت و جستجوی وب) =====
# ============================================================

async def get_user_personality(user_id: str) -> str:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT personality FROM user_settings WHERE user_id = $1", user_id
        )
    return row["personality"] if row else "default"

async def set_user_personality(user_id: str, personality: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, personality, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET personality = EXCLUDED.personality,
                          updated_at = CURRENT_TIMESTAMP
            """,
            user_id, personality,
        )

async def get_nsfw_accepted(user_id: str) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT nsfw_accepted FROM user_settings WHERE user_id = $1", user_id
        )
    return bool(row["nsfw_accepted"]) if row else False

async def set_nsfw_accepted(user_id: str, accepted: bool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, nsfw_accepted, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET nsfw_accepted = EXCLUDED.nsfw_accepted,
                          updated_at = CURRENT_TIMESTAMP
            """,
            user_id, accepted,
        )

# ============================================================
# ===== جستجوی وب =====
# ============================================================

async def get_web_search_status(user_id: str) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT web_search_enabled FROM user_settings WHERE user_id = $1", user_id
        )
    return bool(row["web_search_enabled"]) if row else False

async def set_web_search_status(user_id: str, enabled: bool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, web_search_enabled, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET web_search_enabled = EXCLUDED.web_search_enabled,
                          updated_at = CURRENT_TIMESTAMP
            """,
            user_id, enabled,
        )
