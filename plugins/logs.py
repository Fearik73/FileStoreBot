import os

from pyrogram import Client, filters
from pyrogram.types import Message

from config import LOG_FILE_NAME


@Client.on_message(filters.command("logs") & filters.private)
async def logs_handler(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    if not os.path.exists(LOG_FILE_NAME) or os.path.getsize(LOG_FILE_NAME) == 0:
        return await message.reply("<b>No logs found</b>")
    try:
        await message.reply_document(LOG_FILE_NAME)
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Failed to send log file: {e}")
        await message.reply("<b>Failed to send logs</b>")
