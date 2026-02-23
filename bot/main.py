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

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def update_counters_loop(bot: Bot):
    await asyncio.sleep(5) # Give the bot time to fully start
    last_counts = {} # Cache to prevent spamming API and save memory/CPU
    
    while True:
        try:
            giveaways = await db.get_active_giveaways()
            for giveaway in giveaways:
                giveaway_id = giveaway['id']
                if not giveaway.get('publish_message_id') or not giveaway.get('publish_channel_id'):
                    continue
                    
                count = await db.get_participants_count(giveaway_id)
                
                # Check cache: don't update if nothing changed (saves memory & avoids Rate Limits)
                if last_counts.get(giveaway_id) == count:
                    continue
                    
                last_counts[giveaway_id] = count
                
                raw_btn_text = "Участвую"
                if 'button_text' in giveaway.keys() and giveaway['button_text']:
                    raw_btn_text = giveaway['button_text']
                    
                base_text = raw_btn_text.split(" (")[0]
                new_btn_text = f"{base_text} ({count})"
                
                new_kb = [[InlineKeyboardButton(text=new_btn_text, callback_data=f"participate_{giveaway_id}")]]
                
                try:
                    chat = await bot.get_chat(giveaway['publish_channel_id'])
                    if chat.username:
                        post_url = f"https://t.me/{chat.username}/{giveaway['publish_message_id']}"
                    else:
                        invite_link = await bot.export_chat_invite_link(giveaway['publish_channel_id'])
                        post_url = f"{invite_link}/{giveaway['publish_message_id']}"
                    share_url = f"https://t.me/share/url?text=Участвуй в розыгрыше!&url={post_url}"
                    new_kb.append([InlineKeyboardButton(text="🚀 Поделиться розыгрышем", url=share_url)])
                except Exception:
                    pass
                    
                markup = InlineKeyboardMarkup(inline_keyboard=new_kb)
                
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=giveaway['publish_channel_id'],
                        message_id=giveaway['publish_message_id'],
                        reply_markup=markup
                    )
                    logging.info(f"Updated counter for Giveaway #{giveaway_id} to {count}")
                except Exception as e:
                    # Ignore "message is not modified" errors
                    if "is not modified" not in str(e).lower() and "message to edit not found" not in str(e).lower():
                        logging.error(f"Failed to update counter for GW {giveaway_id}: {e}")
                        
        except Exception as e:
            logging.error(f"Error in background counter updater: {e}")
            
        await asyncio.sleep(20) # Update every 20 seconds

async def main():
    # ... existing logic ...
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    await db.create_tables()

    dp.include_router(admin_channels.router)
    dp.include_router(admin_create.router)
    dp.include_router(admin_manage.router)
    dp.include_router(user.router)

    logging.info("Bot started!")
    
    # Start background task safely
    updater_task = asyncio.create_task(update_counters_loop(bot))
    
    try:
        await dp.start_polling(bot)
    finally:
        updater_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped.")
