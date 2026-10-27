import asyncio
import requests
import random
import string
from config import SHORT_URL, SHORT_API, MESSAGES
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors.pyromod import ListenerTimeout

# ✅ In-memory cache
shortened_urls_cache = {}

def generate_random_alphanumeric():
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(8))

def get_short(url, client):

    # Check if shortner is enabled
    shortner_enabled = getattr(client, 'shortner_enabled', True)
    if not shortner_enabled:
        return url  # Return original URL if shortner is disabled

    # Step 2: Check cache
    if url in shortened_urls_cache:
        return shortened_urls_cache[url]

    try:
        alias = generate_random_alphanumeric()
        # Use dynamic shortner settings from client if available
        short_url = getattr(client, 'short_url', SHORT_URL)
        short_api = getattr(client, 'short_api', SHORT_API)
        
        api_url = f"https://{short_url}/api?api={short_api}&url={url}&alias={alias}"
        response = requests.get(api_url)
        rjson = response.json()

        if rjson.get("status") == "success" and response.status_code == 200:
            short_url = rjson.get("shortenedUrl", url)
            shortened_urls_cache[url] = short_url
            return short_url
    except Exception as e:
        print(f"[Shortener Error] {e}")

    return url  # fallback

#===============================================================#

DENY = '❌ ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ!'


def build_shortner_panel(client):
    enabled = getattr(client, 'shortner_enabled', True)
    short_url = getattr(client, 'short_url', SHORT_URL) or "Not set"
    short_api = getattr(client, 'short_api', SHORT_API) or "Not set"
    tutorial_link = getattr(client, 'tutorial_link', "") or "Not set"
    enabled_text = "ᴇɴᴀʙʟᴇᴅ" if enabled else "ᴅɪꜱᴀʙʟᴇᴅ"
    toggle_label = "ᴏꜰꜰ" if enabled else "ᴏɴ"
    text = (
        "<b>➲ <u>ꜱʜᴏʀᴛɴᴇʀ ꜱᴇᴛᴛɪɴɢꜱ</u></b>\n"
        "──────────────────\n"
        f"<blockquote><b>▸ ꜱᴛᴀᴛᴜꜱ:</b> {enabled_text}\n"
        f"<b>▸ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ:</b> {short_url}\n"
        f"<b>▸ ꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ:</b> {short_api}\n"
        f"<b>▸ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ:</b> {tutorial_link}</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{toggle_label} ꜱʜᴏʀᴛɴᴇʀ", "toggle_shortner"),
            InlineKeyboardButton("ꜱᴇᴛ ᴜʀʟ/ᴀᴘɪ", "add_shortner"),
        ],
        [
            InlineKeyboardButton("ꜱᴇᴛ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ", "set_tutorial_link"),
            InlineKeyboardButton("ᴛᴇꜱᴛ ꜱʜᴏʀᴛɴᴇʀ", "test_shortner"),
        ],
        [InlineKeyboardButton("◂ ʙᴀᴄᴋ", "settings")],
    ])
    return text, markup


BACK = InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", "shortner")]])


