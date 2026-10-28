from pyrogram import Client
import os
import sys
import time
from config import LOGGER, ADMIN_ID, SHORT_URL, SHORT_API, SHORT_TUT
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
        self.owner = ADMIN_ID
        self.fsub_dict = {}
        self.admins = [ADMIN_ID]
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
        
        try:
            db_channel = await self.get_chat(self.db)
            test = await self.send_message(chat_id = db_channel.id, text = "Testing Message by @ProYato")
            await test.delete()
        except Exception as e:
            self.LOGGER(__name__, self.name).warning(e)
            self.LOGGER(__name__, self.name).warning(f"Make Sure bot is Admin in DB Channel, and Double check the database channel Value, Current Value {self.db}")
            self.LOGGER(__name__, self.name).info("\nBot Stopped. Join https://t.me/animes_cruise for support")
            sys.exit()
        self.LOGGER(__name__, self.name).info("Bot Started!!")
        
        self.username = usr_bot_me.username
        self.start_time = time.time()

        if os.path.exists(RESTART_FILE):
            await notify_restart(self)
        else:
            try:
                restart_message = "<b>Bot is running now</b>"
                await self.send_message(chat_id=self.owner, text=restart_message)
            except Exception as e:
                self.LOGGER(__name__, self.name).warning(f"Failed to send restart notification to owner: {e}")
    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__, self.name).info("Bot stopped.")


            
