import html
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.helper_func import is_bot_admin, get_readable_time

#===============================================================#

async def register_fsub(client, channel_id, request, timer, fake=False):
    if channel_id in client.fsub_dict:
        raise Exception("This channel id already exists in force sub list, remove it to change it's configuration!!")
    val, res = await is_bot_admin(client, channel_id)
    if not val:
        raise Exception(res)
    chat = await client.get_chat(channel_id)
    name = chat.title
    if timer > 0:
        data = [name, None, request, timer]
    else:
        chat_link = await client.create_chat_invite_link(channel_id, creates_join_request=request)
        data = [name, chat_link.invite_link, request, timer]
    client.fsub_dict[channel_id] = data

    if request and channel_id not in client.req_channels:
        client.req_channels.append(channel_id)
        await client.mongodb.set_channels(client.req_channels)

    await client.mongodb.add_fsub_channel(channel_id, data)

    if fake:
        client.fake_fsub.add(channel_id)
        await client.mongodb.set_fake_channels(list(client.fake_fsub))
    return name


async def unregister_fsub(client, channel_id):
    if channel_id in client.req_channels:
        client.req_channels.remove(channel_id)
        await client.mongodb.set_channels(client.req_channels)
    client.fsub_dict.pop(channel_id)
    await client.mongodb.remove_fsub_channel(channel_id)
    if channel_id in client.fake_fsub:
        client.fake_fsub.discard(channel_id)
        await client.mongodb.set_fake_channels(list(client.fake_fsub))


def find_flink(client, raw):
    key = raw.strip()
    if key.upper() in client.flink_dict:
        return key.upper()
    for lid, data in client.flink_dict.items():
        if data.get("link") == key:
            return lid
    return None


async def add_flink(client, link, mode="always"):
    if not link.lower().startswith(("http://", "https://")):
        raise Exception("Invalid link")
    if len(link) > 2048:
        raise Exception(f"Link too long ({len(link)}/2048)")
    if mode not in ("always", "once"):
        raise Exception("Mode must be 'always' or 'once'")
    lid = find_flink(client, link)
    if not lid:
        nums = [int(k[1:]) for k in client.flink_dict if k[1:].isdigit()]
        lid = f"L{max(nums, default=0) + 1}"
    data = {"type": "link", "link": link, "mode": mode}
    await client.mongodb.add_flink(lid, data)
    client.flink_dict[lid] = data
    return lid


def link_added_text(lid, mode, link):
    return (
        "<b>✅ ʟɪɴᴋ ꜰ-ꜱᴜʙ ᴀᴅᴅᴇᴅ</b>\n\n"
        f"<b>▸ ɪᴅ:</b> <code>{lid}</code>\n"
        f"<b>▸ ᴍᴏᴅᴇ:</b> {mode.capitalize()}\n"
        f"<b>▸ ʟɪɴᴋ:</b> <code>{html.escape(link, quote=False)}</code>"
    )


def channel_added_text(name, channel_id, request, timer, fake):
    return (
        "<b>✅ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {html.escape(name)}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>\n"
        f"<b>ᴍᴏᴅᴇ:</b> {'Request' if request else 'Direct'}\n"
        f"<b>ᴇxᴘɪʀʏ:</b> {f'{timer}m' if timer > 0 else 'Never'}"
        + ("\n\n<b>❗ᴀᴅᴅᴇᴅ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ ɪɴᴛᴏ ꜰᴀᴋᴇ ꜰ-ꜱᴜʙ ʟɪꜱᴛ</b>" if fake else "")
    )


def parse_bool(value):
    if value.lower() in ('true', 'on', 'yes'):
        return True
    if value.lower() in ('false', 'off', 'no'):
        return False
    raise Exception("Invalid request value or type.")

#===============================================================#

