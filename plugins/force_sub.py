import asyncio
import html
import logging
import time
from datetime import datetime, timedelta, timezone

from pyrogram import Client, raw
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, RPCError

from config import FSUB_MESSAGE, FSUB_PHOTO
from database import (
    add_fsub_channel, get_all_fsub_channels, remove_fsub_channel,
    get_join_request_status, update_join_request_status, remove_join_request,
    get_all_flinks, add_flink, remove_flink, has_flink_seen, mark_flink_seen,
)
from helper.messaging import send_msg, safe_reply

logger = logging.getLogger(__name__)


_ACTIVE = (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

_LINK_CHECK_TTL = 60
_link_checked = {}
_link_locks = {}


async def _link_is_valid(client: Client, channel_id: int, link: str, request: bool = False) -> bool:
    try:
        res = await client.invoke(
            raw.functions.messages.GetExportedChatInvite(
                peer=await client.resolve_peer(channel_id),
                link=link,
            )
        )
        invite = res.invite
        admin_id = getattr(invite, "admin_id", None)
        if admin_id is not None and admin_id != client.me.id:
            logger.warning("Fsub link for channel_id=%s was not created by this bot, replacing it", channel_id)
            return False
        if getattr(invite, "revoked", False):
            return False
        exp = getattr(invite, "expire_date", None)
        if exp:
            exp_ts = exp.timestamp() if hasattr(exp, "timestamp") else exp
            if exp_ts < time.time() + 30:
                return False
        limit = getattr(invite, "usage_limit", None)
        if limit and (getattr(invite, "usage", 0) or 0) >= limit:
            return False
        if bool(getattr(invite, "request_needed", False)) != bool(request):
            return False
        return True
    except RPCError as e:
        if getattr(e, "CODE", None) in (420, 500):
            logger.warning("Could not verify invite link for channel_id=%s: %s", channel_id, e)
            return True
        logger.warning("Fsub link for channel_id=%s is not usable by this bot (%s), replacing it", channel_id, e)
        return False
    except Exception as e:
        logger.warning("Could not verify invite link for channel_id=%s: %s", channel_id, e)
        return False


async def _ensure_valid_link(client: Client, channel_id: int, data: dict):
    lock = _link_locks.setdefault(channel_id, asyncio.Lock())
    async with lock:
        link = data.get("link")
        if link and time.monotonic() - _link_checked.get(channel_id, 0) < _LINK_CHECK_TTL:
            return link
        if link and await _link_is_valid(client, channel_id, link, data.get("request", False)):
            _link_checked[channel_id] = time.monotonic()
            return link
        try:
            invite = await client.create_chat_invite_link(
                channel_id, creates_join_request=data.get("request", False)
            )
            link = invite.invite_link
            data["link"] = link
            _link_checked[channel_id] = time.monotonic()
            logger.info("Fsub link refreshed for channel_id=%s", channel_id)
            try:
                await add_fsub_channel(channel_id, {"link": link})
            except Exception:
                logger.exception("Failed to save refreshed fsub link channel_id=%s", channel_id)
        except Exception:
            logger.exception("Error refreshing invite link for channel_id=%s", channel_id)
        return link


async def _request_pending(channel_id: int, user_id: int) -> bool:
    try:
        status = await get_join_request_status(channel_id, user_id)
        if status is None:
            return False
        if status == "approved":
            await remove_join_request(channel_id, user_id)
            return False
        return True
    except Exception:
        logger.exception("Error checking join-request record for channel_id=%s", channel_id)
        return False


async def check_subscription(client: Client, user_id: int) -> dict:
    statuses = {}
    for channel_id, data in list(client.fsub_dict.items()):
        request = data.get("request")
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in _ACTIVE:
                if request:
                    try:
                        await update_join_request_status(channel_id, user_id, "approved", only_if="pending")
                    except Exception:
                        logger.exception("Error marking join request approved channel_id=%s", channel_id)
                statuses[channel_id] = True
            else:
                statuses[channel_id] = await _request_pending(channel_id, user_id) if request else False
        except UserNotParticipant:
            statuses[channel_id] = await _request_pending(channel_id, user_id) if request else False
        except Exception:
            logger.exception("Error checking fsub status for channel_id=%s", channel_id)
            statuses[channel_id] = True
    return statuses


_fsub_load_lock = asyncio.Lock()


async def ensure_fsub_loaded(client: Client):
    if getattr(client, "_fsub_loaded", False):
        return
    if time.monotonic() < getattr(client, "_fsub_retry_after", 0):
        return
    async with _fsub_load_lock:
        if getattr(client, "_fsub_loaded", False):
            return
        ok = True
        try:
            client.fsub_dict = await get_all_fsub_channels()
            logger.info("Loaded %d Fsub channel(s)", len(client.fsub_dict))
        except Exception:
            ok = False
            logger.exception("Failed to load Fsub channels from MongoDB")
        try:
            client.flink_dict = await get_all_flinks()
            logger.info("Loaded %d Link Fsub entr(ies)", len(client.flink_dict))
        except Exception:
            ok = False
            logger.exception("Failed to load Link Fsub from MongoDB")
        if ok:
            client._fsub_loaded = True
        else:
            client._fsub_retry_after = time.monotonic() + 30


def _ordered_entries(client: Client, include_links: bool) -> list:
    entries = [("c", cid, data) for cid, data in client.fsub_dict.items()]
    if include_links:
        entries += [("l", lid, data) for lid, data in client.flink_dict.items()]
    entries.sort(key=lambda e: e[2].get("added_at") or 0)
    return entries


def force_sub(func):
    async def wrapper(client: Client, message: Message):
        await ensure_fsub_loaded(client)
        if not client.fsub_dict and not client.flink_dict:
            return await func(client, message)

        checking_msg = await safe_reply(message, "<b>Checking Subscription.....</b>")
        if checking_msg is None:  # user blocked the bot / deleted account
            return

        raw_payload = message.command[1] if len(message.command) > 1 else None

        is_retry = False
        original_payload = raw_payload
        if raw_payload == "retry":
            is_retry = True
            original_payload = None
        elif raw_payload and raw_payload.startswith("retry_"):
            is_retry = True
            original_payload = raw_payload[len("retry_"):]

        is_file_request = bool(original_payload) and original_payload.lower().startswith(("single_", "batch_"))
        consider_fake = is_file_request and not is_retry

        user_id = message.from_user.id
        statuses = await check_subscription(client, user_id)

        real_statuses = [statuses.get(cid, False) for cid, data in client.fsub_dict.items() if not data.get("fake")]
        fake_statuses = [statuses.get(cid, False) for cid, data in client.fsub_dict.items() if data.get("fake")]

        pending_links = []
        if consider_fake:
            for lid, data in list(client.flink_dict.items()):
                if data.get("mode") == "once":
                    try:
                        if await has_flink_seen(lid, user_id):
                            continue
                    except Exception:
                        logger.exception("Error checking link-fsub seen record for %s", lid)
                pending_links.append(lid)

        if all(real_statuses) and (not consider_fake or all(fake_statuses)) and not pending_links:
            try:
                await checking_msg.delete()
            except Exception:
                pass
            if is_retry:
                message.command = [message.command[0], original_payload] if original_payload else [message.command[0]]
            return await func(client, message)

        entries = [
            e for e in _ordered_entries(client, consider_fake)
            if not (e[0] == "c" and e[2].get("fake") and not consider_fake)
        ]

        buttons_raw = []
        for rank, (kind, key, data) in enumerate(entries, start=1):
            if kind == "l":
                if key not in pending_links:
                    continue
                link = data.get("link")
            else:
                if statuses.get(key, False):
                    continue
                link = data.get("link")
                if data.get("timer", 0) > 0:
                    try:
                        invite = await client.create_chat_invite_link(
                            key,
                            expire_date=datetime.now(timezone.utc) + timedelta(minutes=data["timer"]),
                            creates_join_request=data.get("request", False),
                        )
                        link = invite.invite_link
                    except Exception:
                        logger.exception("Error creating invite link for channel_id=%s", key)
                        link = await _ensure_valid_link(client, key, data)
                else:
                    link = await _ensure_valid_link(client, key, data)

            if not link:
                continue
            buttons_raw.append({"text": f"Channel {rank:02d}", "url": link, "style": "primary"})

        try_again_payload = f"retry_{original_payload}" if original_payload else "retry"
        try_again_link = f"https://t.me/{client.me.username}?start={try_again_payload}"
        buttons_raw.append({"text": "Try Again", "url": try_again_link, "style": "danger"})

        rows = [buttons_raw[i:i + 2] for i in range(0, len(buttons_raw), 2)]
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(b["text"], url=b["url"]) for b in row] for row in rows]
        )

        try:
            await checking_msg.delete()
        except Exception:
            pass

        await send_msg(
            client,
            message.chat.id,
            FSUB_MESSAGE,
            reply_markup=markup,
            photo=FSUB_PHOTO or None,
        )

        for lid in pending_links:
            if client.flink_dict.get(lid, {}).get("mode") == "once":
                try:
                    await mark_flink_seen(lid, user_id)
                except Exception:
                    logger.exception("Failed to mark link-fsub seen for %s", lid)

    return wrapper


