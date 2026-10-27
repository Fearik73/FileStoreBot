from html import escape

from pyrogram import Client, filters
from pyrogram.types import Message

from helper.updater import update_from_upstream


@Client.on_message(filters.command("update") & filters.private)
async def cmd_update(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    status_msg = await message.reply("♻️ Checking for updates...")
    status, text = await update_from_upstream()
    if status == "updated":
        text = f"✅ <b>Updated</b>\n<pre>{escape(text)}</pre>\nRestart the bot to apply new commits"
    elif status == "uptodate":
        text = f"✅ {escape(text)}"
    else:
        text = f"❌ <b>Update failed</b>\n<pre>{escape(text)}</pre>"
    await status_msg.edit_text(text)
