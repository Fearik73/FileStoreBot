import asyncio
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, Forbidden, FloodWait
from datetime import datetime, timedelta
from pyrogram import errors

#===============================================================#

def parse_payload(payload):
    parts = payload.split("_")
    kind = parts[0].lower()
    if kind == "single" and len(parts) >= 3:
        return [int(parts[-1])]
    if kind == "batch" and len(parts) >= 3:
        first, last = int(parts[1]), int(parts[2])
        return list(range(first, last + 1)) if first <= last else list(range(first, last - 1, -1))
    raise ValueError("bad payload")

#===============================================================#

async def send_with_photo(client, chat_id, photo, text, reply_markup=None, **kwargs):
    if photo:
        try:
            return await client.send_photo(chat_id, photo, caption=text, reply_markup=reply_markup, **kwargs)
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Photo failed, sending text only: {e}")
    return await client.send_message(chat_id, text, reply_markup=reply_markup, **kwargs)

#===============================================================#

async def get_messages(client, message_ids):
    messages = []
    total_messages = 0
    while total_messages != len(message_ids):
        chunk = message_ids[total_messages:total_messages + 200]
        try:
            msgs = await client.get_messages(client.db, chunk)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msgs = await client.get_messages(client.db, chunk)
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error getting messages: {e}")
            msgs = []
        total_messages += len(chunk)
        messages.extend(msg for msg in msgs if msg is not None and not msg.empty)
    return messages

#===============================================================#

def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    hmm = len(time_list)
    for x in range(hmm):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time

#===============================================================#

async def is_bot_admin(client, channel_id):
    try:
        bot = await client.get_chat_member(channel_id, "me")
        if bot.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            if bot.privileges:
                required_rights = ["can_invite_users", "can_delete_messages"]
                missing_rights = [right for right in required_rights if not getattr(bot.privileges, right, False)]
                if missing_rights:
                    return False, f"Bot is missing the following rights: {', '.join(missing_rights)}"
            return True, None
        return False, "Bot is not an admin in the channel."
    except errors.ChatAdminRequired:
        return False, "Bot lacks perminsion to access admin information in this channel."
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

#===============================================================#

async def check_subscription(client, user_id):
    """Enhanced subscription check with better request channel handling."""
    statuses = {}

    # Ensure user exists in database
    if not await client.mongodb.present_user(user_id):
        await client.mongodb.add_user(user_id)

    for channel_id, (channel_name, channel_link, request, timer) in client.fsub_dict.items():
        try:
            # Get actual membership status first
            user = await client.get_chat_member(channel_id, user_id)
            actual_status = user.status
            
            # If user is already a member, admin, or owner
            if actual_status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}:
                await client.mongodb.update_fsub_status(user_id, channel_id, "joined")
                await client.mongodb.add_channel_user(channel_id, user_id)
                
                # If there was a pending join request, mark it as approved
                if request and await client.mongodb.has_submitted_join_request(user_id, channel_id):
                    await client.mongodb.update_join_request_status(user_id, channel_id, "approved")
                
                statuses[channel_id] = actual_status
                continue
            
            # User is not a member - check if they left after being approved  
            if request:
                # For request channels, check if user has submitted a request
                has_request = await client.mongodb.has_submitted_join_request(user_id, channel_id)
                if has_request:
                    # User has submitted request but not yet a member
                    request_status = await client.mongodb.get_join_request_status(user_id, channel_id)
                    
                    if request_status == "approved":
                        # Request was approved but user still not in channel
                        # This means user might have left after approval - force them to rejoin
                        await client.mongodb.update_fsub_status(user_id, channel_id, "left")
                        await client.mongodb.remove_join_request(user_id, channel_id)
                        statuses[channel_id] = ChatMemberStatus.BANNED
                    else:
                        # Request is still pending, allow user to proceed
                        await client.mongodb.update_fsub_status(user_id, channel_id, "request_submitted")
                        statuses[channel_id] = ChatMemberStatus.MEMBER  # Treat as subscribed for request channels
                else:
                    # No request submitted yet for request channel
                    await client.mongodb.update_fsub_status(user_id, channel_id, "not_requested")
                    statuses[channel_id] = ChatMemberStatus.BANNED
            else:
                # Regular channel (not request), user must be a member
                await client.mongodb.update_fsub_status(user_id, channel_id, "left")
                await client.mongodb.remove_channel_user(channel_id, user_id)
                statuses[channel_id] = ChatMemberStatus.BANNED
                
        except UserNotParticipant:
            # User is not in the channel
            await client.mongodb.update_fsub_status(user_id, channel_id, "left")
            await client.mongodb.remove_channel_user(channel_id, user_id)
            
            if request:
                # For request channels, check if user has submitted a request
                has_request = await client.mongodb.has_submitted_join_request(user_id, channel_id)
                if has_request:
                    # User has submitted request but not in channel - still allow access for request channels
                    await client.mongodb.update_fsub_status(user_id, channel_id, "request_submitted")
                    statuses[channel_id] = ChatMemberStatus.MEMBER  # Treat as subscribed for request channels
                else:
                    # No request submitted yet
                    await client.mongodb.update_fsub_status(user_id, channel_id, "not_requested")
                    statuses[channel_id] = ChatMemberStatus.BANNED
            else:
                # Regular channel, user must join
                statuses[channel_id] = ChatMemberStatus.BANNED
                
        except Forbidden:
            client.LOGGER(__name__, client.name).warning(f"Bot lacks permission for {channel_name}.")
            statuses[channel_id] = None
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error checking {channel_name}: {e}")
            statuses[channel_id] = None

    return statuses

