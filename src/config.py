# Чтение настроек из .env
# Секреты держим вне кода: load_dotenv() подгружает переменные из файла .env
# в окружение процесса, дальше читаем их через os.getenv.

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# База лежит в корне проекта, путь строим от расположения этого файла,
# чтобы бот работал независимо от того, из какой папки его запустили
DB_PATH = Path(__file__).resolve().parent.parent / "orders.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Скопируй .env.example в .env и заполни его.")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID не задан. Скопируй .env.example в .env и заполни его.")
