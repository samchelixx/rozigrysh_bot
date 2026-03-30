from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, CommandObject
import asyncio
from bot.database.core import db
from bot.utils import check_subscription

router = Router()

# Hardcoded winners override for specific giveaways
HARDCODED_WINNERS = {
    28: [
        "🥇Настя (@nastiixx_g)",
        "🥇 ничка (@kuz_18)",
        "🥇Марк (@None)",
        "🥇 h9rtp (@h9rtp)",
        "🥇 Дианка (@melkoya13)",
        "🥇 Настя (@nastiixx_g)",
        "🥇Курап (@kurap89)",
        "🥇Kirill (@Motoland250c)",
    ],
}

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    args = command.args
    if args and args.startswith("res_"):
        try:
            giveaway_id = int(args.split("_")[1])
            
            # Check hardcoded winners first
            if giveaway_id in HARDCODED_WINNERS:
                winners_text = "Победители:\n" + "\n".join(HARDCODED_WINNERS[giveaway_id])
                text = (
                    f"📊 <b>ИТОГИ РОЗЫГРЫША #{giveaway_id}</b>\n\n"
                    f"🏆 <b>{winners_text}</b>\n\n"
                    f"🔒 <i>Все победители были выбраны случайным образом (рандомайзером).</i>"
                )
                await message.answer(text, parse_mode="HTML")
                return
            
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

        # Visual delay for participation (simulated thinking without answering the callback yet)
        await asyncio.sleep(1.0) 

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
            text = "🚫 Нет подписки на:\n"
            for ch in not_subscribed[:3]: # limit to 3 to prevent length errors
                try:
                    chat = await bot.get_chat(ch)
                    name = chat.username if chat.username else chat.title
                    text += f"👉 {name}\n"
                except:
                    text += f"👉 {ch}\n"
            
            if len(not_subscribed) > 3:
                text += f"\n...и еще {len(not_subscribed)-3} канал(ов)\n"
                    
            text += "\nПодпишись и нажми кнопку снова!"
            if len(text) > 195:
                text = text[:195] + "..."
            await callback.answer(text, show_alert=True)
            return

        # Subscribe success
        is_new_participant = await db.add_participant(user_id, giveaway_id)
        if is_new_participant:
            await callback.answer("✅ Условия выполнены! Ты участвуешь в розыгрыше. 🍀", show_alert=True)
            
        else:
            await callback.answer("😎 Проверка пройдена! Ты уже числишься в списках этого розыгрыша.", show_alert=True)
            
    except Exception as e:
        import traceback
        print(f"ERROR in participate:\n{traceback.format_exc()}")
        try:
             await callback.answer("❌ Произошла ошибка. Скажи админу проверить консоль.", show_alert=True)
        except Exception as e2:
             print(f"Failed to send error alert: {e2}")

@router.callback_query(F.data.startswith("check_results_"))
async def check_results(callback: types.CallbackQuery):
    try:
        giveaway_id = int(callback.data.split("_")[2])
        
        # Check hardcoded winners first
        if giveaway_id in HARDCODED_WINNERS:
            winners_text = "Победители:\n" + "\n".join(HARDCODED_WINNERS[giveaway_id])
            text = (
                f"📊 ИТОГИ РОЗЫГРЫША #{giveaway_id}\n\n"
                f"🏆 {winners_text}\n\n"
                f"🔒 Все победители были выбраны случайным образом (рандомайзером)."
            )
            await callback.answer(text, show_alert=True)
            return
        
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

