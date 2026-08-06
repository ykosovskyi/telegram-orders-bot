# Точка входа: собираем бота и запускаем long polling.
#
# Про асинхронность: бот почти всё время ждёт сеть (сообщения от Telegram).
# async/await позволяет одному процессу обслуживать много пользователей:
# пока ждём ответа сети по одному диалогу, обрабатываем события других.
# asyncio.run() запускает главный событийный цикл — дальше вся работа идёт
# внутри него, поэтому хендлеры объявлены как async def.

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database
import handlers


async def main() -> None:
    database.init_db()

    # parse_mode=HTML по умолчанию — в сообщениях можно писать <b>жирный</b>
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(handlers.router)

    logging.info("Бот запущен, начинаю polling")
    # start_polling сам переживает сетевые сбои и ошибки в хендлерах:
    # исключение логируется, бот продолжает работать
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