@Client.on_message(filters.command("fsub") & filters.private)
async def fsub_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    args = message.command[1:]
    if len(args) < 2:
        return
    status_msg = await message.reply("<b>Adding Force-Sub Channel.....</b>")
    try:
        if args[0].lower().startswith(("http://", "https://")):
            lid = await add_flink(client, args[0], args[1].lower())
            return await status_msg.edit(link_added_text(lid, args[1].lower(), args[0]), disable_web_page_preview=True)
        fake = args[-1].lower() == 'x'
        if fake:
            args = args[:-1]
        if len(args) != 3:
            raise Exception("Invalid format")
        channel_id = int(args[0])
        timer = args[2]
        if not timer.isdigit():
            raise Exception("Timer must be a non-negative integer")
        name = await register_fsub(client, channel_id, parse_bool(args[1]), int(timer), fake)
        await status_msg.edit(channel_added_text(name, channel_id, parse_bool(args[1]), int(timer), fake))
    except Exception as e:
        await status_msg.edit(f"<b>Error:</b> <code>{html.escape(str(e))}</code>")


@Client.on_message(filters.command("ffsub") & filters.private)
async def ffsub_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    args = message.command[1:]
    if not args or len(args) > 2:
        return
    try:
        mode = args[1].lower() if len(args) == 2 else "always"
        lid = await add_flink(client, args[0], mode)
        await message.reply(link_added_text(lid, mode, args[0]), disable_web_page_preview=True)
    except Exception as e:
        await message.reply(f"<b>Error:</b> <code>{html.escape(str(e))}</code>")


@Client.on_message(filters.command("rmf") & filters.private)
async def rmf_command(client: Client, message: Message):
    if message.from_user.id not in client.admins or len(message.command) != 2:
        return
    raw = message.command[1]
    lid = find_flink(client, raw)
    if lid:
        await client.mongodb.remove_flink(lid)
        client.flink_dict.pop(lid, None)
        return await message.reply(f"<b>✅ Link F-Sub Removed:</b> {lid}")
    try:
        channel_id = int(raw)
    except ValueError:
        return await message.reply("<b>Invalid channel ID</b>")
    if channel_id not in client.fsub_dict:
        return await message.reply("<b>This channel isn't in the Force-Sub list</b>")
    name = client.fsub_dict[channel_id][0]
    await unregister_fsub(client, channel_id)
    await message.reply(f"<b>✅ F-Sub removed</b>\n\n<b>Channel:</b> {html.escape(name)}\n<b>ID:</b> <code>{channel_id}</code>")


@Client.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    start = time.monotonic()
    sent = await message.reply("<b>Pinging.....</b>")
    ping_ms = (time.monotonic() - start) * 1000
    uptime = get_readable_time(int(time.time() - client.start_time))
    users_count = len(await client.mongodb.full_userbase())

    text = (
        "<b>⧉ <u>ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ</u></b>\n\n"
        f"<b>┠ ᴘɪɴɢ:</b> {ping_ms:.2f} ms\n"
        f"<b>┠ ᴜᴘᴛɪᴍᴇ:</b> {uptime}\n"
        f"<b>┠ ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> {users_count}\n\n"
    )
    if not client.fsub_dict:
        text += "<b>⧉ <u>ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</u>:</b>\n<i>No force-sub channels added yet</i>"
    else:
        lines = []
        for idx, (channel_id, (name, _, request, timer)) in enumerate(client.fsub_dict.items(), start=1):
            lines.append(
                f"{idx}. <b>{html.escape(name)}</b> — <code>{channel_id}</code>\n"
                f"<b>▸ ᴛʏᴘᴇ:</b> {'Fake' if channel_id in client.fake_fsub else 'Real'}\n"
                f"<b>▸ ᴍᴏᴅᴇ:</b> {'Request' if request else 'Direct'}\n"
                f"<b>▸ ᴇxᴘɪʀʏ:</b> {f'{timer}m' if timer > 0 else 'Never'}"
            )
        text += "<b>⧉ <u>ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</u>:</b>\n\n<blockquote>" + "\n\n".join(lines) + "</blockquote>"
    if client.flink_dict:
        links = [
            f"<b>▸ ʟɪɴᴋ_ɪᴅ -</b> {lid}\n<b>▸ ᴍᴏᴅᴇ -</b> {str(d.get('mode', 'always')).capitalize()}\n<b>▸ ʟɪɴᴋ -</b> <code>{html.escape(d.get('link', ''), quote=False)}</code>"
            for lid, d in client.flink_dict.items()
        ]
        text += "\n\n<b>⧉ <u>ʟɪɴᴋ ꜰ-ꜱᴜʙ</u>:</b>\n\n<blockquote>" + "\n\n".join(links) + "</blockquote>"
    await sent.edit(text, disable_web_page_preview=True)



    