def _find_flink(client: Client, raw: str):
    key = raw.strip()
    if key.upper() in client.flink_dict:
        return key.upper()
    for lid, data in client.flink_dict.items():
        if data.get("link") == key:
            return lid
    return None


async def process_flink_add(client: Client, args: list) -> str:
    if not args or len(args) > 2:
        return "<b>Invalid format</b>"

    link = args[0]
    mode = args[1].lower() if len(args) == 2 else "always"

    if not link.lower().startswith(("http://", "https://")):
        return "<b>Invalid link</b>"
    if len(link) > 2048:
        return f"<b>Link too long</b> ({len(link)}/2048)"
    if mode not in ("always", "once"):
        return "<b>Mode must be 'always' or 'once'</b>"

    existing = _find_flink(client, link)
    if existing:
        lid = existing
        data = {k: v for k, v in client.flink_dict[lid].items() if k != "_id"}
        data["mode"] = mode
    else:
        nums = [int(k[1:]) for k in client.flink_dict if k[1:].isdigit()]
        lid = f"L{max(nums, default=0) + 1}"
        data = {"type": "link", "link": link, "mode": mode, "added_at": time.time()}

    try:
        await add_flink(lid, data)
    except Exception:
        logger.exception("Failed to save link fsub %s to MongoDB", lid)

    client.flink_dict[lid] = data

    return (
        "<b>✅ ʟɪɴᴋ ꜰ-ꜱᴜʙ ᴀᴅᴅᴇᴅ</b>\n\n"
        f"<b>▸ ɪᴅ:</b> <code>{lid}</code>\n"
        f"<b>▸ ᴍᴏᴅᴇ:</b> {mode.capitalize()}\n"
        f"<b>▸ ʟɪɴᴋ:</b> <code>{html.escape(link, quote=False)}</code>"
    )


