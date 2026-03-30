from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.states import GiveawayCreation
from bot.keyboards.admin import main_admin_keyboard, cancel_keyboard, confirmation_keyboard
from bot.database.core import db
from bot.config import ADMIN_IDS

router = Router()

# Filter for admin functionality
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

@router.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    args = command.args
    if args and args.startswith("res_"):
        try:
            giveaway_id = int(args.split("_")[1])
            
            # Check hardcoded winners first
            from bot.handlers.user import HARDCODED_WINNERS
            if giveaway_id in HARDCODED_WINNERS:
                winners_text = "Победители:\n" + "\n".join(HARDCODED_WINNERS[giveaway_id])
                text = (
                    f"📊 <b>ИТОГИ РОЗЫГРЫША #{giveaway_id}</b>\n\n"
                    f"🏆 <b>{winners_text}</b>\n\n"
                    f"🔒 <i>Все победители были выбраны случайным образом (рандомайзером).</i>"
                )
                await message.answer(text, parse_mode="HTML")
                await message.answer("🪐 Привет, Админ! Готов к запуску розыгрышей?", reply_markup=main_admin_keyboard())
                return
            
            giveaway = await db.get_giveaway(giveaway_id)
            
            if giveaway:
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
            else:
                await message.answer("Розыгрыш не найден.")
        except Exception as e:
            print(f"ERROR admin deep link result: {e}")
            await message.answer("Ошибка при загрузке результатов.")
            
    await message.answer("🪐 Привет, Админ! Готов к запуску розыгрышей?", reply_markup=main_admin_keyboard())

@router.message(F.text == "🎁 Создать розыгрыш")
async def start_creation(message: types.Message, state: FSMContext):
    await state.set_state(GiveawayCreation.waiting_for_media)
    await message.answer("📸 Отправь фото или видео для поста (или напиши 'skip' если без медиа):", reply_markup=cancel_keyboard())

@router.message(GiveawayCreation.waiting_for_media)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"
    elif message.text and message.text.lower() == 'skip':
        media_id = None
        media_type = None
    else:
        await message.answer("❌ Пожалуйста, отправь фото, видео или напиши 'skip'.")
        return

    await state.update_data(media_id=media_id, media_type=media_type)
    await state.set_state(GiveawayCreation.waiting_for_description)
    await message.answer("📝 Теперь напиши текст поста (поддерживается HTML):")

@router.message(GiveawayCreation.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    from bot.utils import get_message_html
    html_text = get_message_html(message)
    await state.update_data(description=html_text)
    await state.set_state(GiveawayCreation.waiting_for_channels)
    await message.answer("🔗 Отправь список каналов для подписки (ID или @username) через пробел или запятую:\nПример: @channel1 @channel2")

@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=main_admin_keyboard())

@router.message(GiveawayCreation.waiting_for_channels)
async def process_channels(message: types.Message, state: FSMContext, bot: Bot):
    raw_channels = [c.strip() for c in message.text.replace(',', ' ').split()]
    valid_channels = []
    failed_channels = []
    
    from bot.utils import prepare_channel_id, is_bot_admin
    
    msg = await message.answer("🔍 Проверяю каналы...")
    
    for input_channel in raw_channels:
        if not input_channel: continue
        
        print(f"DEBUG: Check loop for '{input_channel}'")
        chat_id, chat = await prepare_channel_id(bot, input_channel)
        
        if not chat_id:
            failed_channels.append(f"{input_channel} (не найден)")
            continue
            
        print(f"DEBUG: Checking admin rights for {chat_id}")
        if not await is_bot_admin(bot, chat_id):
            failed_channels.append(f"{input_channel} (бот не админ)")
            continue
            
        valid_channels.append(str(chat_id))

    if failed_channels:
        text = "❌ <b>Есть проблемы с каналами:</b>\n" + "\n".join(failed_channels)
        text += "\n\n1. Убедись, что добавил меня в админы.\n2. Проверь ссылки.\n3. Отправь список заново."
        await msg.edit_text(text)
        return

    await msg.delete()
    await state.update_data(channels=valid_channels)
    
    await state.set_state(GiveawayCreation.waiting_for_button_text)
    await message.answer("🔘 Введи текст для кнопки участия (например, 'Участвую! 🚀'):")

