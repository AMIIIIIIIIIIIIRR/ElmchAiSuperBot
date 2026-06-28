async def handle_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()
    
    # ===== اگر متن خالی بود =====
    if not text:
        await update.message.reply_text("❌ متن نمی‌تواند خالی باشد. لطفاً دوباره بنویسید.")
        context.user_data.pop("waiting_for", None)  # ← پاک کردن حالت
        return
    
    data_dict = context.user_data.get("reminder_data", {})
    year = data_dict.get("year")
    month = data_dict.get("month")
    day = data_dict.get("day")
    hour = data_dict.get("hour", 0)
    minute = data_dict.get("minute", 0)
    
    # ===== اگر تاریخ ناقص بود =====
    if not year or not month or not day:
        await update.message.reply_text("❌ خطا در دریافت تاریخ. لطفاً دوباره تلاش کنید.")
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("reminder_data", None)
        return
    
    # ===== اگر تاریخ گذشته بود =====
    if not is_future_date(year, month, day, hour, minute):
        await update.message.reply_text(
            "❌ **تاریخ انتخاب‌شده گذشته است!**\n\n"
            f"تاریخ انتخاب‌شده: {format_jalali_datetime(year, month, day, hour, minute)}\n\n"
            "لطفاً دوباره تلاش کنید."
        )
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("reminder_data", None)
        return
    
    # ===== ذخیره یادآوری =====
    remind_at = jalali_to_gregorian(year, month, day, hour, minute)
    now = datetime.now()
    
    job_id = f"reminder_{user_id}_{int(remind_at.timestamp())}"
    reminder_id = await save_reminder(user_id, chat_id, text, remind_at, job_id)
    
    delta = remind_at - now
    context.job_queue.run_once(
        send_reminder,
        when=delta,
        name=job_id,
        data={
            "reminder_id": reminder_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message": text,
            "job_id": job_id
        }
    )
    
    # ===== پاک کردن همه‌ی وضعیت‌ها (موفقیت) =====
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("reminder_data", None)
    context.user_data.pop("reminder_step", None)
    
    await update.message.reply_text(
        f"✅ **یادآوری ثبت شد!**\n\n"
        f"📝 {text}\n"
        f"⏰ {remind_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🆔 شماره: {reminder_id}"
    )
