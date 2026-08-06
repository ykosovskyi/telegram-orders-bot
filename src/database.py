# Работа с SQLite без ORM — обычные SQL-запросы через модуль sqlite3.
# Соединение открываем на каждую операцию: для SQLite это дёшево,
# зато нет проблем с "висящим" соединением и блокировками файла.

import sqlite3
from datetime import datetime

from config import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # row_factory даёт доступ к колонкам по имени: row["name"] вместо row[1]
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создать таблицу заявок, если её ещё нет. Вызывается при старте бота."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                phone       TEXT NOT NULL,
                task        TEXT NOT NULL,
                tg_user_id  INTEGER NOT NULL,
                tg_username TEXT,
                created_at  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'new'
            )
        """)


def add_order(name: str, phone: str, task: str,
              tg_user_id: int, tg_username: str | None) -> int:
    """Сохранить заявку и вернуть её номер (id)."""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cursor = conn.execute(
            # Знаки ? — плейсхолдеры sqlite3: значения подставляются безопасно,
            # SQL-инъекция через имя или текст задачи невозможна
            "INSERT INTO orders (name, phone, task, tg_user_id, tg_username, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, phone, task, tg_user_id, tg_username, created_at),
        )
        return cursor.lastrowid


def get_last_orders(limit: int = 10) -> list[sqlite3.Row]:
    """Последние заявки, новые сверху. Для команды /orders."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def get_all_orders() -> list[sqlite3.Row]:
    """Все заявки по порядку. Для выгрузки в xlsx."""
    with _connect() as conn:
        return conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
