import html

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.errors.pyromod import ListenerTimeout
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import SETTINGS_IMAGE
from plugins.force_sub import register_fsub, unregister_fsub, add_flink, find_flink, parse_bool, link_added_text, channel_added_text

DENY = '❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!'

#===============================================================#

async def edit_msg(message, text, reply_markup=None):
    try:
        if message.photo:
            return await message.edit_caption(text, reply_markup=reply_markup)
        return await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        return None
    except Exception:
        chat_id = message.chat.id
        client = message._client
        try:
            await message.delete()
        except Exception:
            pass
        return await client.send_message(chat_id, text, reply_markup=reply_markup)


def settings_view(client):
    total_fsub = len(client.fsub_dict)
    request_enabled = sum(1 for data in client.fsub_dict.values() if data[2])
    timer_enabled = sum(1 for data in client.fsub_dict.values() if data[3] > 0)
    msg = f"""<blockquote>✦ sᴇᴛᴛɪɴɢs ᴏғ @{client.username}</blockquote>
›› **ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟs:** `{total_fsub}` (ʀᴇǫᴜᴇsᴛ: {request_enabled}, ᴛɪᴍᴇʀ: {timer_enabled})
›› **ʟɪɴᴋ ꜰꜱᴜʙ:** `{len(client.flink_dict)}`
›› **ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ:** `{client.auto_del}`
›› **ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ:** `{"✓ ᴛʀᴜᴇ" if client.protect else "✗ ꜰᴀʟsᴇ"}`
›› **sʜᴏʀᴛɴᴇʀ:** `{"✓ ᴏɴ" if getattr(client, 'shortner_enabled', False) else "✗ ᴏꜰꜰ"}`
"""
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ', 'fsub'), InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ', 'auto_del')],
        [InlineKeyboardButton('ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ', 'protect'), InlineKeyboardButton('sʜᴏʀᴛɴᴇʀ', 'shortner')],
        [InlineKeyboardButton('ᴄʟᴏsᴇ', 'close')]
    ])
    return msg, reply_markup


async def show_main(client, query):
    msg, reply_markup = settings_view(client)
    m = query.message
    if m.photo:
        try:
            return await m.edit_caption(msg, reply_markup=reply_markup)
        except MessageNotModified:
            return
        except Exception:
            pass
    try:
        await m.delete()
    except Exception:
        pass
    await client.send_photo(m.chat.id, SETTINGS_IMAGE, caption=msg, reply_markup=reply_markup)

#===============================================================#

@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    if message.from_user.id not in client.admins:
        return
    msg, reply_markup = settings_view(client)
    await message.reply_photo(SETTINGS_IMAGE, caption=msg, reply_markup=reply_markup)

#===============================================================#

@Client.on_callback_query(filters.regex("^settings$"))
async def settings(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    await query.answer()
    await show_main(client, query)

#===============================================================#

def build_protect_panel(client):
    is_on = client.protect
    on_label = f"{'🟢' if is_on else '○'} On"
    off_label = f"{'🟢' if not is_on else '○'} Off"
    text = (
        "<b>➲ ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ</b>\n\n"
        "<i>_ᴡʜᴇɴ ᴏɴ, ᴜꜱᴇʀꜱ ᴡᴏɴ'ᴛ ʙᴇ ᴀʙʟᴇ ᴛᴏ ꜰᴏʀᴡᴀʀᴅ ᴏʀ ꜱᴀᴠᴇ ꜰɪʟᴇꜱ ꜱᴇɴᴛ ʙʏ ᴛʜᴇ ʙᴏᴛ_</i>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(on_label, "set_protect_on"),
            InlineKeyboardButton(off_label, "set_protect_off"),
        ],
        [InlineKeyboardButton("◂ ʙᴀᴄᴋ", "settings")],
    ])
    return text, markup


