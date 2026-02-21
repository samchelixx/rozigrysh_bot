from aiogram import Router, F, types
from aiogram.enums import ChatMemberStatus
from bot.database.core import db

router = Router()

@router.my_chat_member()
async def on_my_chat_member(event: types.ChatMemberUpdated):
    """
    Updates the list of channels where the bot is an admin.
    """
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status
    
    chat = event.chat
    
    # We only care about channels (and maybe groups if user want)
    if chat.type not in ['channel', 'supergroup', 'group']:
        return

    is_admin = new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    was_admin = old_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]

    if is_admin and not was_admin:
        # Bot became admin
        await db.add_admin_channel(chat.id, chat.title)
        print(f"DEBUG: Added admin channel {chat.title} ({chat.id})")
        
    elif not is_admin and was_admin:
        # Bot lost admin rights
        await db.remove_admin_channel(chat.id)
        print(f"DEBUG: Removed admin channel {chat.title} ({chat.id})")
    
    # Also update if it was admin and still admin (e.g. title changed or perms changed)
    elif is_admin and was_admin:
         await db.add_admin_channel(chat.id, chat.title)
