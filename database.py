import asyncpg
from config import DATABASE_URL
from telegram.ext import Application  # برای type hint

db_pool: asyncpg.Pool | None = None

# ===== مقداردهی اولیه =====
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
        # جدول تاریخچه مکالمه
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                user_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول یادداشت‌های بلندمدت
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                user_id TEXT,
                memory TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول یادآوری‌ها
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
        # ایندکس‌ها برای سرعت بیشتر
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at)")
    print("✅ دیتابیس PostgreSQL آماده است.")

# ===== بستن اتصالات (با پذیرش آرگومان Application) =====
async def close_db(app: Application = None):  # ← آرگومان اضافه شد
    """بستن Pool دیتابیس"""
    if db_pool:
        await db_pool.close()
        print("🔒 اتصالات دیتابیس بسته شد.")

# ===== توابع تاریخچه =====
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

# ===== توابع حافظه‌ی بلندمدت =====
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

# ===== توابع یادآوری =====
async def save_reminder(user_id: str, chat_id: str, message: str, remind_at, job_id: str):
    async with db_pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO reminders (user_id, chat_id, message, remind_at, job_id) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, chat_id, message, remind_at, job_id
        )

async def get_user_reminders(user_id: str):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, message, remind_at, job_id FROM reminders WHERE user_id = $1 ORDER BY remind_at ASC",
            user_id
        )
    return rows

async def delete_reminder(reminder_id: int, user_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM reminders WHERE id = $1 AND user_id = $2",
            reminder_id, user_id
        )

async def get_reminder_by_id(reminder_id: int, user_id: str):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM reminders WHERE id = $1 AND user_id = $2",
            reminder_id, user_id
        )

async def delete_reminder_by_job_id(job_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM reminders WHERE job_id = $1", job_id)