@Client.on_callback_query(filters.regex("^shortner$"))
async def shortner_callback(client, query):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    from plugins.settings import edit_msg
    text, markup = build_shortner_panel(client)
    await edit_msg(query.message, text, markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^toggle_shortner$"))
async def toggle_shortner(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    from plugins.settings import edit_msg
    value = not getattr(client, 'shortner_enabled', True)
    client.shortner_enabled = value
    await client.mongodb.set_shortner_status(value)
    text, markup = build_shortner_panel(client)
    await edit_msg(query.message, text, markup)
    await query.answer(f"Shortener {'enabled' if value else 'disabled'}")


@Client.on_callback_query(filters.regex("^add_shortner$"))
async def add_shortner(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    from plugins.settings import edit_msg
    await edit_msg(
        query.message,
        "<b>➲ ꜱᴇᴛ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ/ᴀᴘɪ</b>\n\n"
        "<i>_ꜱᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴜʀʟ ᴀɴᴅ ᴀᴘɪ ᴋᴇʏ ɪɴ ᴛʜɪꜱ ꜰᴏʀᴍᴀᴛ, ᴡᴀɪᴛ ꜰᴏʀ 60 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ_</i>\n\n"
        "<b>ꜰᴏʀᴍᴀᴛ:</b> url api\n"
        "<b>ᴇxᴀᴍᴘʟᴇ:</b> inshorturl.com 9435xxxxxxxxxxxxxxxx",
    )
    await query.answer()
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
    except ListenerTimeout:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
        return await edit_msg(query.message, text, BACK)
    parts = res.text.strip().split()
    if len(parts) >= 2:
        new_url = parts[0].replace("https://", "").replace("http://", "").replace("/", "")
        new_api = " ".join(parts[1:])
        if new_url and "." in new_url and new_api:
            client.short_url = new_url
            client.short_api = new_api
            shortened_urls_cache.clear()
            await client.mongodb.update_shortner_setting('short_url', new_url)
            await client.mongodb.update_shortner_setting('short_api', new_api)
            text = f"<b>ꜱʜᴏʀᴛɴᴇʀ ᴜᴘᴅᴀᴛᴇᴅ!</b>\n\n<b>ᴜʀʟ:</b> `{new_url}`\n<b>ᴀᴘɪ:</b> `{new_api[:20]}...`"
        else:
            text = "<b>ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ! ᴄʜᴇᴄᴋ ᴜʀʟ ᴀɴᴅ ᴀᴘɪ ᴋᴇʏ.</b>"
    else:
        text = "<b>ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ! ᴜꜱᴇ:</b> url api"
    await edit_msg(query.message, text, BACK)


@Client.on_callback_query(filters.regex("^set_tutorial_link$"))
async def set_tutorial_link(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    from plugins.settings import edit_msg
    await edit_msg(
        query.message,
        "<b>➲ ꜱᴇᴛ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ</b>\n\n"
        "<i>_ꜱᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ, ᴡᴀɪᴛ ꜰᴏʀ 60 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ_</i>\n\n"
        "<b>ᴇxᴀᴍᴘʟᴇ:</b> https://t.me/How_to_Download_9999999",
    )
    await query.answer()
    try:
        res = await client.listen(user_id=query.from_user.id, filters=filters.text, timeout=60)
    except ListenerTimeout:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
        return await edit_msg(query.message, text, BACK)
    new_link = res.text.strip()
    if new_link.startswith(("https://", "http://")):
        client.tutorial_link = new_link
        await client.mongodb.update_shortner_setting('tutorial_link', new_link)
        text = "<b>ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ ᴜᴘᴅᴀᴛᴇᴅ!</b>"
    else:
        text = "<b>ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ! ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ https:// ᴏʀ http://</b>"
    await edit_msg(query.message, text, BACK)


@Client.on_callback_query(filters.regex("^test_shortner$"))
async def test_shortner(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        return await query.answer(DENY, show_alert=True)
    from plugins.settings import edit_msg
    await query.answer()
    await edit_msg(query.message, "<b>🔄 ᴛᴇꜱᴛɪɴɢ ꜱʜᴏʀᴛɴᴇʀ...</b>")
    short_url = getattr(client, 'short_url', SHORT_URL)
    short_api = getattr(client, 'short_api', SHORT_API)
    if not short_url or not short_api:
        text = "<b>❌ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ/ᴀᴘɪ ɴᴏᴛ ꜱᴇᴛ ʏᴇᴛ!</b>"
    else:
        try:
            api_url = f"https://{short_url}/api?api={short_api}&url=https://google.com&alias={generate_random_alphanumeric()}"
            response = await asyncio.to_thread(requests.get, api_url, timeout=10)
            rjson = response.json()
            if response.status_code == 200 and rjson.get("status") == "success":
                text = (
                    "<b>✅ ꜱʜᴏʀᴛɴᴇʀ ᴛᴇꜱᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n"
                    f"<b>ꜱʜᴏʀᴛ ᴜʀʟ:</b> `{rjson.get('shortenedUrl', '')}`"
                )
            else:
                text = (
                    "<b>❌ Shortner Test Failed!</b>\n\n"
                    f"<b>ᴇʀʀᴏʀ:</b> {rjson.get('message', 'Unknown error')}"
                )
        except Exception as e:
            text = f"<b>❌ Shortner Test Failed</b>\n\n<b>Error:</b> {e}"
    await edit_msg(query.message, text, BACK)

