from aiogram.fsm.state import State, StatesGroup

class GiveawayCreation(StatesGroup):
    waiting_for_media = State()
    waiting_for_description = State()
    waiting_for_channels = State()
    waiting_for_button_text = State()
    waiting_for_publish_channel = State()
    waiting_for_confirmation = State()
