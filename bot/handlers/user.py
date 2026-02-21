from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from bot.database.core import db
from bot.utils import check_subscription

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(
        "👋 <b>Привет, кибер-странник!</b> 🌌\n\n"
        "Я бот для проведения розыгрышей. Следи за новостями в каналах и жми кнопки участия!\n"
        "Удачи! 🍀"
    )

@router.callback_query(F.data.startswith("participate_"))
async def participate(callback: types.CallbackQuery, bot: Bot):
    try:
        print(f"DEBUG: Participation request from {callback.from_user.id} for {callback.data}")
        user_id = callback.from_user.id
        username = callback.from_user.username
        full_name = callback.from_user.full_name
        
        # Ensure user is in DB
        await db.create_user(user_id, username, full_name)
        
        giveaway_id = int(callback.data.split("_")[1])
        giveaway = await db.get_giveaway(giveaway_id)
        
        if not giveaway or giveaway['status'] != 'active':
            await callback.answer("⏳ Розыгрыш уже завершен или не найден.", show_alert=True)
            return

        # Check subscriptions
        channels = giveaway['channel_ids'].split(',')
        not_subscribed = []
        
        for channel in channels:
            channel = channel.strip()
            if not channel: continue
            
            # channel is now likely an ID string inside DB
            print(f"DEBUG: Checking sub for {channel}")
            
            # Convert to int if it looks like one, otherwise str
            try:
                chan_id = int(channel)
            except ValueError:
                chan_id = channel

            is_sub = await check_subscription(bot, user_id, chan_id)
            if not is_sub:
                not_subscribed.append(channel)
                
        if not_subscribed:
            text = "🚫 <b>Ты не подписан на каналы:</b>\n\n"
            for ch in not_subscribed:
                # Try to get chat to show link
                try:
                    chat = await bot.get_chat(ch)
                    if chat.username:
                        text += f"👉 <a href='https://t.me/{chat.username}'>{chat.title}</a>\n"
                    else:
                         text += f"👉 {chat.title}\n"
                except:
                    text += f"👉 Канал\n"
                    
            text += "\nПодпишись и нажми кнопку снова!"
            await callback.answer(text, show_alert=True)
            return

        # Subscribe success
        result = await db.add_participant(user_id, giveaway_id)
        if result:
            await callback.answer("✅ Ты участвуешь! Жди результатов. 🍀", show_alert=True)
        else:
            await callback.answer("😎 Ты уже участвуешь!", show_alert=True)
            
    except Exception as e:
        print(f"ERROR in participate: {e}")
        await callback.answer("❌ Произошла ошибка. Скажи админу проверить консоль.", show_alert=True)
