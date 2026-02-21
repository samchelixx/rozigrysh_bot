from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def main_admin_keyboard():
    kb = [
        [KeyboardButton(text="🎁 Создать розыгрыш")],
        [KeyboardButton(text="📋 Список розыгрышей"), KeyboardButton(text="👥 Список участников")],
        [KeyboardButton(text="⚙️ Управление")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_keyboard():
    kb = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Опубликовать", callback_data="publish_giveaway")
    builder.button(text="❌ Отменить", callback_data="cancel_giveaway")
    return builder.as_markup()
