from pyrogram import Client, filters
from pyrogram.types import CallbackQuery


@Client.on_callback_query(filters.regex('^close$'))
async def close(client: Client, query: CallbackQuery):
    if not query.message:
        return
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        await query.message.reply_to_message.delete()
    except Exception:
        pass
        