#===============================================================#

ACTIVE = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

#===============================================================#

def force_sub(func):
    """Decorator to enforce force subscription before executing a command."""
    async def wrapper(client: Client, message: Message):
        if not client.fsub_dict and not client.flink_dict:
            return await func(client, message)
        msg = await message.reply("<b>ᴡᴀɪᴛ ᴀ sᴇᴄᴏɴᴅ.....</b>")

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
        subscribed = {cid: (status in ACTIVE or status is None) for cid, status in statuses.items()}

        real_ok = all(ok for cid, ok in subscribed.items() if cid not in client.fake_fsub)
        fake_ok = all(ok for cid, ok in subscribed.items() if cid in client.fake_fsub)

        pending_links = []
        if consider_fake:
            for lid, data in list(client.flink_dict.items()):
                if data.get("mode") == "once":
                    try:
                        if await client.mongodb.has_flink_seen(lid, user_id):
                            continue
                    except Exception as e:
                        client.LOGGER(__name__, client.name).warning(f"Error checking link fsub seen {lid}: {e}")
                pending_links.append(lid)

        if real_ok and (not consider_fake or fake_ok) and not pending_links:
            await msg.delete()
            if is_retry:
                message.command = [message.command[0], original_payload] if original_payload else [message.command[0]]
            return await func(client, message)

        buttons = []
        numbers = {key: i for i, key in enumerate([*client.fsub_dict, *client.flink_dict], start=1)}
        channels_message = f"{client.messages.get('FSUB', '')}\n\n"

        for channel_id, (channel_name, channel_link, request, timer) in client.fsub_dict.items():
            if channel_id in client.fake_fsub and not consider_fake:
                continue
            if subscribed.get(channel_id, True):
                continue
            if timer > 0:
                expire_time = datetime.now() + timedelta(minutes=timer)
                try:
                    invite = await client.create_chat_invite_link(
                        chat_id=channel_id,
                        expire_date=expire_time,
                        creates_join_request=request
                    )
                    channel_link = invite.invite_link
                except Exception as e:
                    client.LOGGER(__name__, client.name).warning(f"Error creating invite link for {channel_name}: {e}")
            buttons.append(InlineKeyboardButton(f"Channel {numbers[channel_id]:02d}", url=channel_link))

        for lid in pending_links:
            buttons.append(InlineKeyboardButton(f"Channel {numbers[lid]:02d}", url=client.flink_dict[lid]["link"]))

        retry_payload = f"retry_{original_payload}" if original_payload else "retry"
        buttons.append(InlineKeyboardButton("Try Again", url=f"https://t.me/{client.username}?start={retry_payload}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

        buttons_markup = InlineKeyboardMarkup(rows)

        try:
            await msg.delete()
        except Exception:
            pass
        await send_with_photo(client, message.chat.id, client.messages.get('FSUB_PHOTO', ''), channels_message, buttons_markup)

        for lid in pending_links:
            if client.flink_dict.get(lid, {}).get("mode") == "once":
                try:
                    await client.mongodb.mark_flink_seen(lid, user_id)
                except Exception as e:
                    client.LOGGER(__name__, client.name).warning(f"Error marking link fsub seen {lid}: {e}")

    return wrapper

#===============================================================#

#Time conversion for auto delete timer
def convert_time(duration_seconds: int) -> str:
    periods = [
        ('Yᴇᴀʀ', 60 * 60 * 24 * 365),
        ('Mᴏɴᴛʜ', 60 * 60 * 24 * 30),
        ('Day', 60 * 60 * 24),
        ('Hour', 60 * 60),
        ('Minute', 60),
        ('Second', 1)
    ]

    parts = []
    for period_name, period_seconds in periods:
        if duration_seconds >= period_seconds:
            num_periods = duration_seconds // period_seconds
            duration_seconds %= period_seconds
            parts.append(f"{num_periods} {period_name}{'s' if num_periods > 1 else ''}")

    if len(parts) == 0:
        return "0 Sᴇᴄᴏɴᴅ"
    elif len(parts) == 1:
        return parts[0]
    else:
        return ', '.join(parts[:-1]) +' ᴀɴᴅ '+ parts[-1]

#===============================================================#
#.........Auto Delete Functions.......#
#===============================================================#

async def batch_auto_del_notification(messages, delay_time, chat_id, client):
    if not messages:
        return

    notification_msg = await client.send_message(
        chat_id=chat_id,
        text=f"<blockquote><b>This File is deleting automatically in {convert_time(delay_time)}. Forward in your Saved Messages..!</b></blockquote>"
    )

    await asyncio.sleep(delay_time)

    for msg in messages:
        try:
            await msg.delete()
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error deleting message {getattr(msg, 'id', 'Unknown')}: {e}")

    try:
        await notification_msg.edit_text("<b><i>💬 The Previous Files Has Been Deleted</i></b>")
    except Exception as e:
        client.LOGGER(__name__, client.name).warning(f"Error updating notification message: {e}")

        
