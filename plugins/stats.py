import html
import io
import json
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)


def _flink_lines(client):
    return [
        f"{idx}.\n"
        f"<b>▸ ʟɪɴᴋ_ɪᴅ -</b> {lid}\n"
        f"<b>▸ ᴍᴏᴅᴇ -</b> {str(data.get('mode', 'always')).capitalize()}\n"
        f"<b>▸ ʟɪɴᴋ -</b> <code>{html.escape(data.get('link', ''), quote=False)}</code>"
        for idx, (lid, data) in enumerate(client.flink_dict.items(), start=1)
    ]


@Client.on_message(filters.command("stats") & filters.private)
async def stats_export(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return

    try:
        users_count = await client.mongodb.total_users()

        if client.fsub_dict:
            channel_lines = []
            for index, (channel_id, data) in enumerate(client.fsub_dict.items(), start=1):
                mode = "ʀᴇQᴜᴇꜱᴛ" if data[2] else "ᴅɪʀᴇᴄᴛ"
                channel_lines.append(
                    f"{index}.\n<b>▸ ɴᴀᴍᴇ</b> - {html.escape(str(data[0]))}\n"
                    f"<b>▸ ᴄʜᴀɴɴᴇʟ ɪᴅ</b> - <code>{channel_id}</code>\n<b>▸ ᴍᴏᴅᴇ</b> - {mode}"
                )
            fsub_display = "\n\n".join(channel_lines)
        else:
            fsub_display = "ɴᴏ ꜰ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ"

        stats_text = (
            "<b>➲ <u>ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ ꜰᴏʀ ʙᴏᴛ:</u></b>\n\n"
            f"ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ ɪɴ ʙᴏᴛ: {users_count}\n\n"
            "<b>➲ <u>ꜰ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ɴᴀᴍᴇ &amp; ɪᴅ:</u></b>\n\n"
            f"<blockquote>{fsub_display}</blockquote>"
        )
        links = "\n\n".join(_flink_lines(client))
        if links:
            stats_text += f"\n\n<b>➲ <u>ʟɪɴᴋ ꜰ-ꜱᴜʙ:</u></b>\n\n<blockquote>{links}</blockquote>"
        await message.reply_text(stats_text, disable_web_page_preview=True)

        export_notice = await message.reply("<b>Exporting userdata...</b>")

        user_ids = await client.mongodb.full_userbase()
        file = io.BytesIO(json.dumps(user_ids, indent=2).encode("utf-8"))
        file.name = "userdata.json"

        await client.send_document(
            chat_id=message.chat.id,
            document=file,
            file_name="userdata.json",
            caption=f"<b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ</b> : {users_count}",
        )
        await export_notice.delete()
    except Exception as e:
        logger.exception("Error in /stats export")
        return await message.reply(f"✗ <b>Error:</b> <code>{html.escape(str(e))}</code>")
