# Клавиатуры бота.
# Inline-кнопки прикрепляются к сообщению и шлют callback (событие с data),
# reply-кнопки заменяют обычную клавиатуру и отправляют текст или контакт.

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Кнопка под приветствием — начать оформление заявки
start_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="new_order")],
])

# Кнопка «Поделиться контактом»: request_contact=True — Telegram сам
# предложит отправить номер, привязанный к аккаунту. Ввести вручную тоже можно.
phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Или введите номер вручную",
)

# Подтверждение собранной заявки
confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_send")],
    [InlineKeyboardButton(text="🔄 Заполнить заново", callback_data="confirm_restart")],
])
