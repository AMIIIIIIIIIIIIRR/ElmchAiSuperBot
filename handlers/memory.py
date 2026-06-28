from telegram import Update
from telegram.ext import ContextTypes
from database import save_memory, get_memories, clear_memories, delete_memory

async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متنی را برای ذخیره وارد کنید.\nمثال: /remember نام من علی است"
        )
        return
    await save_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ یادداشت ذخیره شد:\n\n📝 {memory_text}")

async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    if not memories:
        await update.message.reply_text("📭 هیچ یادداشتی ذخیره نشده است.")
        return
    reply = "📚 یادداشت‌های ذخیره‌شده:\n\n" + "\n".join(
        f"{i + 1}. {m}" for i, m in enumerate(memories)
    )
    await update.message.reply_text(reply)

async def forget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_text = " ".join(context.args)
    if not memory_text:
        await update.message.reply_text(
            "❌ لطفاً متن یادداشت را برای حذف وارد کنید.\nمثال: /forget نام من علی است"
        )
        return
    await delete_memory(user_id, memory_text)
    await update.message.reply_text(f"✅ یادداشت حذف شد:\n\n📝 {memory_text}")

async def clear_memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await clear_memories(user_id)
    await update.message.reply_text("🧹 همه‌ی یادداشت‌های شما پاک شدند.")

async def clear_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import clear_history
    user_id = str(update.effective_user.id)
    await clear_history(user_id)
    await update.message.reply_text("🧹 حافظه‌ی کوتاه‌مدت پاک شد!\n\n💡 یادداشت‌های بلندمدت شما همچنان ذخیره شده‌اند.")
