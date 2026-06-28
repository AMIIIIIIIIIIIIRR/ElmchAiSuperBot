import logging

async def safe_reply(message, text, **kwargs):
    """اگر Markdown parse خطا داد، بدون parse_mode می‌فرستد."""
    try:
        await message.reply_text(text, **kwargs)
    except Exception as e:
        logging.warning(f"Markdown parse failed, retrying plain: {e}")
        kwargs.pop("parse_mode", None)
        await message.reply_text(text, **kwargs)
