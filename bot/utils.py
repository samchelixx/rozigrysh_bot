from aiogram import Bot
from aiogram.enums import ChatMemberStatus

async def prepare_channel_id(bot: Bot, channel_input: str):
    """
    Tries to resolve a channel input (username, link, or ID) to a proper chat_id or username.
    Returns: (id_or_username, chat_object) or (None, None)
    """
    print(f"DEBUG: prepare_channel_id called for '{channel_input}'")
    channel_input = channel_input.strip()
    
    # Handle links like https://t.me/username
    if "t.me/" in channel_input:
        channel_input = channel_input.split("t.me/")[-1].split("/")[0]
        if not channel_input.startswith("@") and not channel_input.startswith("-"):
             channel_input = f"@{channel_input}"
    
    # Handle pure usernames without @
    if not channel_input.startswith("@") and not channel_input.startswith("-") and not channel_input.isdigit():
        channel_input = f"@{channel_input}"
    
    print(f"DEBUG: Resolved input to '{channel_input}', calling get_chat...")
    try:
        chat = await bot.get_chat(channel_input)
        print(f"DEBUG: get_chat success: {chat.id}, {chat.title}")
        return chat.id, chat
    except Exception as e:
        print(f"DEBUG: Could not resolve channel {channel_input}: {e}")
        return None, None

async def is_bot_admin(bot: Bot, chat_id: int) -> bool:
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        return bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception:
        return False

async def check_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    try:
        print(f"DEBUG: Checking {user_id} in {channel_id}")
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        print(f"DEBUG: Status for {user_id} in {channel_id} is {member.status}")
        
        return member.status in [
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED 
        ]
    except Exception as e:
        print(f"ERROR checking subscription for {channel_id}: {e}")
        return False

from aiogram.utils.text_decorations import html_decoration

def get_message_html(message) -> str:
    """
    Extracts HTML formatted text from a message manually.
    """
    if not message.text and not message.caption:
        return ""

    text = message.text or message.caption
    entities = message.entities or message.caption_entities

    if not entities:
        return text

    # Sort entities by offset
    entities = sorted(entities, key=lambda e: e.offset)
    
    formatted_text = ""
    last_offset = 0
    
    # Simple manual reconstruction
    # Note: Nested entities are not handled here, but Telegram usually sends non-nested for basic formatting.
    # Aiogram 3's `message.html_text` is NOT standard, so we do this.
    
    for entity in entities:
        start = entity.offset
        end = start + entity.length
        
        # Text before entity
        chunk = text[last_offset:start]
        formatted_text += html_decoration.quote(chunk)
        
        # Entity text
        entity_text = text[start:end]
        
        if entity.type == "text_link":
            formatted_text += f'<a href="{entity.url}">{html_decoration.quote(entity_text)}</a>'
        elif entity.type == "url":
            formatted_text += f'<a href="{entity_text}">{html_decoration.quote(entity_text)}</a>'
        elif entity.type == "bold":
            formatted_text += f'<b>{html_decoration.quote(entity_text)}</b>'
        elif entity.type == "italic":
            formatted_text += f'<i>{html_decoration.quote(entity_text)}</i>'
        elif entity.type == "code":
            formatted_text += f'<code>{html_decoration.quote(entity_text)}</code>'
        elif entity.type == "pre":
            formatted_text += f'<pre>{html_decoration.quote(entity_text)}</pre>'
        elif entity.type == "strikethrough":
            formatted_text += f'<s>{html_decoration.quote(entity_text)}</s>'
        elif entity.type == "underline":
            formatted_text += f'<u>{html_decoration.quote(entity_text)}</u>'
        else:
            formatted_text += html_decoration.quote(entity_text)
            
        last_offset = end
        
    formatted_text += html_decoration.quote(text[last_offset:])
    return formatted_text
