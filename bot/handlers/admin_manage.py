
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.database.core import db
from bot.config import ADMIN_IDS
from bot.keyboards.admin import main_admin_keyboard
from aiogram.fsm.state import State, StatesGroup
import random
from bot.utils import get_message_html, check_subscription

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

# --- Helpers ---
async def get_giveaway_keyboard(action_prefix: str):
    giveaways = await db.get_active_giveaways()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    for g in giveaways:
        # Get participant count
        participants = await db.get_participants(g['id'])
        count = len(participants)
        # Button text: ID | Description snippet | Count
        desc = g['description'][:15] + "..." if len(g['description']) > 15 else g['description']
        rows.append([InlineKeyboardButton(text=f"#{g['id']} {desc} ({count} уч.)", callback_data=f"{action_prefix}_{g['id']}")])
    
    kb.inline_keyboard = rows
    return kb, len(giveaways)

# --- 📋 Список розыгрышей (View Info) ---
@router.message(F.text == "📋 Список розыгрышей")
async def list_giveaways(message: types.Message):
    kb, count = await get_giveaway_keyboard("view_gw")
    if count == 0:
        await message.answer("📭 Активных розыгрышей нет.")
    else:
        await message.answer("📋 Выбери розыгрыш для просмотра инфо:", reply_markup=kb)

@router.callback_query(F.data.startswith("view_gw_"))
async def view_giveaway_info(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    gw = await db.get_giveaway(gw_id)
    if not gw:
        await callback.answer("Розыгрыш не найден", show_alert=True)
        return

    participants = await db.get_participants(gw_id)
    winners = await db.get_winners(gw_id)
    
    # Construct info text
    text = (
        f"🎁 <b>Розыгрыш #{gw_id}</b>\n"
        f"📄 Описание: {gw['description']}\n"
        f"📢 Публикация в: {gw['publish_channel_id']}\n"
        f"👥 Участников: {len(participants)}\n"
        f"🏆 Победителей выбрано: {len(winners)}\n"
        f"🏁 Статус: {gw['status']}"
    )
    
    # Button to go back to list or maybe manage directly?
    # User separated "List" and "Manage". So here just info.
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_list_view")
    ]])
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "back_to_list_view")
async def back_to_list_view(callback: types.CallbackQuery):
    await callback.message.delete()
    await list_giveaways(callback.message)


# --- 👥 Список участников (Pick Winner) ---
@router.message(F.text == "👥 Список участников")
async def list_participants_menu(message: types.Message):
    kb, count = await get_giveaway_keyboard("part_gw")
    if count == 0:
        await message.answer("📭 Активных розыгрышей нет.")
    else:
        await message.answer("👥 Выбери розыгрыш для просмотра участников и выбора победителя:", reply_markup=kb)

