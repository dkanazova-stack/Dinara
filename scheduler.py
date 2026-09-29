import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database

logger = logging.getLogger(__name__)

def get_reminder_action_keyboard(reminder_id: int) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру действия для сработавшего напоминания."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=f"rem_done:{reminder_id}")
    builder.button(text="⏰ +15 мин", callback_data=f"rem_snooze:{reminder_id}:15")
    builder.button(text="⏰ +1 час", callback_data=f"rem_snooze:{reminder_id}:60")
    builder.button(text="⏰ На завтра", callback_data=f"rem_snooze:{reminder_id}:1440")
    builder.adjust(1, 3)
    return builder.as_markup()

async def check_and_send_reminders(bot: Bot):
    """Проверяет базу данных и отправляет сработавшие напоминания."""
    try:
        due_reminders = database.get_due_reminders()
        for rem in due_reminders:
            rem_id = rem["id"]
            user_id = rem["user_id"]
            title = rem["title"]
            remind_at_str = rem["remind_at"]

            # Отмечаем как выполненное/отправленное
            database.mark_reminder_completed(rem_id)

            msg_text = (
                f"🔔 **НАПОМИНАНИЕ!**\n\n"
                f"📌 **Дело/Встреча:** {title}\n"
                f"🕒 **Запланировано на:** {remind_at_str}\n\n"
                f"Не забудьте выполнить эту задачу!"
            )

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=msg_text,
                    parse_mode="Markdown",
                    reply_markup=get_reminder_action_keyboard(rem_id)
                )
                logger.info(f"Напоминание {rem_id} отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить напоминание {rem_id} пользователю {user_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка в цикле планировщика напоминаний: {e}")

async def start_reminder_scheduler(bot: Bot, check_interval_seconds: int = 10):
    """Фоновая асинхронная задача планировщика."""
    logger.info("Запуск фонового планировщика напоминаний...")
    while True:
        await check_and_send_reminders(bot)
        await asyncio.sleep(check_interval_seconds)
