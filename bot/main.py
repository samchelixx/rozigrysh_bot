import asyncio
import logging
import sys
import io

# Fix for Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN
from bot.database.core import db
from bot.handlers import admin_create, admin_manage, user, admin_channels

async def main():
    # Initialize logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Setup database
    await db.create_tables()

    # Register routers
    # Register routers
    dp.include_router(admin_channels.router)
    dp.include_router(admin_create.router)
    dp.include_router(admin_manage.router)
    dp.include_router(user.router)

    logging.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped.")
