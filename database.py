import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_NAME = "reminders.db"

def init_db():
    """Инициализация базы данных и создание таблиц."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_status ON reminders (user_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remind_status ON reminders (remind_at, status)")
        conn.commit()
    logger.info("База данных инициализирована.")

def add_reminder(user_id: int, title: str, remind_at: datetime) -> int:
    """Добавление нового напоминания."""
    remind_at_str = remind_at.strftime("%Y-%m-%d %H:%M:%S")
    created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders (user_id, title, remind_at, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (user_id, title, remind_at_str, created_at_str))
        conn.commit()
        return cursor.lastrowid

def get_user_reminders(user_id: int, status: str = "pending") -> List[Dict[str, Any]]:
    """Получение всех активных напоминаний пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, remind_at, created_at, status
            FROM reminders
            WHERE user_id = ? AND status = ?
            ORDER BY remind_at ASC
        """, (user_id, status))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_due_reminders() -> List[Dict[str, Any]]:
    """Получение всех напоминаний, время которых уже наступило."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, title, remind_at
            FROM reminders
            WHERE status = 'pending' AND remind_at <= ?
            ORDER BY remind_at ASC
        """, (now_str,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def mark_reminder_completed(reminder_id: int) -> bool:
    """Отметка напоминания как выполненного."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reminders
            SET status = 'completed'
            WHERE id = ?
        """, (reminder_id,))
        conn.commit()
        return cursor.rowcount > 0

def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Удаление напоминания пользователем."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM reminders
            WHERE id = ? AND user_id = ?
        """, (reminder_id, user_id))
        conn.commit()
        return cursor.rowcount > 0

def snooze_reminder(reminder_id: int, new_remind_at: datetime) -> bool:
    """Откладывание напоминания на новое время."""
    remind_at_str = new_remind_at.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reminders
            SET remind_at = ?, status = 'pending'
            WHERE id = ?
        """, (remind_at_str, reminder_id))
        conn.commit()
        return cursor.rowcount > 0