@router.callback_query(F.data.startswith("part_gw_"))
async def show_participants_menu(callback: types.CallbackQuery):
    try:
        gw_id = int(callback.data.split("_")[2])
        participants = await db.get_participants(gw_id)
        
        text = f"👥 <b>Участники розыгрыша #{gw_id} ({len(participants)} чел.):</b>\n"
        
        kb_rows = []
        
        # Show last 50 participants as buttons
        display_participants = participants[-50:] 
        
        for p in display_participants:
            # p is from users table (u.* via join), so use p['id']
            # Also p has username and full_name
            name = p['full_name'] or p['username'] or str(p['id'])
            # Button to pick this specific user
            kb_rows.append([InlineKeyboardButton(text=f"👤 {name}", callback_data=f"pick_winner_{gw_id}_{p['id']}")])

        # Navigation buttons at top/bottom
        kb_rows.insert(0, [InlineKeyboardButton(text="🎲 Случайный победитель", callback_data=f"pick_random_{gw_id}")])
        kb_rows.append([InlineKeyboardButton(text="📢 Опубликовать результаты", callback_data=f"finish_gw_{gw_id}")])
        kb_rows.append([InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_list_part")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        msg_text = text + "\n👇 Нажми на участника, чтобы выбрать победителем (или выбери случайного)."
        await callback.message.edit_text(msg_text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"ERROR in show_participants_menu: {e}")
        await callback.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "back_to_list_part")
async def back_to_list_part(callback: types.CallbackQuery):
    await callback.message.delete()
    await list_participants_menu(callback.message)

@router.callback_query(F.data.startswith("pick_winner_"))
async def pick_specific_winner(callback: types.CallbackQuery):
    # data: pick_winner_GWID_UID
    parts = callback.data.split("_")
    gw_id = int(parts[2])
    user_id = int(parts[3])
    
    await db.set_winner(user_id, gw_id)
    
    user = await db.get_user(user_id)
    name = user['full_name'] if user else str(user_id)
    
    await callback.answer(f"🏆 {name} выбран победителем!", show_alert=True)
    # Refresh menu
    await show_participants_menu(callback)

@router.callback_query(F.data.startswith("pick_random_"))
async def pick_random_winner(callback: types.CallbackQuery, bot: Bot):
    gw_id = int(callback.data.split("_")[2])
    # db.get_participants returns list of user Row objects (u.*)
    participants = await db.get_participants(gw_id)
    gw = await db.get_giveaway(gw_id)
    
    # Filter out existing winners
    current_winners = await db.get_winners(gw_id)
    # db.get_winners also returns u.*
    winner_ids = [w['id'] for w in current_winners]
    
    eligible = []
    
    # Check subscription for random pick to be safe
    required_channels = [c.strip() for c in gw['channel_ids'].split(',') if c.strip()]
    cleaned_channels = [] 
    
    # Resolve channel IDs to int if possible for check_subscription
    for c in required_channels:
        try:
            cleaned_channels.append(int(c))
        except:
            cleaned_channels.append(c)

    random.shuffle(participants)
    
    valid_winner = None
    
    await callback.answer("🎲 Ищем победителя...", show_alert=False)
    
    for p in participants:
        # p is user Row
        if p['id'] in winner_ids:
            continue
            
        # Check sub
        is_sub = True
        for ch in cleaned_channels:
            if not await check_subscription(bot, p['id'], ch):
                is_sub = False
                break
        
        if is_sub:
            valid_winner = p
            break
            
    if not valid_winner:
        await callback.answer("🤷‍♂️ Нет доступных участников (или все отписались).", show_alert=True)
        return

    await db.set_winner(valid_winner['id'], gw_id)
    
    name = valid_winner['full_name'] or valid_winner['username'] or str(valid_winner['id'])
    
    await callback.answer(f"🎲 Случайный победитель: {name}", show_alert=True)
    await show_participants_menu(callback)

@router.callback_query(F.data.startswith("finish_gw_"))
async def finish_giveaway_publish(callback: types.CallbackQuery, bot: Bot):
    gw_id = int(callback.data.split("_")[2])
    winners = await db.get_winners(gw_id)
    
    if not winners:
        await callback.answer("❌ Сначала выбери победителей!", show_alert=True)
        return
        
    gw = await db.get_giveaway(gw_id)
    
    winners_text = "\n".join([f"🥇 {w['full_name'] or 'Пользователь'}" for w in winners])
    text = (
        f"🏆 <b>Итоги розыгрыша!</b>\n\n"
        f"{gw['description']}\n\n"
        f"<b>Победители:</b>\n{winners_text}\n\n"
        f"Поздравляем! 🥳"
    )
    
    try:
        if gw['publish_channel_id']:
            await bot.send_message(chat_id=gw['publish_channel_id'], text=text)
            # Remove button from original post if possible
            if gw['publish_message_id']:
                try:
                    await bot.edit_message_reply_markup(chat_id=gw['publish_channel_id'], message_id=gw['publish_message_id'], reply_markup=None)
                except:
                    pass
        
        await callback.answer("✅ Результаты опубликованы!", show_alert=True)
        await callback.message.edit_text(f"✅ Розыгрыш #{gw_id} завершен.\n\n{winners_text}")
    except Exception as e:
        await callback.answer(f"Ошибка публикации: {e}", show_alert=True)


# --- ⚙️ Управление (Edit/Delete) ---
@router.message(F.text == "⚙️ Управление")
async def manage_menu(message: types.Message):
    kb, count = await get_giveaway_keyboard("manage_gw")
    if count == 0:
        await message.answer("📭 Активных розыгрышей нет.")
    else:
        await message.answer("⚙️ Выбери розыгрыш для редактирования или удаления:", reply_markup=kb)

@router.callback_query(F.data.startswith("manage_gw_"))
async def manage_giveaway_actions(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_desc_{gw_id}")],
        [InlineKeyboardButton(text="🗑 Удалить розыгрыш", callback_data=f"delete_gw_{gw_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="back_to_manage_list")]
    ])
    
    await callback.message.edit_text(f"⚙️ Управление розыгрышем #{gw_id}", reply_markup=kb)

@router.callback_query(F.data == "back_to_manage_list")
async def back_to_manage_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await manage_menu(callback.message)

@router.callback_query(F.data.startswith("delete_gw_"))
async def delete_giveaway_confirm(callback: types.CallbackQuery):
    gw_id = int(callback.data.split("_")[2])
    await db.delete_giveaway(gw_id)
    await callback.answer("✅ Розыгрыш удален.", show_alert=True)
    await manage_menu(callback.message)

# Edit FSM
class EditGiveaway(StatesGroup):
    waiting_for_new_desc = State()

@router.callback_query(F.data.startswith("edit_desc_"))
async def edit_desc_start(callback: types.CallbackQuery, state: FSMContext):
    gw_id = int(callback.data.split("_")[2])
    await state.update_data(edit_gw_id=gw_id)
    await state.set_state(EditGiveaway.waiting_for_new_desc)
    
    # Send new message because we need reply keyboard potentially or just text input
    # User might want to cancel with /cancel
    await callback.message.answer(
        "✏️ Введи новое описание (HTML поддерживается).\nИли нажми /cancel для отмены.", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    await callback.answer()

@router.message(EditGiveaway.waiting_for_new_desc)
async def edit_desc_save(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    gw_id = data.get('edit_gw_id')
    
    new_text = get_message_html(message)
    await db.update_giveaway_description(gw_id, new_text)
    
    # Try update channel
    gw = await db.get_giveaway(gw_id)
    updated_in_channel = False
    
    if gw['publish_channel_id'] and gw['publish_message_id']:
        try:
            # Reconstruct channels text
            channel_ids = gw['channel_ids'].split(',')
            lines = []
            for cid in channel_ids:
                 try: 
                     chat = await bot.get_chat(cid)
                     link = chat.username
                     name = chat.title
                     if link:
                         lines.append(f"👉 <a href='https://t.me/{link}'>{name}</a>")
                     else:
                         lines.append(f"👉 {name}")
                 except:
                     lines.append(f"👉 Канал {cid}")
            
            channels_text = "\n\n📢 <b>Подпишись на:</b>\n" + "\n".join(lines)
            final_text = new_text + channels_text
            
            # Reconstruct KB with the share button
            try:
                chat = await bot.get_chat(gw['publish_channel_id'])
                if chat.username:
                    post_url = f"https://t.me/{chat.username}/{gw['publish_message_id']}"
                else:
                    post_url = f"https://t.me/c/{str(chat.id)[4:]}/{gw['publish_message_id']}"
                share_url = f"https://t.me/share/url?url={post_url}&text=Участвуй в конкурсе! 🎁"
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=gw['button_text'], callback_data=f"participate_{gw_id}")],
                    [InlineKeyboardButton(text="🔗 Поделиться", url=share_url)]
                ])
            except Exception:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=gw['button_text'], callback_data=f"participate_{gw_id}")
                ]])
            
            await bot.edit_message_caption(
                chat_id=gw['publish_channel_id'], 
                message_id=gw['publish_message_id'], 
                caption=final_text, 
                reply_markup=kb
            )
            updated_in_channel = True
        except Exception as e:
            print(f"Edit error: {e}")
            # If caption fails, try text
            try:
                await bot.edit_message_text(
                    chat_id=gw['publish_channel_id'], 
                    message_id=gw['publish_message_id'], 
                    text=final_text, 
                    reply_markup=kb
                )
                updated_in_channel = True
            except:
                pass

    await state.clear()
    msg = "✅ Описание обновлено!"
    if updated_in_channel:
        msg += " (и в канале тоже)"
    
    await message.answer(msg, reply_markup=main_admin_keyboard())

