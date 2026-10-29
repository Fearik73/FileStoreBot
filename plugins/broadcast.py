import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, ChannelInvalid, PeerIdInvalid, ChatWriteForbidden, ChannelPrivate, ChatAdminRequired, UserIsBot
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import BROADCAST_EFFECT_ID

logger = logging.getLogger(__name__)

PROGRESS_EDIT_INTERVAL = 4

_active = {}


def _cancel_markup(cmd_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"bc_cancel_{cmd_id}")]])


def _progress_text(done: int, total: int, successful: int, blocked: int, deleted: int, unsuccessful: int, range_label: str = None, retrying: bool = False) -> str:
    if retrying:
        head = "ʀᴇᴛʀʏɪɴɢ ꜰᴀɪʟᴇᴅ..."
    else:
        head = "ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ʀᴀɴɢᴇ..." if range_label else "ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ..."
    rng = f"<b>ʀᴀɴɢᴇ :</b> {range_label}\n" if range_label else ""
    return (
        f"<blockquote><b>📢 {head}</b></blockquote>\n"
        + rng +
        f"<b>ᴘʀᴏᴄᴇꜱꜱᴇᴅ :</b> {done}/{total}\n"
        f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {successful}\n"
        f"<b>ʙʟᴏᴄᴋᴇᴅ :</b> {blocked}\n"
        f"<b>ᴅᴇʟᴇᴛᴇᴅ :</b> {deleted}\n"
        f"<b>ᴜɴꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {unsuccessful}"
    )


def _final_text(total: int, successful: int, blocked: int, deleted: int, unsuccessful: int, range_label: str = None, next_start: str = None, head: str = "ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ") -> str:
    rng = f"<b>ʀᴀɴɢᴇ :</b> {range_label}\n" if range_label else ""
    nxt = f"\n<b>ɴᴇxᴛ ꜱᴛᴀʀᴛ :</b> {next_start}" if next_start else ""
    return (
        f"<blockquote><b>{head}</b></blockquote>\n"
        + rng +
        f"<b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ :</b> {total}\n"
        f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {successful}\n"
        f"<b>ʙʟᴏᴄᴋᴇᴅ :</b> {blocked}\n"
        f"<b>ᴅᴇʟᴇᴛᴇᴅ :</b> {deleted}\n"
        f"<b>ᴜɴꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {unsuccessful}"
        + nxt
    )


async def _send_one(client: Client, chat_id: int, broadcast_msg: Message, pin: bool) -> str:
    for _ in range(2):
        try:
            sent = await broadcast_msg.copy(chat_id, reply_markup=broadcast_msg.reply_markup)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except UserIsBlocked:
            return "blocked"
        except (InputUserDeactivated, ChannelInvalid, PeerIdInvalid):
            return "deleted"
        except (ChatWriteForbidden, ChannelPrivate, ChatAdminRequired, UserIsBot):
            return "skip"
        except Exception:
            logger.exception("Failed to broadcast to chat_id=%s", chat_id)
            return "failed"
        if pin and sent:
            try:
                await client.pin_chat_message(chat_id=chat_id, message_id=sent.id, both_sides=True)
            except Exception:
                logger.exception("Failed to pin broadcast message in chat_id=%s", chat_id)
        return "ok"
    return "failed"


async def _send_done(client: Client, cmd_msg: Message, text: str):
    try:
        await client.send_message(
            cmd_msg.chat.id, text,
            reply_to_message_id=cmd_msg.id,
            message_effect_id=BROADCAST_EFFECT_ID,
        )
    except Exception:
        logger.exception("Failed to send completion message with effect")
        try:
            await cmd_msg.reply(text, quote=True)
        except Exception:
            logger.exception("Failed to send completion message")