@Client.on_callback_query(filters.regex("^protect$"))
async def protect(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    text, markup = build_protect_panel(client)
    await edit_msg(query.message, text, markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^set_protect_(on|off)$"))
async def protect_toggle(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    value = query.data.endswith("_on")
    client.protect = value
    await client.mongodb.set_setting("protect", value)
    text, markup = build_protect_panel(client)
    await edit_msg(query.message, text, markup)
    await query.answer(f"Protect Content {'enabled' if value else 'disabled'}")

#===============================================================#

@Client.on_callback_query(filters.regex("^auto_del$"))
async def auto_del(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    back = InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", "settings")]])
    await edit_msg(
        query.message,
        "<b>➲ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴛɪᴍᴇʀ:</b> {client.auto_del}\n\n"
        "<i>_ᴇɴᴛᴇʀ ɴᴇᴡ ɪɴᴛᴇɢᴇʀ ᴠᴀʟᴜᴇ ᴏꜰ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ, ᴋᴇᴇᴘ 0 ᴛᴏ ᴅɪꜱᴀʙʟᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ "
        "ᴀɴᴅ ᴡᴀɪᴛ ꜰᴏʀ 120 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ ᴛᴏ ʙᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!_</i>",
    )
    await query.answer()
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
    except ListenerTimeout:
        text = "<b>😕 ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ʏᴏᴜ ᴅɪᴅɴ'ᴛ ᴀᴅᴅ ᴀɴʏ ᴛɪᴍᴇ ᴠᴀʟᴜᴇ. ꜱᴇᴀꜱᴏɴ ᴛɪᴍᴇᴅ ᴏᴜᴛ_</i>"
        return await edit_msg(query.message, text, back)
    try:
        value = int(res.text.strip())
    except ValueError:
        text = "<b>😵‍💫 ɪɴᴠᴀʟɪᴅ ᴠᴀʟᴜᴇ.</b> ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ɪɴᴛᴇɢᴇʀ"
        return await edit_msg(query.message, text, back)
    if value != -1:
        client.auto_del = max(value, 0)
        await client.mongodb.set_setting("auto_del", client.auto_del)
    await show_main(client, query)

#===============================================================#

def flink_lines(client):
    return [
        f"<b>▸ ʟɪɴᴋ_ɪᴅ -</b> {lid}\n"
        f"<b>▸ ᴍᴏᴅᴇ -</b> {str(data.get('mode', 'always')).capitalize()}\n"
        f"<b>▸ ʟɪɴᴋ -</b> <code>{html.escape(data.get('link', ''), quote=False)}</code>"
        for lid, data in client.flink_dict.items()
    ]


def build_fsub_panel(client):
    real = [f"• {d[0]} (<code>{cid}</code>)" for cid, d in client.fsub_dict.items() if cid not in client.fake_fsub]
    fake = [f"• {d[0]} (<code>{cid}</code>)" for cid, d in client.fsub_dict.items() if cid in client.fake_fsub]
    text = (
        "<b>➲ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</b>\n"
        "──────────────────\n\n"
        "<b>☰ ʀᴇᴀʟ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʟɪꜱᴛ:</b>\n" + ("\n".join(real) if real else "_No Channel added yet_") + "\n\n"
        "<b>☰ ꜰᴀᴋᴇ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʟɪꜱᴛ:</b>\n" + ("\n".join(fake) if fake else "_No Channel added yet_") + "\n\n"
        "<b>☰ ʟɪɴᴋ ꜰꜱᴜʙ ʟɪꜱᴛ:</b>\n" + ("<blockquote>" + "\n\n".join(flink_lines(client)) + "</blockquote>" if client.flink_dict else "_No Link added yet_")
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ", "add_fsub"),
            InlineKeyboardButton("ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ", "rm_fsub"),
        ],
        [InlineKeyboardButton("◂ ʙᴀᴄᴋ", "settings")],
    ])
    return text, markup


async def process_fsub_add(client, args):
    if not args:
        return "<b>Invalid format</b>"
    try:
        if args[0].lower().startswith(("http://", "https://")):
            if len(args) > 2:
                return "<b>Invalid format</b>"
            mode = args[1].lower() if len(args) == 2 else "always"
            lid = await add_flink(client, args[0], mode)
            return link_added_text(lid, mode, args[0])
        fake = args[-1].lower() == "x"
        if fake:
            args = args[:-1]
        if len(args) != 3:
            return "<b>Invalid format</b>"
        channel_id_raw, mode_raw, timer_raw = args
        try:
            channel_id = int(channel_id_raw)
        except ValueError:
            return "<b>Invalid channel ID</b>"
        if mode_raw.lower() not in ("yes", "no"):
            return "<b>Mode must be yes or no</b>"
        request = parse_bool(mode_raw)
        if not timer_raw.isdigit():
            return "<b>Timer must be a non-negative integer</b>"
        timer = int(timer_raw)
        name = await register_fsub(client, channel_id, request, timer, fake)
    except Exception as e:
        return f"<b>Error:</b> <code>{html.escape(str(e))}</code>"
    return channel_added_text(name, channel_id, request, timer, fake)


async def process_fsub_remove(client, raw):
    lid = find_flink(client, raw)
    if lid:
        await client.mongodb.remove_flink(lid)
        client.flink_dict.pop(lid, None)
        return f"<b>✅ Link F-Sub Removed:</b> {lid}"
    try:
        channel_id = int(raw.strip())
    except ValueError:
        return "<b>Invalid channel ID</b>"
    if channel_id not in client.fsub_dict:
        return "<b>This channel isn't in the Force-Sub list</b>"
    name = client.fsub_dict[channel_id][0]
    await unregister_fsub(client, channel_id)
    return (
        "<b>✅ ꜰ-ꜱᴜʙ ʀᴇᴍᴏᴠᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {html.escape(name)}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>"
    )


@Client.on_callback_query(filters.regex("^fsub$"))
async def fsub(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    text, markup = build_fsub_panel(client)
    await edit_msg(query.message, text, markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^add_fsub$"))
async def add_fsub(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    await edit_msg(
        query.message,
        "<b>Q. ʜᴏᴡ ᴛᴏ ᴀᴅᴅ ᴀ ᴄʜᴀɴɴᴇʟ?</b>\n\n"
        "ꜰɪʀꜱᴛ ꜱᴇɴᴅ ᴍᴇ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴅᴀᴛᴀ ɪɴ ᴛʜɪꜱ ꜰᴏʀᴍᴀᴛ:\n\n"
        "» {channel_id} yes/no Timer\n\n"
        "ᴀᴅᴅ X ᴀꜰᴛᴇʀ ᴛʜᴇ ᴛɪᴍᴇʀ ᴛᴏ ᴍᴀᴋᴇ ɪᴛ ᴀ ꜰᴀᴋᴇ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ\n\n"
        "ʟɪɴᴋ ᴏɴʟʏ: » {link} always/once\n\n"
        "<blockquote expandable><b><i>_ʜᴇʀᴇ ʏᴇꜱ ᴍᴇᴀɴꜱ ʀᴇQᴜᴇꜱᴛ ᴍᴏᴅᴇ ᴀɴᴅ ɴᴏ ᴍᴇᴀɴꜱ ᴅɪʀᴇᴄᴛ ᴍᴏᴅᴇ."
        " ɪɴ ʀᴇQᴜᴇꜱᴛ ᴍᴏᴅᴇ ᴜꜱᴇʀ ꜱᴇɴᴅ ʀᴇQᴜᴇꜱᴛ ɪɴ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʙᴜᴛ ɪɴ ᴅɪʀᴄᴛ ᴍᴏᴅᴇ ᴛʜᴇʏ ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ ᴅɪʀᴇᴄᴛʟʏ."
        "ᴀɴᴅ ᴛɪᴍᴇʀ ɪꜱ ᴜꜱᴇ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀᴄᴄᴇꜱꜱɪʙʟᴇ ʟɪɴᴋ ꜰᴏʀ ᴛʜᴀᴛ ᴘᴀʀᴛɪᴄᴜʟᴀʀ ᴛɪᴍᴇ ᴘᴇʀɪᴏᴅ, ᴀꜰᴛᴇʀ ᴛʜᴀᴛ ʟɪɴᴋ ᴡɪʟʟ ᴇxᴘɪʀᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ,"
        "ᴛᴏ ᴋᴇᴇᴘ ʟɪɴᴋ ɴᴏɴ ᴇxᴘɪʀʏ ʏᴏᴜ ᴄᴀɴ ᴘᴜᴛ 0 ᴀꜱ ᴛɪᴍᴇʀ ᴠᴀʟᴜᴇ_</i></b></blockquote>",
    )
    await query.answer()
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
        text = await process_fsub_add(client, res.text.split())
    except ListenerTimeout:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ꜱᴇᴀꜱᴏɴ ᴄᴀɴᴄᴇʟʟᴇᴅ ʙᴇᴄᴀᴜꜱᴇ ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    await edit_msg(query.message, text, InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", "fsub")]]))


@Client.on_callback_query(filters.regex("^rm_fsub$"))
async def rm_fsub(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    await edit_msg(
        query.message,
        "<b>➲ ʀᴇᴍᴏᴠᴇ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ</b>\n\n"
        "<i>ꜱᴇɴᴅ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ_</i>",
    )
    await query.answer()
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
        text = await process_fsub_remove(client, res.text.strip())
    except ListenerTimeout:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ꜱᴇᴀꜱᴏɴ ᴄᴀɴᴄᴇʟʟᴇᴅ ʙᴇᴄᴀᴜꜱᴇ ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    await edit_msg(query.message, text, InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", "fsub")]]))

    