@router.message(F.text, F.state == "waiting_for_winner_username")
async def pick_manual_finish(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    giveaway_id = data['picking_giveaway_id']
    
    user = await db.get_user_by_username(username)
    if not user:
        await message.answer("❌ Пользователь не найден в базе данных этого бота. Попробуй еще раз.")
        return

    # Check subscriptions
    giveaway = await db.get_giveaway(giveaway_id)
    required_channels = [c.strip() for c in giveaway['channel_ids'].split(',') if c.strip()]
    
    from bot.utils import check_subscription
    not_subscribed = []
    for channel in required_channels:
        if not await check_subscription(bot, user['id'], channel):
            not_subscribed.append(channel)
    
    if not_subscribed:
        await message.answer(
            f"❌ Этот пользователь (@{user['username']}) не подписан на: {', '.join(not_subscribed)}.\n"
            "Выбери другого или скажи ему подписаться."
        )
        return

    # Mark as winner
    await db.set_winner(user['id'], giveaway_id)
    await state.clear()
    
    await message.answer(f"✅ Победитель {user['full_name']} добавлен!", reply_markup=main_admin_keyboard())
    # Note: ideally redirect back to manage menu, but since message is new, we just give confirm.
    # We can send a new message with the menu.
    
    # Re-show menu
    # Need to verify if we can call list_giveaways or just show the manage menu for this specific giveaway
    # Can't easily call manage_giveaway_menu because it expects a callback.
    # Let's just say "Added, go back to list"
    builder = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text="🔙 К управлению розыгрышем", callback_data=f"manage_{giveaway_id}")
    ]])
    await message.answer("Вернуться в меню:", reply_markup=builder)