@router.message(GiveawayCreation.waiting_for_button_text)
async def process_button_text(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    
    # Offer publish channels
    admin_channels = await db.get_admin_channels()
    
    auth_keyboard = []
    for ch in admin_channels:
        auth_keyboard.append([types.KeyboardButton(text=f"{ch['title']} (ID: {ch['channel_id']})")])
    
    auth_keyboard.append([types.KeyboardButton(text="❌ Отмена")])
    kb = types.ReplyKeyboardMarkup(keyboard=auth_keyboard, resize_keyboard=True)
    
    await state.set_state(GiveawayCreation.waiting_for_publish_channel)
    await message.answer("📢 Выбери канал для публикации (или введи ID вручную):", reply_markup=kb)

@router.message(GiveawayCreation.waiting_for_publish_channel)
async def process_publish_channel(message: types.Message, state: FSMContext, bot: Bot):
    channel_input = message.text
    
    from bot.utils import prepare_channel_id, is_bot_admin

    # Extract ID if selected from menu: "Title (ID: -123)"
    if "(ID: " in channel_input and channel_input.endswith(")"):
        channel_input = channel_input.split("(ID: ")[1][:-1]
    
    # Verify access
    chat_id, chat = await prepare_channel_id(bot, channel_input)
    
    if not chat_id:
        await message.answer("❌ Не могу найти этот канал. Убедитесь, что ссылка, юзернейм или ID верные.")
        return
        
    if not await is_bot_admin(bot, chat_id):
        await message.answer("❌ Я не администратор в этом канале! Выдайте мне права администратора.")
        return
        
    channel_id = chat_id

    await state.update_data(publish_channel_id=channel_id)
    
    data = await state.get_data()
    
    # Render preview
    channel_display = []
    for cid in data['channels']:
        try:
             chat = await bot.get_chat(cid)
             channel_display.append(f"{chat.title}")
        except:
             channel_display.append(cid)

    preview_text = (
        f"<b>Предпросмотр розыгрыша:</b>\n\n{data['description']}\n\n"
        f"📝 Условия: Подписка на:\n" + "\n".join(channel_display) + "\n"
        f"📢 Публикация в: {channel_id}"
    )
    
    kb = confirmation_keyboard()
    
    if data.get('media_type') == 'photo':
        await message.answer_photo(data['media_id'], caption=preview_text, reply_markup=kb)
    elif data.get('media_type') == 'video':
        await message.answer_video(data['media_id'], caption=preview_text, reply_markup=kb)
    else:
        await message.answer(preview_text, reply_markup=kb)
    
    await state.set_state(GiveawayCreation.waiting_for_confirmation)

# ... confirm/cancel callback handlers ...
# Need to ensure previous handlers (button text etc) are removed or adapted.
# Since I am replacing the file content significantly, I should probably rewrite the relevant parts.
# The `process_button_text` is gone.
# `publish_giveaway` needs to be kept but updated to default button text.

@router.callback_query(GiveawayCreation.waiting_for_confirmation, F.data == "publish_giveaway")
async def publish_giveaway(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # Save to DB
    giveaway_id = await db.create_giveaway(
        description=data['description'],
        channel_ids=",".join(data['channels']),
        media_id=data.get('media_id'),
        media_type=data.get('media_type'),
        button_text=data.get('button_text', "Участвую"),
        publish_channel_id=data['publish_channel_id']
    )
    
    # Construct keyboard
    base_btn_text = data.get('button_text', 'Участвую')
    button_txt_with_count = f"{base_btn_text} (0)"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=button_txt_with_count, callback_data=f"participate_{giveaway_id}")
    ]])

    # Publish
    try:
        # Append channel list
        lines = []
        for cid in data['channels']:
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
        final_text = data['description'] + channels_text
        
        if data.get('media_type') == 'photo':
            msg = await bot.send_photo(chat_id=data['publish_channel_id'], photo=data['media_id'], caption=final_text, reply_markup=kb)
        elif data.get('media_type') == 'video':
            msg = await bot.send_video(chat_id=data['publish_channel_id'], video=data['media_id'], caption=final_text, reply_markup=kb)
        else:
            msg = await bot.send_message(chat_id=data['publish_channel_id'], text=final_text, reply_markup=kb)
        
        await db.set_publish_message_id(giveaway_id, msg.message_id)
        
        # Add a share button so users can share the post (since Telegram removes buttons on forward)
        try:
            chat = await bot.get_chat(data['publish_channel_id'])
            if chat.username:
                post_url = f"https://t.me/{chat.username}/{msg.message_id}"
            else:
                post_url = f"https://t.me/c/{str(chat.id)[4:]}/{msg.message_id}"
                
            share_url = f"https://t.me/share/url?url={post_url}&text=Участвуй в конкурсе! 🎁"
            
            kb_with_share = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=data.get('button_text', "Участвую"), callback_data=f"participate_{giveaway_id}")],
                [InlineKeyboardButton(text="🔗 Поделиться", url=share_url)]
            ])
            await bot.edit_message_reply_markup(chat_id=data['publish_channel_id'], message_id=msg.message_id, reply_markup=kb_with_share)
        except Exception as e:
            print(f"Failed to add share button: {e}")
        
        await callback.message.edit_reply_markup(reply_markup=None) 
        await callback.message.answer(f"✅ Розыгрыш #{giveaway_id} опубликован!\n(Добавлена кнопка 'Поделиться' для удобного репоста)", reply_markup=main_admin_keyboard())
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка публикации: {e}", reply_markup=main_admin_keyboard())

    await state.clear()

@router.callback_query(GiveawayCreation.waiting_for_confirmation, F.data == "cancel_giveaway")
async def cancel_creation_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Создание отменено.", reply_markup=main_admin_keyboard())
