
import asyncio
from bot import Bot
from pyrogram import compose
from config import *

async def main():
    app = []

    app.append(
        Bot(
            SESSION,
            WORKERS,
            DB_CHANNEL,
            TOKEN,
            [ADMIN_ID],
            MESSAGES,
            AUTO_DEL,
            DB_URI,
            DB_NAME,
            API_ID,
            API_HASH
        )
    )

    await compose(app)


asyncio.run(main())