@router.callback_query(F.data.startswith("publish_results_"))
async def publish_results(callback: types.CallbackQuery, bot: Bot):
    try:
        print(f"DEBUG: publish_results called for {callback.data}")
        giveaway_id = int(callback.data.split("_")[2])
        giveaway = await db.get_giveaway(giveaway_id)
        winners = await db.get_winners(giveaway_id)
        
        if not winners:
            print("DEBUG: No winners selected")
            await callback.answer("❌ Сначала выбери победителей!", show_alert=True)
            return
            
        # Finish and Announce
        await db.finish_giveaway(giveaway_id)
        
        if giveaway['publish_channel_id']:
            try:
                winners_text = "\n".join([f"🥇 {w['full_name']} (@{w['username']})" for w in winners])
                result_text = (
                    f"🎉 <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b>\n\n"
                    f"🎁 Приз: {giveaway['description'].splitlines()[0]}\n\n"
                    f"🏆 <b>Победители:</b>\n"
                    f"{winners_text}\n\n"
                    f"Поздравляем! 🥳"
                )
                await bot.send_message(chat_id=giveaway['publish_channel_id'], text=result_text)
                print(f"DEBUG: Results posted to {giveaway['publish_channel_id']}")
                
                # Remove button from original post and replace with Results button
                if giveaway['publish_message_id']:
                    try:
                        print(f"DEBUG: Replacing button for msg {giveaway['publish_message_id']}")
                        bot_info = await bot.me()
                        bot_username = bot_info.username
                        url = f"https://t.me/{bot_username}?start=result_{giveaway_id}"
                        
                        kb_results = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🏆 Проверить результаты", url=url)
                        ]])
                        await bot.edit_message_reply_markup(
                            chat_id=giveaway['publish_channel_id'], 
                            message_id=giveaway['publish_message_id'], 
                            reply_markup=kb_results
                        )
                    except Exception as e:
                         print(f"DEBUG: Failed to replace button: {e}")
                    
                await callback.message.edit_text(f"✅ Результаты опубликованы в канале!\n\n{winners_text}", reply_markup=None)
                
            except Exception as e:
                print(f"ERROR posting results: {e}")
                await callback.message.answer(f"⚠️ Ошибка публикации: {e}")
        else:
            await callback.message.edit_text("✅ Розыгрыш закрыт (без публикации в канале).", reply_markup=None)
    except Exception as e:
        print(f"CRITICAL ERROR in publish_results: {e}")
        await callback.message.answer(f"❌ Критическая ошибка: {e}")

@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await list_giveaways(callback.message)
