import asyncpg
from config import DATABASE_URL

db_pool: asyncpg.Pool | None = None

# ===== مقداردهی اولیه =====
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                user_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                user_id TEXT,
                memory TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ایندکس‌ها برای سرعت بیشتر
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories(user_id)")
    print("✅ دیتابیس PostgreSQL آماده است.")

async def close_db():
    if db_pool:
        await db_pool.close()

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
