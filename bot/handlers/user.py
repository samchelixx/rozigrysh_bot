from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, CommandObject
import asyncio
from bot.database.core import db
from bot.utils import check_subscription

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    args = command.args
    if args and args.startswith("res_"):
        try:
            giveaway_id = int(args.split("_")[1])
            giveaway = await db.get_giveaway(giveaway_id)
            
            if not giveaway:
                await message.answer("Розыгрыш не найден.")
                return
                
            participants_count = await db.get_participants_count(giveaway_id)
            winners = await db.get_winners(giveaway_id)
            
            winners_names = [f"@{w['username']}" if w['username'] else w['full_name'] for w in winners]
            
            if not winners:
                winners_text = "Победители еще не определены."
            else:
                winners_text = "Победители:\n" + "\n".join([f"🥇 {name}" for name in winners_names])
                
            text = (
                f"📊 <b>ИТОГИ РОЗЫГРЫША #{giveaway_id}</b>\n\n"
                f"👥 Всего участников: {participants_count}\n"
                f"🏆 <b>{winners_text}</b>\n\n"
                f"🔒 <i>Все победители были выбраны случайным образом (рандомайзером).</i>"
            )
            
            await message.answer(text, parse_mode="HTML")
            return
        except Exception as e:
            print(f"ERROR deep link result: {e}")
            await message.answer("Ошибка при загрузке результатов.")
            return

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

        # Visual delay for participation
        await callback.answer("⏳ Проверяем выполнение условий...", show_alert=False)
        await asyncio.sleep(1.5) # Simulated delay

        # Check subscriptions
        channels = giveaway['channel_ids'].split(',')
        not_subscribed = []
        
        for channel in channels:
            channel = channel.strip()
            if not channel: continue
            
            try:
                chan_id = int(channel)
            except ValueError:
                chan_id = channel

            is_sub = await check_subscription(bot, user_id, chan_id)
            if not is_sub:
                not_subscribed.append(channel)
                
        if not_subscribed:
            text = "🚫 Вы не подписаны на следующие каналы:\n\n"
            for ch in not_subscribed:
                try:
                    chat = await bot.get_chat(ch)
                    if chat.username:
                        text += f"👉 @{chat.username}\n"
                    else:
                         text += f"👉 {chat.title}\n"
                except:
                    text += f"👉 Канал\n"
                    
            text += "\nПодпишитесь и нажмите кнопку снова!"
            await callback.answer(text, show_alert=True)
            return

        # Subscribe success
        is_new_participant = await db.add_participant(user_id, giveaway_id)
        if is_new_participant:
            await callback.answer("✅ Условия выполнены! Ты участвуешь в розыгрыше. 🍀", show_alert=True)
            
            # --- Update Participant Count on Button ---
            try:
                count = await db.get_participants_count(giveaway_id)
                # Keep the original button text base but append the count
                base_text = giveaway.get('button_text', "Участвую").split(" (")[0]
                new_btn_text = f"{base_text} ({count})"
                
                # Reconstruct the keyboard with the Share button if it existed
                new_kb = []
                if callback.message.reply_markup and callback.message.reply_markup.inline_keyboard:
                    orig_kb = callback.message.reply_markup.inline_keyboard
                    for row in orig_kb:
                        new_row = []
                        for btn in row:
                            if btn.callback_data == callback.data:
                                # Update our own participate button
                                new_row.append(InlineKeyboardButton(text=new_btn_text, callback_data=callback.data))
                            else:
                                # Keep Share button or any other original buttons intact
                                if btn.url:
                                    new_row.append(InlineKeyboardButton(text=btn.text, url=btn.url))
                                elif btn.callback_data:
                                    new_row.append(InlineKeyboardButton(text=btn.text, callback_data=btn.callback_data))
                        new_kb.append(new_row)
                        
                markup = InlineKeyboardMarkup(inline_keyboard=new_kb)
                
                # Only try to update if it's the official channel post
                if giveaway.get('publish_message_id'):
                    await bot.edit_message_reply_markup(
                        chat_id=giveaway['publish_channel_id'],
                        message_id=giveaway['publish_message_id'],
                        reply_markup=markup
                    )
            except Exception as e:
                print(f"DEBUG: Could not update participant count on button: {e}")
                
        else:
            await callback.answer("😎 Проверка пройдена! Ты уже числишься в списках этого розыгрыша.", show_alert=True)
            
    except Exception as e:
        print(f"ERROR in participate: {e}")
        try:
             await callback.answer("❌ Произошла ошибка. Скажи админу проверить консоль.", show_alert=True)
        except:
             pass

@router.callback_query(F.data.startswith("check_results_"))
async def check_results(callback: types.CallbackQuery):
    try:
        giveaway_id = int(callback.data.split("_")[2])
        giveaway = await db.get_giveaway(giveaway_id)
        
        if not giveaway:
            await callback.answer("Розыгрыш не найден.", show_alert=True)
            return
            
        participants_count = await db.get_participants_count(giveaway_id)
        winners = await db.get_winners(giveaway_id)
        
        winners_names = [f"@{w['username']}" if w['username'] else w['full_name'] for w in winners]
        
        if not winners:
            winners_text = "Победители еще не определены."
        else:
            winners_text = "Победители: " + ", ".join(winners_names)
            
        text = (
            f"📊 ИТОГИ РОЗЫГРЫША #{giveaway_id}\n\n"
            f"👥 Всего участников: {participants_count}\n"
            f"🏆 {winners_text}\n\n"
            f"🔒 Все победители были выбраны случайным образом (рандомайзером)."
        )
        
        await callback.answer(text, show_alert=True)
    except Exception as e:
        print(f"ERROR in check_results: {e}")
        await callback.answer("Ошибка при загрузке результатов.", show_alert=True)

