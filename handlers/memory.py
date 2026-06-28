from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import save_memory, get_memories, clear_memories, delete_memory

# ===== منوی حافظه =====
MEMORY_MENU = [
    [InlineKeyboardButton("📝 ذخیره یادداشت", callback_data="memory_save")],
    [InlineKeyboardButton("📚 مشاهده یادداشت‌ها", callback_data="memory_view")],
    [InlineKeyboardButton("🗑️ حذف یک یادداشت", callback_data="memory_delete")],
    [InlineKeyboardButton("🧹 پاک کردن همه", callback_data="memory_clear")],
    [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_main")],
]

async def show_memory_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    """نمایش منوی حافظه با توضیح"""
    text = """
🧠 **مدیریت حافظه**

📝 **این بخش به شما کمک می‌کند اطلاعات مهم را ذخیره کنید.**

| گزینه | توضیح |
| :--- | :--- |
| 📝 **ذخیره یادداشت** | یک نکته را به خاطر بسپارید |
| 📚 **مشاهده یادداشت‌ها** | همه‌ی نکات ذخیره‌شده را ببینید |
| 🗑️ **حذف یک یادداشت** | یک نکته خاص را حذف کنید |
| 🧹 **پاک کردن همه** | همه‌ی یادداشت‌ها را یک‌جا پاک کنید |

💡 **مثال:** «نام همسرم سارا است» یا «رمز وای‌فای ۱۲۳۴۵۶۷۸ است»
"""
    reply_markup = InlineKeyboardMarkup(MEMORY_MENU)
    
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ===== عملیات‌ها =====
async def memory_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "memory_text"
    await query.edit_message_text(
        "📝 لطفاً **متن یادداشت** را ارسال کنید.\n\n"
        "✏️ هر چیزی که می‌خواهید به خاطر بسپارم را بنویسید.",
        parse_mode="Markdown"
    )

async def memory_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    if not memories:
        await query.edit_message_text("📭 هیچ یادداشتی ذخیره نشده است.")
        return
    reply = "📚 **یادداشت‌های شما:**\n\n"
    for i, mem in enumerate(memories, 1):
        reply += f"{i}. {mem}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی حافظه", callback_data="menu_memory")]]
    await query.edit_message_text(reply, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def memory_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    memories = await get_memories(user_id)
    if not memories:
        await query.edit_message_text("📭 هیچ یادداشتی برای حذف وجود ندارد.")
        return
    buttons = []
    for i, mem in enumerate(memories, 1):
        short = mem[:20] + "..." if len(mem) > 20 else mem
        buttons.append([InlineKeyboardButton(f"{i}. {short}", callback_data=f"delete_mem_{i}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_memory")])
    await query.edit_message_text(
        "🗑️ **کدام یادداشت را حذف می‌خواهید؟**\n\nلطفاً شماره‌ی آن را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def memory_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    index = int(query.data.split("_")[2]) - 1
    memories = await get_memories(user_id)
    if index >= len(memories):
        await query.edit_message_text("❌ شماره نامعتبر است.")
        return
    mem_text = memories[index]
    await delete_memory(user_id, mem_text)
    await query.edit_message_text(f"✅ یادداشت حذف شد:\n\n📝 {mem_text}")

async def memory_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("✅ بله، همه را پاک کن", callback_data="memory_clear_confirm")],
        [InlineKeyboardButton("❌ انصراف", callback_data="menu_memory")],
    ]
    await query.edit_message_text(
        "⚠️ **آیا مطمئن هستید؟**\n\nهمه‌ی یادداشت‌های شما برای همیشه حذف می‌شوند.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def memory_clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    await clear_memories(user_id)
    await query.edit_message_text("🧹 همه‌ی یادداشت‌های شما پاک شدند.")

async def handle_memory_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    await save_memory(user_id, text)
    await update.message.reply_text(f"✅ یادداشت ذخیره شد:\n\n📝 {text}")
    context.user_data.pop("waiting_for", None)
    await show_memory_menu(update, context)