async def _run_broadcast(client: Client, cmd_msg: Message, status_msg: Message, broadcast_msg: Message, pin: bool = False, user_ids: list = None, range_label: str = None, next_start: str = None, range_start: int = None):
    if user_ids is None:
        user_ids = await client.mongodb.full_userbase()
    total = len(user_ids)
    done = successful = blocked = deleted = unsuccessful = 0
    last_edit = 0.0
    failed = []
    key = (cmd_msg.chat.id, cmd_msg.id)
    state = {"cancel": False}
    _active[key] = state
    markup = _cancel_markup(cmd_msg.id)

    async def _update_progress(force: bool = False, retrying: bool = False):
        nonlocal last_edit
        now = time.monotonic()
        if not force and (now - last_edit) < PROGRESS_EDIT_INTERVAL:
            return
        last_edit = now
        try:
            await status_msg.edit(
                _progress_text(done, total, successful, blocked, deleted, unsuccessful, range_label, retrying),
                reply_markup=markup,
            )
        except Exception:
            pass

    try:
        for chat_id in user_ids:
            if state["cancel"]:
                break
            if not isinstance(chat_id, int) or chat_id <= 0:
                unsuccessful += 1
                done += 1
                await _update_progress()
                continue
            try:
                result = await _send_one(client, chat_id, broadcast_msg, pin)
            except Exception:
                logger.exception("Unexpected broadcast error for chat_id=%s", chat_id)
                result = "failed"
            if result == "ok":
                successful += 1
            elif result == "blocked":
                blocked += 1
            elif result == "deleted":
                deleted += 1
            elif result == "skip":
                unsuccessful += 1
            else:
                unsuccessful += 1
                failed.append(chat_id)
            done += 1
            await _update_progress()

        if failed and not state["cancel"]:
            await _update_progress(force=True, retrying=True)
            for chat_id in failed:
                if state["cancel"]:
                    break
                try:
                    result = await _send_one(client, chat_id, broadcast_msg, pin)
                except Exception:
                    logger.exception("Unexpected broadcast retry error for chat_id=%s", chat_id)
                    result = "failed"
                if result == "ok":
                    unsuccessful -= 1
                    successful += 1
                elif result == "blocked":
                    unsuccessful -= 1
                    blocked += 1
                elif result == "deleted":
                    unsuccessful -= 1
                    deleted += 1
                await _update_progress(retrying=True)
    finally:
        _active.pop(key, None)

    if state["cancel"]:
        resume = str(range_start + done) if range_start is not None else None
        try:
            await status_msg.edit(_final_text(total, successful, blocked, deleted, unsuccessful, range_label, resume, head="ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ"))
        except Exception:
            logger.exception("Failed to edit cancelled broadcast status")
        return

    try:
        await status_msg.edit("<blockquote><b>ʙʀᴏᴀᴅᴄᴀꜱᴛ ꜰɪɴɪꜱʜᴇᴅ</b></blockquote>")
    except Exception:
        pass
    await _send_done(client, cmd_msg, _final_text(total, successful, blocked, deleted, unsuccessful, range_label, next_start))


async def _require_reply(message: Message) -> bool:
    if message.reply_to_message:
        return True
    warn = await message.reply("<b>❗Reply to a message to broadcast it.</b>")
    await asyncio.sleep(8)
    await warn.delete()
    return False


async def _launch(client: Client, message: Message, pin: bool, intro: str, **kwargs):
    status_msg = await message.reply(intro, quote=True, reply_markup=_cancel_markup(message.id))
    await _run_broadcast(client, message, status_msg, message.reply_to_message, pin=pin, **kwargs)


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    if not await _require_reply(message):
        return
    await _launch(client, message, False, "<blockquote><i>Broadcasting message.. this will take some time</i></blockquote>")


@Client.on_message(filters.private & filters.command("pbroadcast"))
async def pin_broadcast_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    if not await _require_reply(message):
        return
    await _launch(client, message, True, "<blockquote><i>Broadcasting message.. this will take some time</i></blockquote>")


@Client.on_message(filters.private & filters.command("brange"))
async def range_broadcast_command(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    if not await _require_reply(message):
        return
    try:
        start, count = int(message.command[1]), int(message.command[2])
        if start < 1 or count < 1:
            raise ValueError
    except (IndexError, ValueError):
        warn = await message.reply("<b>❗Usage:</b> <code>/brange start count</code>")
        await asyncio.sleep(8)
        await warn.delete()
        return

    total_db = await client.mongodb.total_users()
    if start > total_db:
        warn = await message.reply(f"<b>❗Start {start} is beyond total users ({total_db}).</b>")
        await asyncio.sleep(8)
        await warn.delete()
        return

    user_ids = await client.mongodb.full_userbase_range(start, count)
    end = start + len(user_ids) - 1
    range_label = f"{start} → {end}"
    next_start = str(end + 1) if end < total_db else "ᴇɴᴅ ᴏꜰ ʟɪꜱᴛ"

    await _launch(
        client, message, False,
        f"<blockquote><i>Broadcasting range {range_label}.. this will take some time</i></blockquote>",
        user_ids=user_ids, range_label=range_label, next_start=next_start, range_start=start,
    )


@Client.on_callback_query(filters.regex(r"^bc_cancel_(\d+)$"))
async def broadcast_cancel_callback(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        await query.answer("Not allowed", show_alert=True)
        return
    cmd_id = int(query.matches[0].group(1))
    if (query.message.chat.id, cmd_id) not in _active:
        await query.answer("Broadcast already finished", show_alert=True)
        return
    await query.answer()
    await query.message.reply(
        "<b>Really you want to stop this process?</b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes", callback_data=f"bc_yes_{cmd_id}"),
            InlineKeyboardButton("No", callback_data="bc_no"),
        ]]),
    )


@Client.on_callback_query(filters.regex(r"^bc_yes_(\d+)$"))
async def broadcast_stop_callback(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        await query.answer("Not allowed", show_alert=True)
        return
    cmd_id = int(query.matches[0].group(1))
    state = _active.get((query.message.chat.id, cmd_id))
    if state is None:
        await query.answer("Broadcast already finished", show_alert=True)
    else:
        state["cancel"] = True
        await query.answer("Stopping broadcast...")
    try:
        await query.message.delete()
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^bc_no$"))
async def broadcast_keep_callback(client: Client, query: CallbackQuery):
    if query.from_user.id not in client.admins:
        await query.answer("Not allowed", show_alert=True)
        return
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass


@Client.on_message(filters.private & filters.command("users"))
async def user_count(client: Client, message: Message):
    if message.from_user.id not in client.admins:
        return
    total = await client.mongodb.total_users()
    await message.reply(f"<b>{total} Users are using this bot currently!</b>")
