import glob
import os

from pyrogram import Client, filters
from pyrogram.types import Message

from config import LOG_FILE_NAME


def _size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


@Client.on_message(filters.command("logs") & filters.private)
async def logs_handler(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    if not os.path.exists(LOG_FILE_NAME) or os.path.getsize(LOG_FILE_NAME) == 0:
        return await message.reply("<b>No logs found</b>")
    status = await message.reply("<b>ꜰᴇᴛᴄʜɪɴɢ ʟᴏɢꜱ.....</b>")
    try:
        await message.reply_document(LOG_FILE_NAME)
        await status.delete()
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Failed to send log file: {e}")
        await status.edit("<b>Failed to send logs</b>")


@Client.on_message(filters.command(["clearlogs", "clearlog"]) & filters.private)
async def clear_logs_handler(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    status = await message.reply("<b>ᴄʟᴇᴀʀɪɴɢ ʟᴏɢꜱ.....</b>")
    freed = 0
    try:
        for path in glob.glob(f"{LOG_FILE_NAME}.*"):
            try:
                freed += os.path.getsize(path)
                os.remove(path)
            except OSError:
                pass
        if os.path.exists(LOG_FILE_NAME):
            freed += os.path.getsize(LOG_FILE_NAME)
            open(LOG_FILE_NAME, "w").close()
        await status.edit(f"<b>✅ ʟᴏɢꜱ ᴄʟᴇᴀʀᴇᴅ</b>\n\n<b>▸ ꜰʀᴇᴇᴅ:</b> {_size(freed)}")
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Failed to clear logs: {e}")
        await status.edit("<b>Failed to clear logs</b>")
    
