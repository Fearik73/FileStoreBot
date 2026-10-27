import motor.motor_asyncio
from datetime import datetime, timedelta

USER_FILTER = {"_id": {"$type": ["int", "long"], "$ne": 1}}


class MongoDB:
    _instances = {}

    def __new__(cls, uri: str, db_name: str):
        if (uri, db_name) not in cls._instances:
            instance = super().__new__(cls)
            instance.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            instance.db = instance.client[db_name]
            instance.user_data = instance.db["users"]
            instance.channel_data = instance.db["channels"]
            instance.fsub_status = instance.db['fsub_status']
            instance.request_sub = instance.db['request_sub']
            instance.flinks = instance.db['flinks']
            instance.flink_seen = instance.db['flink_seen']
            cls._instances[(uri, db_name)] = instance
        return cls._instances[(uri, db_name)]

    async def set_channels(self, channels: list[int]):
        await self.user_data.update_one(
            {"_id": 1},
            {"$set": {"channels": channels}},
            upsert=True
        )

    async def get_channels(self) -> list[int]:
        data = await self.user_data.find_one({"_id": 1})
        return data.get("channels", []) if data else []

    async def add_channel_user(self, channel_id: int, user_id: int):
        await self.channel_data.update_one(
            {"_id": channel_id},
            {"$addToSet": {"users": user_id}},
            upsert=True
        )

    async def remove_channel_user(self, channel_id: int, user_id: int):
        await self.channel_data.update_one(
            {"_id": channel_id},
            {"$pull": {"users": user_id}}
        )

    # USER FUNCTIONS

    async def present_user(self, user_id: int) -> bool:
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})

    async def full_userbase(self) -> list[int]:
        cursor = self.user_data.find(USER_FILTER).sort("_id", 1)
        return [doc['_id'] async for doc in cursor]

    async def full_userbase_range(self, start: int, count: int) -> list[int]:
        cursor = self.user_data.find(USER_FILTER).sort("_id", 1).skip(start - 1).limit(count)
        return [doc['_id'] async for doc in cursor]

    async def total_users(self) -> int:
        return await self.user_data.count_documents(USER_FILTER)

    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})

    # FSUB CHANNELS FUNCTIONS

    async def set_fsub_channels(self, fsub_data: dict):
        await self.user_data.update_one(
            {"_id": "fsub_channels"},
            {"$set": {"channels": fsub_data}},
            upsert=True
        )

    async def get_fsub_channels(self) -> dict:
        data = await self.user_data.find_one({"_id": "fsub_channels"})
        return data.get("channels", {}) if data else {}

    async def add_fsub_channel(self, channel_id: int, channel_data: list):
        current_data = await self.get_fsub_channels()
        current_data[str(channel_id)] = channel_data
        await self.set_fsub_channels(current_data)

    async def remove_fsub_channel(self, channel_id: int):
        current_data = await self.get_fsub_channels()
        current_data.pop(str(channel_id), None)
        await self.set_fsub_channels(current_data)

    async def get_fake_channels(self) -> list[int]:
        data = await self.user_data.find_one({"_id": "fake_fsub"})
        return data.get("channels", []) if data else []

    async def set_fake_channels(self, channels: list[int]):
        await self.user_data.update_one(
            {"_id": "fake_fsub"},
            {"$set": {"channels": channels}},
            upsert=True
        )

    # LINK FSUB FUNCTIONS

    async def get_all_flinks(self) -> dict:
        return {doc["_id"]: {k: v for k, v in doc.items() if k != "_id"} async for doc in self.flinks.find()}

    async def add_flink(self, lid: str, data: dict):
        await self.flinks.update_one({"_id": lid}, {"$set": data}, upsert=True)

    async def remove_flink(self, lid: str):
        await self.flinks.delete_one({"_id": lid})
        await self.flink_seen.delete_many({"lid": lid})

    async def has_flink_seen(self, lid: str, user_id: int) -> bool:
        return await self.flink_seen.find_one({"lid": lid, "user_id": user_id}) is not None

    async def mark_flink_seen(self, lid: str, user_id: int):
        await self.flink_seen.update_one({"lid": lid, "user_id": user_id}, {"$set": {"lid": lid, "user_id": user_id}}, upsert=True)

    # SHORTNER SETTINGS FUNCTIONS

    async def set_shortner_settings(self, shortner_data: dict):
        await self.user_data.update_one(
            {"_id": "shortner_settings"},
            {"$set": {"settings": shortner_data}},
            upsert=True
        )

    async def get_shortner_settings(self) -> dict:
        data = await self.user_data.find_one({"_id": "shortner_settings"})
        return data.get("settings", {}) if data else {}

    async def update_shortner_setting(self, key: str, value: str):
        current_data = await self.get_shortner_settings()
        current_data[key] = value
        await self.set_shortner_settings(current_data)

    async def set_shortner_status(self, enabled: bool):
        await self.update_shortner_setting('enabled', enabled)

    # FSUB STATUS FUNCTIONS

    async def update_fsub_status(self, user_id: int, channel_id: int, status: str):
        await self.fsub_status.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$set": {"status": status, "last_updated": datetime.now()}},
            upsert=True
        )

    # JOIN REQUEST FUNCTIONS

    async def add_join_request(self, user_id: int, channel_id: int, request_id: int = None):
        await self.request_sub.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$set": {
                "request_id": request_id,
                "status": "pending",
                "submitted_at": datetime.now(),
                "last_updated": datetime.now()
            }},
            upsert=True
        )

    async def update_join_request_status(self, user_id: int, channel_id: int, status: str):
        await self.request_sub.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$set": {"status": status, "last_updated": datetime.now()}}
        )

    async def get_join_request_status(self, user_id: int, channel_id: int) -> str:
        doc = await self.request_sub.find_one({"user_id": user_id, "channel_id": channel_id})
        return doc.get("status") if doc else None

    async def has_submitted_join_request(self, user_id: int, channel_id: int) -> bool:
        doc = await self.request_sub.find_one({"user_id": user_id, "channel_id": channel_id})
        return doc is not None

    async def remove_join_request(self, user_id: int, channel_id: int):
        await self.request_sub.delete_one({"user_id": user_id, "channel_id": channel_id})
