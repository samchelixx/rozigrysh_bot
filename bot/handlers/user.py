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
    if args and args.startswith("result_"):
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
        await callback.answer() # Ack the callback so button stops spinning
        try:
            status_msg = await bot.send_message(user_id, "⏳ <b>Проверяем выполнение условий...</b> 🔍", parse_mode="HTML")
            await asyncio.sleep(1.5) # Simulated delay
        except Exception:
            status_msg = None

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
                    
            text += "\nПодпишись и нажми кнопку участия снова!"
            
            if status_msg:
                await status_msg.edit_text(text, disable_web_page_preview=True)
            else:
                await bot.send_message(user_id, text, disable_web_page_preview=True)
            return

        # Subscribe success
        result = await db.add_participant(user_id, giveaway_id)
        if result:
            success_txt = "✅ <b>Условия выполнены!</b>\nТы участвуешь в розыгрыше. Жди результатов. 🍀"
            if status_msg:
                await status_msg.edit_text(success_txt)
            else:
                await bot.send_message(user_id, success_txt)
        else:
            already_txt = "😎 <b>Проверка пройдена!</b>\nТы уже числишься в списках участников этого розыгрыша."
            if status_msg:
                await status_msg.edit_text(already_txt)
            else:
                await bot.send_message(user_id, already_txt)
            
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

