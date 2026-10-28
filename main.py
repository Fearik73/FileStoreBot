
import asyncio
from bot import Bot
from pyrogram import compose
from config import *

async def main():
    app = []

    # Create bot instance using config.py values
    app.append(
        Bot(
            SESSION,
            WORKERS,
            DB_CHANNEL,
            TOKEN,
            MESSAGES,
            DB_URI,
            DB_NAME,
            API_ID,
            API_HASH
        )
    )

    await compose(app)


asyncio.run(main())
