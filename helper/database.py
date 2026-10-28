import motor.motor_asyncio
from datetime import datetime
from pymongo import UpdateOne, ReturnDocument

from config import FSUB_COLLECTION, REQUEST_COLLECTION, SETTINGS_COLLECTION, USERS_COLLECTION

USER_FILTER = {"_id": {"$type": ["int", "long"], "$ne": 1}}
REQ_TYPE = {"$in": [None, "request"]}


def _status_id(channel_id, user_id):
    return f"status:{channel_id}:{user_id}"


def _seen_id(lid, user_id):
    return f"seen:{lid}:{user_id}"


class MongoDB:
    _instances = {}

    def __new__(cls, uri: str, db_name: str):
        if (uri, db_name) not in cls._instances:
            instance = super().__new__(cls)
            instance.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            instance.db = instance.client[db_name]
            instance.user_data = instance.db[USERS_COLLECTION]
            instance.fsub_data = instance.db[FSUB_COLLECTION]
            instance.settings_data = instance.db[SETTINGS_COLLECTION]
            instance.request_sub = instance.db[REQUEST_COLLECTION]
            cls._instances[(uri, db_name)] = instance
        return cls._instances[(uri, db_name)]

    async def migrate_legacy(self):
        moves = [("fsub_channels", self.fsub_data), ("fake_fsub", self.fsub_data), ("shortner_settings", self.settings_data)]
        for doc_id, target in moves:
            if target.name == self.user_data.name:
                continue
            doc = await self.user_data.find_one({"_id": doc_id})
            if doc:
                if not await target.find_one({"_id": doc_id}):
                    await target.insert_one(doc)
                await self.user_data.delete_one({"_id": doc_id})
        if self.fsub_data.name != self.user_data.name:
            await self.user_data.delete_one({"_id": 1})
        await self._migrate_extra_collections()

    async def _drain(self, name, target, build):
        ops = []
        async for doc in self.db[name].find():
            ops.extend(build(doc))
            if len(ops) >= 1000:
                await target.bulk_write(ops, ordered=False)
                ops = []
        if ops:
            await target.bulk_write(ops, ordered=False)
        await self.db[name].drop()

    async def _migrate_extra_collections(self):
        try:
            names = set(await self.db.list_collection_names())
        except Exception:
            return

        def flink(doc):
            data = {k: v for k, v in doc.items() if k != "_id"}
            return [UpdateOne({"_id": doc["_id"]}, {"$set": {**data, "type": "link"}}, upsert=True)]

        def seen(doc):
            lid, uid = doc.get("lid"), doc.get("user_id")
            if lid is None or uid is None:
                return []
            return [UpdateOne({"_id": _seen_id(lid, uid)}, {"$set": {"type": "seen", "lid": lid, "user_id": uid}}, upsert=True)]

        def status(doc):
            cid, uid = doc.get("channel_id"), doc.get("user_id")
            if cid is None or uid is None:
                return []
            data = {k: v for k, v in doc.items() if k != "_id"}
            return [UpdateOne({"_id": _status_id(cid, uid)}, {"$set": {**data, "type": "status"}}, upsert=True)]

        def members(doc):
            cid = doc["_id"]
            return [
                UpdateOne({"_id": _status_id(cid, uid)}, {"$set": {"type": "status", "user_id": uid, "channel_id": cid, "member": True}}, upsert=True)
                for uid in doc.get("users", [])
            ]

        for name, target, build in (
            ("flinks", self.fsub_data, flink),
            ("flink_seen", self.request_sub, seen),
            ("fsub_status", self.request_sub, status),
            ("channels", self.request_sub, members),
        ):
            if name in names:
                try:
                    await self._drain(name, target, build)
                except Exception as e:
                    print(f"Migration of '{name}' failed, will retry on next start: {e}")

    async def set_channels(self, channels: list[int]):
        await self.fsub_data.update_one(
            {"_id": "req_channels"},
            {"$set": {"channels": channels}},
            upsert=True
        )

    async def _set_member(self, channel_id: int, user_id: int, member: bool):
        await self.request_sub.update_one(
            {"_id": _status_id(channel_id, user_id)},
            {"$set": {"type": "status", "user_id": user_id, "channel_id": channel_id, "member": member}},
            upsert=True
        )

    async def add_channel_user(self, channel_id: int, user_id: int):
        await self._set_member(channel_id, user_id, True)

    async def remove_channel_user(self, channel_id: int, user_id: int):
        await self._set_member(channel_id, user_id, False)

    # USER FUNCTIONS

    async def present_user(self, user_id: int) -> bool:
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def _next_uid(self) -> int:
        key = {"_id": "uid_counter"}
        if not await self.settings_data.find_one(key, {"_id": 1}):
            top = await self.user_data.find_one({**USER_FILTER, "uid": {"$type": "number"}}, {"uid": 1}, sort=[("uid", -1)])
            await self.settings_data.update_one(key, {"$setOnInsert": {"seq": top["uid"] if top else 0}}, upsert=True)
        doc = await self.settings_data.find_one_and_update(key, {"$inc": {"seq": 1}}, return_document=ReturnDocument.AFTER)
        return doc["seq"]

    async def add_user(self, user):
        if await self.user_data.find_one({"_id": user.id}, {"_id": 1}):
            return
        await self.user_data.update_one(
            {"_id": user.id},
            {"$setOnInsert": {
                "username": user.username,
                "name": f"{user.first_name} {user.last_name}",
                "uid": await self._next_uid(),
            }},
            upsert=True
        )

    async def full_userbase(self) -> list[int]:
        cursor = self.user_data.find(USER_FILTER).sort("_id", 1)
        return [doc['_id'] async for doc in cursor]

    async def full_userbase_range(self, start: int, count: int) -> list[int]:
        cursor = self.user_data.find(USER_FILTER).sort("_id", 1).skip(start - 1).limit(count)
        return [doc['_id'] async for doc in cursor]

    async def total_users(self) -> int:
        return await self.user_data.count_documents(USER_FILTER)

    # FSUB CHANNELS FUNCTIONS

    async def set_fsub_channels(self, fsub_data: dict):
        await self.fsub_data.update_one(
            {"_id": "fsub_channels"},
            {"$set": {"channels": fsub_data}},
            upsert=True
        )

    async def get_fsub_channels(self) -> dict:
        data = await self.fsub_data.find_one({"_id": "fsub_channels"})
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
        data = await self.fsub_data.find_one({"_id": "fake_fsub"})
        return data.get("channels", []) if data else []

    async def set_fake_channels(self, channels: list[int]):
        await self.fsub_data.update_one(
            {"_id": "fake_fsub"},
            {"$set": {"channels": channels}},
            upsert=True
        )

    # LINK FSUB FUNCTIONS

    async def get_all_flinks(self) -> dict:
        return {doc["_id"]: {k: v for k, v in doc.items() if k not in ("_id", "type")} async for doc in self.fsub_data.find({"type": "link"})}

    async def add_flink(self, lid: str, data: dict):
        await self.fsub_data.update_one({"_id": lid}, {"$set": {**data, "type": "link"}}, upsert=True)

    async def remove_flink(self, lid: str):
        await self.fsub_data.delete_one({"_id": lid, "type": "link"})
        await self.request_sub.delete_many({"type": "seen", "lid": lid})

    async def has_flink_seen(self, lid: str, user_id: int) -> bool:
        return await self.request_sub.find_one({"_id": _seen_id(lid, user_id)}, {"_id": 1}) is not None

    async def mark_flink_seen(self, lid: str, user_id: int):
        await self.request_sub.update_one(
            {"_id": _seen_id(lid, user_id)},
            {"$set": {"type": "seen", "lid": lid, "user_id": user_id}},
            upsert=True
        )

    # SHORTNER SETTINGS FUNCTIONS

    async def set_shortner_settings(self, shortner_data: dict):
        await self.settings_data.update_one(
            {"_id": "shortner_settings"},
            {"$set": {"settings": shortner_data}},
            upsert=True
        )

    async def get_shortner_settings(self) -> dict:
        data = await self.settings_data.find_one({"_id": "shortner_settings"})
        return data.get("settings", {}) if data else {}

    async def update_shortner_setting(self, key: str, value: str):
        current_data = await self.get_shortner_settings()
        current_data[key] = value
        await self.set_shortner_settings(current_data)

    async def set_shortner_status(self, enabled: bool):
        await self.update_shortner_setting('enabled', enabled)

    # BOT SETTINGS FUNCTIONS

    async def get_setting(self, key: str, default):
        data = await self.settings_data.find_one({"_id": "bot_settings"})
        return data.get(key, default) if data else default

    async def set_setting(self, key: str, value):
        await self.settings_data.update_one(
            {"_id": "bot_settings"},
            {"$set": {key: value}},
            upsert=True
        )

    # FSUB STATUS FUNCTIONS

    async def update_fsub_status(self, user_id: int, channel_id: int, status: str):
        await self.request_sub.update_one(
            {"_id": _status_id(channel_id, user_id)},
            {"$set": {"type": "status", "user_id": user_id, "channel_id": channel_id, "status": status, "last_updated": datetime.now()}},
            upsert=True
        )

    # JOIN REQUEST FUNCTIONS

    async def add_join_request(self, user_id: int, channel_id: int):
        await self.request_sub.update_one(
            {"user_id": user_id, "channel_id": channel_id, "type": REQ_TYPE},
            {"$set": {
                "type": "request",
                "status": "pending",
                "submitted_at": datetime.now(),
                "last_updated": datetime.now()
            }},
            upsert=True
        )

    async def update_join_request_status(self, user_id: int, channel_id: int, status: str):
        await self.request_sub.update_one(
            {"user_id": user_id, "channel_id": channel_id, "type": REQ_TYPE},
            {"$set": {"status": status, "last_updated": datetime.now()}}
        )

    async def get_join_request_status(self, user_id: int, channel_id: int) -> str:
        doc = await self.request_sub.find_one({"user_id": user_id, "channel_id": channel_id, "type": REQ_TYPE})
        return doc.get("status") if doc else None

    async def has_submitted_join_request(self, user_id: int, channel_id: int) -> bool:
        doc = await self.request_sub.find_one({"user_id": user_id, "channel_id": channel_id, "type": REQ_TYPE}, {"_id": 1})
        return doc is not None

    async def remove_join_request(self, user_id: int, channel_id: int):
        await self.request_sub.delete_one({"user_id": user_id, "channel_id": channel_id, "type": REQ_TYPE})




    