async def process_flink_remove(client: Client, lid: str) -> str:
    try:
        await remove_flink(lid)
    except Exception:
        logger.exception("Failed to remove link fsub %s from MongoDB", lid)

    client.flink_dict.pop(lid, None)
    return f"<b>✅ Link F-Sub Removed:</b> {lid}"


def flink_lines(client: Client, numbered: bool = False) -> list:
    lines = []
    for idx, (lid, data) in enumerate(client.flink_dict.items(), start=1):
        link = data.get("link", "")
        body = (
            f"<b>▸ ʟɪɴᴋ_ɪᴅ -</b> {lid}\n"
            f"<b>▸ ᴍᴏᴅᴇ -</b> {str(data.get('mode', 'always')).capitalize()}\n"
            f"<b>▸ ʟɪɴᴋ -</b> <code>{html.escape(link, quote=False)}</code>"
        )
        lines.append(f"{idx}.\n{body}" if numbered else body)
    return lines


async def process_fsub_add(client: Client, args: list) -> str:
    if not args:
        return "<b>Invalid format</b>"

    if args[0].lower().startswith(("http://", "https://")):
        return await process_flink_add(client, args)

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

    mode = mode_raw.lower()
    if mode == "yes":
        request = True
    elif mode == "no":
        request = False
    else:
        return "<b>Mode must be yes or no</b>"

    if not timer_raw.isdigit():
        return "<b>Timer must be a non-negative integer</b>"
    timer = int(timer_raw)

    try:
        chat, member = await asyncio.gather(
            client.get_chat(channel_id),
            client.get_chat_member(channel_id, "me"),
        )
    except Exception as e:
        return f"<b>Error:</b> <code>{e}</code>"

    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return "<b>I must be an admin in that channel first</b>"

    link = None
    if timer == 0:
        try:
            invite = await client.create_chat_invite_link(channel_id, creates_join_request=request)
            link = invite.invite_link
        except Exception as e:
            return f"<b>Error creating invite link:</b> <code>{e}</code>"

    data = {"name": chat.title, "link": link, "request": request, "timer": timer, "fake": fake}
    old = client.fsub_dict.get(channel_id)
    if old is None:
        data["added_at"] = time.time()
    elif old.get("added_at"):
        data["added_at"] = old["added_at"]

    try:
        await add_fsub_channel(channel_id, data)
    except Exception:
        logger.exception("Failed to save fsub channel_id=%s to MongoDB", channel_id)

    client.fsub_dict[channel_id] = data

    return (
        "<b>✅ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {chat.title}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>\n"
        f"<b>ᴍᴏᴅᴇ:</b> {'Request' if request else 'Direct'}\n"
        f"<b>ᴇxᴘɪʀʏ:</b> {f'{timer}m' if timer > 0 else 'Never'}\n\n"
        + ("<b>❗ᴀᴅᴅᴇᴅ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ ɪɴᴛᴏ ꜰᴀᴋᴇ ꜰ-ꜱᴜʙ ʟɪꜱᴛ</b>" if fake else "")
    )


async def process_fsub_remove(client: Client, channel_id_raw: str) -> str:
    lid = _find_flink(client, channel_id_raw)
    if lid:
        return await process_flink_remove(client, lid)

    try:
        channel_id = int(channel_id_raw.strip())
    except ValueError:
        return "<b>Invalid channel ID</b>"

    if channel_id not in client.fsub_dict:
        return "<b>This channel isn't in the Force-Sub list</b>"

    name = client.fsub_dict[channel_id].get("name", str(channel_id))

    try:
        await remove_fsub_channel(channel_id)
    except Exception:
        logger.exception("Failed to remove fsub channel_id=%s from MongoDB", channel_id)

    client.fsub_dict.pop(channel_id, None)

    return (
        "<b>✅ ꜰ-ꜱᴜʙ ʀᴇᴍᴏᴠᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {name}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>"
    )






    
