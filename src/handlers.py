# Хендлеры пользовательского диалога.
# Декоратор @router.message(...) регистрирует функцию как обработчик события —
# как public-колбэки в Pawn, только фильтры (команда, состояние, тип контента)
# задаются прямо в декораторе, и aiogram сам выбирает подходящий хендлер.

import logging
import re
from datetime import datetime

from aiogram import Bot, F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
import database
import keyboards
from states import OrderForm

logger = logging.getLogger(__name__)

router = Router()


def normalize_phone(raw: str) -> str | None:
    """Убрать пробелы, скобки и дефисы. Вернуть номер или None, если формат кривой."""
    cleaned = re.sub(r"[ \-()]", "", raw.strip())
    if re.fullmatch(r"\+?\d{10,15}", cleaned):
        return cleaned
    return None


# ---------- Старт и отмена ----------

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! 👋\n\n"
        "Я принимаю заявки: расскажите о своей задаче, "
        "и мы свяжемся с вами в ближайшее время.\n\n"
        "Нажмите кнопку, чтобы начать.",
        reply_markup=keyboards.start_kb,
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    # /cancel работает на любом шаге: сбрасываем состояние и собранные данные
    if await state.get_state() is None:
        await message.answer("Сейчас нечего отменять. Нажмите /start, чтобы начать.")
        return
    await state.clear()
    await message.answer(
        "Заявка отменена. Если передумаете — нажмите /start.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ---------- Админские команды ----------
# Регистрируем их до шагов диалога: хендлеры проверяются в порядке объявления,
# и иначе /orders посреди заполнения формы был бы принят как имя или задача.

@router.message(Command("orders"), F.from_user.id == config.ADMIN_ID)
async def cmd_orders(message: Message) -> None:
    orders = database.get_last_orders(10)
    if not orders:
        await message.answer("Заявок пока нет.")
        return

    lines = []
    for row in orders:
        username = f"@{row['tg_username']}" if row["tg_username"] else "—"
        # Задачу обрезаем, иначе 10 длинных заявок не влезут в лимит сообщения
        task = row["task"] if len(row["task"]) <= 100 else row["task"][:100] + "…"
        lines.append(
            f"<b>№{row['id']}</b> · {row['created_at']}\n"
            f"{html.quote(row['name'])}, {html.quote(row['phone'])}, {html.quote(username)}\n"
            f"{html.quote(task)}"
        )
    await message.answer("Последние заявки:\n\n" + "\n\n".join(lines))


@router.message(Command("orders"))
async def cmd_orders_denied(message: Message) -> None:
    await message.answer("Эта команда доступна только администратору. 🙂")


async def notify_admin(bot: Bot, order_id: int, name: str, phone: str, task: str,
                       username: str | None) -> None:
    """Отправить админу уведомление о новой заявке.

    Ошибка отправки (например, админ ещё не написал боту /start) не должна
    ломать диалог с клиентом — поэтому только логируем её.
    """
    username_text = f"@{username}" if username else "—"
    text = (
        f"🔔 Новая заявка <b>№{order_id}</b>\n\n"
        f"<b>Имя:</b> {html.quote(name)}\n"
        f"<b>Телефон:</b> {html.quote(phone)}\n"
        f"<b>Telegram:</b> {html.quote(username_text)}\n"
        f"<b>Задача:</b> {html.quote(task)}\n"
        f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        await bot.send_message(config.ADMIN_ID, text)
    except Exception:
        logger.exception("Не удалось отправить уведомление админу")


@router.callback_query(F.data == "new_order")
async def start_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderForm.name)
    await callback.message.answer("Как вас зовут?")
    # callback.answer() убирает «часики» на кнопке — Telegram ждёт этот ответ
    await callback.answer()


# ---------- Шаг 1: имя ----------

@router.message(OrderForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not (2 <= len(name) <= 50):
        await message.answer("Пожалуйста, введите имя текстом, от 2 до 50 символов.")
        return
    # update_data сохраняет ответ в контексте FSM — данные живут между шагами
    await state.update_data(name=name)
    await state.set_state(OrderForm.phone)
    await message.answer(
        "Оставьте номер телефона: нажмите кнопку ниже "
        "или введите номер вручную.",
        reply_markup=keyboards.phone_kb,
    )


# ---------- Шаг 2: телефон ----------

@router.message(OrderForm.phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext) -> None:
    # Пользователь нажал «Поделиться контактом» — Telegram присылает номер
    # без плюса, добавляем его сами (номер всегда в международном формате)
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await save_phone_and_ask_task(message, state, phone)


@router.message(OrderForm.phone)
async def process_phone_text(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer(
            "Не похоже на номер телефона. 🤔\n"
            "Введите его в формате +380501234567 или нажмите кнопку ниже.",
            reply_markup=keyboards.phone_kb,
        )
        return
    await save_phone_and_ask_task(message, state, phone)


async def save_phone_and_ask_task(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    await state.set_state(OrderForm.task)
    await message.answer(
        "Опишите вашу задачу (от 10 до 1000 символов).",
        reply_markup=ReplyKeyboardRemove(),
    )


# ---------- Шаг 3: задача ----------

@router.message(OrderForm.task)
async def process_task(message: Message, state: FSMContext) -> None:
    task = (message.text or "").strip()
    if not (10 <= len(task) <= 1000):
        await message.answer(
            "Опишите задачу текстом, от 10 до 1000 символов — "
            "так мы сможем сразу понять, чем помочь."
        )
        return
    await state.update_data(task=task)
    await state.set_state(OrderForm.confirm)

    # Показываем всё собранное. html.quote экранирует <, > и & в пользовательском
    # тексте, чтобы он не сломал HTML-разметку сообщения
    data = await state.get_data()
    await message.answer(
        "Проверьте заявку:\n\n"
        f"<b>Имя:</b> {html.quote(data['name'])}\n"
        f"<b>Телефон:</b> {html.quote(data['phone'])}\n"
        f"<b>Задача:</b> {html.quote(data['task'])}",
        reply_markup=keyboards.confirm_kb,
    )


# ---------- Шаг 4: подтверждение ----------

@router.callback_query(OrderForm.confirm, F.data == "confirm_send")
async def confirm_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    order_id = database.add_order(
        name=data["name"],
        phone=data["phone"],
        task=data["task"],
        tg_user_id=callback.from_user.id,
        tg_username=callback.from_user.username,
    )
    logger.info("Новая заявка №%d от %s (%s)", order_id, data["name"], data["phone"])

    await notify_admin(
        callback.bot,
        order_id,
        name=data["name"],
        phone=data["phone"],
        task=data["task"],
        username=callback.from_user.username,
    )

    # Убираем кнопки под сообщением с заявкой, чтобы не нажали второй раз
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"Спасибо! Ваша заявка <b>№{order_id}</b> принята. ✅\n"
        "Мы свяжемся с вами в ближайшее время."
    )
    await callback.answer()


@router.callback_query(OrderForm.confirm, F.data == "confirm_restart")
async def confirm_restart(callback: CallbackQuery, state: FSMContext) -> None:
    # Начинаем сбор заново: чистим данные, но остаёмся в диалоге
    await state.clear()
    await state.set_state(OrderForm.name)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Хорошо, начнём заново. Как вас зовут?")
    await callback.answer()


@router.message(OrderForm.confirm)
async def confirm_typed(message: Message) -> None:
    await message.answer("Нажмите одну из кнопок выше: «Отправить» или «Заполнить заново».")


# Кнопка из старого сообщения (диалог уже завершён или сброшен) —
# отвечаем, чтобы у пользователя не крутились «часики»
@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer("Эта кнопка уже неактуальна. Нажмите /start.")
