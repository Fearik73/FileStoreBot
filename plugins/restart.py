import asyncio
import os
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

RESTART_FILE = "restart.txt"


@Client.on_message(filters.command("restart") & filters.private)
async def restart_handler(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    notice = await message.reply("<b>Restarting...</b>")
    try:
        with open(RESTART_FILE, "w") as f:
            f.write(f"{message.chat.id} {notice.id}")
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Failed to write restart marker: {e}")
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)


async def notify_restart(client: Client):
    try:
        with open(RESTART_FILE) as f:
            chat_id, msg_id = map(int, f.read().split())
        os.remove(RESTART_FILE)
        try:
            await client.delete_messages(chat_id, msg_id)
        except Exception:
            pass
        await client.send_message(chat_id, "<b>♻️ Bot restarted Successfully</b>")
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Failed to send restart notification: {e}")
