from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.pyromod import ListenerTimeout

#===============================================================#

def settings_view(client):
    total_fsub = len(client.fsub_dict)
    request_enabled = sum(1 for data in client.fsub_dict.values() if data[2])
    timer_enabled = sum(1 for data in client.fsub_dict.values() if data[3] > 0)
    msg = f"""<blockquote>✦ sᴇᴛᴛɪɴɢs ᴏғ @{client.username}</blockquote>
›› **ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟs:** `{total_fsub}` (ʀᴇǫᴜᴇsᴛ: {request_enabled}, ᴛɪᴍᴇʀ: {timer_enabled})
›› **ʟɪɴᴋ ꜰꜱᴜʙ:** `{len(client.flink_dict)}`
›› **ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ:** `{client.auto_del}`
›› **ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ:** `{"✓ ᴛʀᴜᴇ" if client.protect else "✗ ꜰᴀʟsᴇ"}`
›› **sʜᴏʀᴛɴᴇʀ:** `{"✓ ᴏɴ" if getattr(client, 'shortner_enabled', True) else "✗ ᴏꜰꜰ"}`
"""
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ', 'fsub'), InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ', 'auto_del')],
        [InlineKeyboardButton('ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ', 'protect'), InlineKeyboardButton('sʜᴏʀᴛɴᴇʀ', 'shortner')],
        [InlineKeyboardButton('ᴄʟᴏsᴇ', 'close')]
    ])
    return msg, reply_markup

#===============================================================#

@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    if message.from_user.id not in client.admins:
        return
    msg, reply_markup = settings_view(client)
    await message.reply(msg, reply_markup=reply_markup)

#===============================================================#

@Client.on_callback_query(filters.regex("^settings$"))
async def settings(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer('❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!', show_alert=True)
    msg, reply_markup = settings_view(client)
    try:
        await query.message.edit_text(msg, reply_markup=reply_markup)
    except Exception:
        await query.message.delete()
        await query.message.reply(msg, reply_markup=reply_markup)

#===============================================================#

@Client.on_callback_query(filters.regex("^fsub$"))
async def fsub(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer('❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!', show_alert=True)
    if client.fsub_dict:
        channel_list = []
        for channel_id, channel_data in client.fsub_dict.items():
            request_status = "✓ ʀᴇǫᴜᴇsᴛ" if channel_data[2] else "✗ ʀᴇǫᴜᴇsᴛ"
            timer_status = f"ᴛɪᴍᴇʀ: {channel_data[3]}ᴍ" if channel_data[3] > 0 else "ᴛɪᴍᴇʀ: ∞"
            fake = " • ꜰᴀᴋᴇ" if channel_id in client.fake_fsub else ""
            channel_list.append(f"• `{channel_data[0]}` (`{channel_id}`) - {request_status}, {timer_status}{fake}")
        channels_display = "\n".join(channel_list)
    else:
        channels_display = "_ɴᴏ ꜰᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴄʜᴀɴɴᴇʟs ᴄᴏɴғɪɢᴜʀᴇᴅ_"

    msg = f"""<blockquote>✦ ꜰᴏʀᴄᴇ sᴜʙsᴄʀɪᴘᴛɪᴏɴ sᴇᴛᴛɪɴɢs</blockquote>
›› **ᴄᴏɴғɪɢᴜʀᴇᴅ ᴄʜᴀɴɴᴇʟs:**
{channels_display}
"""
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('›› ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ', 'add_fsub'), InlineKeyboardButton('›› ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ', 'rm_fsub')],
        [InlineKeyboardButton('‹ ʙᴀᴄᴋ', 'settings')]]
    )
    await query.message.edit_text(msg, reply_markup=reply_markup)

#===============================================================#

@Client.on_callback_query(filters.regex("^protect$"))
async def protect(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer('❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!', show_alert=True)
    client.protect = not client.protect
    await client.mongodb.set_protect(client.protect)
    return await settings(client, query)

#===============================================================#

@Client.on_callback_query(filters.regex("^auto_del$"))
async def auto_del(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer('❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!', show_alert=True)
    back = InlineKeyboardMarkup([[InlineKeyboardButton('◂ ʙᴀᴄᴋ', 'settings')]])
    msg = f"""<blockquote>**Change Auto Delete Time:**</blockquote>
**Current Timer:** `{client.auto_del}`

__Enter new integer value of auto delete timer in seconds, keep 0 to disable auto delete, or wait for 60 second timeout!__
"""
    await query.answer()
    await query.message.edit_text(msg)
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
        timer = res.text.strip()
        if timer.isdigit():
            client.auto_del = int(timer)
            return await query.message.edit_text(f'**Auto Delete timer value changed to {timer} seconds!**', reply_markup=back)
        return await query.message.edit_text("**This is not an integer value!!**", reply_markup=back)
    except ListenerTimeout:
        return await query.message.edit_text("**Timeout, try again!**", reply_markup=back)
        
