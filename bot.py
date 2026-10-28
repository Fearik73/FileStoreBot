from pyrogram import Client
import os
import time
from config import LOGGER, ADMIN_IDS, SHORT_URL, SHORT_API, SHORT_TUT
from helper import MongoDB
from plugins.restart import RESTART_FILE, notify_restart


class Bot(Client):
    def __init__(self, session, workers, db, token, messages, db_uri, db_name, api_id, api_hash):
        super().__init__(
            name=session,
            api_hash=api_hash,
            api_id=api_id,
            plugins={
                "root": "plugins"
            },
            workers=workers,
            bot_token=token
        )
        self.LOGGER = LOGGER
        self.name = session
        self.db = db
        self.fsub_dict = {}
        self.admins = list(ADMIN_IDS)
        self.messages = messages
        self.auto_del = 0
        self.shortner_enabled = False
        self.protect = True
        self.mongodb = MongoDB(db_uri, db_name)
        self.req_channels = []
        self.flink_dict = {}
        self.fake_fsub = set()
    
    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        
        try:
            await self.mongodb.migrate_legacy()
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(f"Legacy data migration failed: {e}")

        # Load dynamically added fsub channels from database
        try:
            db_fsub_channels = await self.mongodb.get_fsub_channels()
            for channel_id_str, channel_data in db_fsub_channels.items():
                channel_id = int(channel_id_str)
                try:
                    chat = await self.get_chat(channel_id)
                    name = chat.title
                    # Update name in case it changed
                    channel_data[0] = name
                    if channel_data[3] == 0:
                        try:
                            new_link = await self.create_chat_invite_link(channel_id, creates_join_request=channel_data[2])
                            channel_data[1] = new_link.invite_link
                            await self.mongodb.add_fsub_channel(channel_id, channel_data)
                        except Exception as e:
                            self.LOGGER(__name__, self.name).warning(f"Could not refresh invite link for {channel_id}: {e}")
                    self.fsub_dict[channel_id] = channel_data
                    if channel_data[2]:  # if request is True
                        self.req_channels.append(channel_id)
                except Exception as e:
                    self.LOGGER(__name__, self.name).warning(f"Could not load dynamic fsub channel {channel_id}: {e}")
                    # Remove invalid channel from database
                    await self.mongodb.remove_fsub_channel(channel_id)
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(f"Error loading dynamic fsub channels: {e}")
            
        await self.mongodb.set_channels(self.req_channels)

        try:
            self.fake_fsub = {c for c in await self.mongodb.get_fake_channels() if c in self.fsub_dict}
            self.flink_dict = await self.mongodb.get_all_flinks()
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(f"Error loading link/fake fsub: {e}")
        
        try:
            self.protect = await self.mongodb.get_setting("protect", True)
            self.auto_del = await self.mongodb.get_setting("auto_del", 0)
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(f"Error loading bot settings: {e}")

        # Load shortner settings from database
        try:
            shortner_settings = await self.mongodb.get_shortner_settings()
            self.short_url = shortner_settings.get('short_url', SHORT_URL)
            self.short_api = shortner_settings.get('short_api', SHORT_API)
            self.tutorial_link = shortner_settings.get('tutorial_link', SHORT_TUT)
            self.shortner_enabled = shortner_settings.get('enabled', False)
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(f"Error loading shortner settings: {e}")
            # Set defaults from config if loading fails
            self.short_url = SHORT_URL
            self.short_api = SHORT_API
            self.tutorial_link = SHORT_TUT
            self.shortner_enabled = False
        
        self.LOGGER(__name__, self.name).info("Bot Started!!")
        
        self.username = usr_bot_me.username
        self.start_time = time.time()

        if os.path.exists(RESTART_FILE):
            await notify_restart(self)
        else:
            for admin_id in self.admins:
                try:
                    await self.send_message(chat_id=admin_id, text="<b>Bot is running now</b>")
                except Exception as e:
                    self.LOGGER(__name__, self.name).warning(f"Failed to send restart notification to {admin_id}: {e}")
    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__, self.name).info("Bot stopped.")




        
