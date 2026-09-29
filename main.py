import asyncio
import logging
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
from gemini_service import GeminiService, split_message
from keyboards import get_main_menu_keyboard, get_reminders_list_keyboard
from scheduler import start_reminder_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Проверка конфигурации перед запуском
if not config.validate_config():
    sys.exit(1)

# Инициализация базы данных
database.init_db()

# Инициализация бота и сервиса Gemini
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
gemini_service = GeminiService(
    api_key=config.GEMINI_API_KEY,
    model_name=config.GEMINI_MODEL
)


class ReminderStates(StatesGroup):
    waiting_for_reminder_text = State()


@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        f"Я твой персональный **Telegram Бот-Органайзер** с ИИ на базе **Google Gemini**!\n\n"
        f"⏰ **Я помогу тебе никогда не забывать о встречах и делах.**\n\n"
        f"💡 **Как создавать напоминания:**\n"
        f"Просто напиши мне своими словами, например:\n"
        f"• *«Напомни завтра в 15:00 про встречу с клиентом»*\n"
        f"• *«Через 45 минут выключить духовку»*\n"
        f"• *«Встреча со стоматологом 5 октября в 12:30»*\n"
        f"• *«Напомни вечером купить молоко»*\n\n"
        f"🤖 Также ты можешь задавать мне любые вопросы — я отреагирую как умный ассистент!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())


@dp.message(Command("help"))
@dp.message(F.text == "💡 Справка и Команды")
async def handle_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 **Справка по использованию бота:**\n\n"
        "1️⃣ **Быстрое создание напоминания:**\n"
        "Напишите текст в чат: `Напомни через 20 минут позвонить маме`.\n"
        "ИИ автоматически выделит название дела, дату и точное время!\n\n"
        "2️⃣ **Посмотреть список дел:**\n"
        "Отправьте команду `/list` или нажмите кнопку **📋 Мои напоминания**.\n\n"
        "3️⃣ **Управление:**\n"
        "В списке напоминаний вы можете отмечать выполненные дела (✅) или удалять ненужные (🗑️).\n\n"
        "4️⃣ **Свободное общение:**\n"
        "Задавайте любые вопросы ИИ Gemini, когда не ставите задачи."
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("list"))
@dp.message(F.text == "📋 Мои напоминания")
async def handle_list_reminders(message: types.Message):
    """Отображение всех активных напоминаний пользователя."""
    user_id = message.from_user.id
    reminders = database.get_user_reminders(user_id)

    if not reminders:
        await message.answer(
            "📋 **У вас пока нет активных напоминаний!**\n\n"
            "Напишите мне, например: *«Напомни завтра в 10:00 провести созвон»*, чтобы добавить первое.",
            parse_mode="Markdown"
        )
        return

    text_lines = ["📋 **Ваши активные напоминания и встречи:**\n"]
    for i, rem in enumerate(reminders, 1):
        rem_dt = rem["remind_at"]
        text_lines.append(f"{i}. 📌 **{rem['title']}**")
        text_lines.append(f"   🕒 Время: `{rem_dt}`\n")

    text_lines.append("Нажмите на кнопки ниже, чтобы отметить выполненным (✅) или удалить (🗑️):")

    await message.answer(
        "\n".join(text_lines),
        parse_mode="Markdown",
        reply_markup=get_reminders_list_keyboard(reminders)
    )


@dp.message(Command("add"))
@dp.message(F.text == "➕ Новое напоминание")
async def handle_add_prompt(message: types.Message, state: FSMContext):
    """Подсказка пользователю для ввода нового напоминания."""
    await state.set_state(ReminderStates.waiting_for_reminder_text)
    prompt_msg = (
        "✍️ **Напишите ваше напоминание или встречу:**\n\n"
        "Примеры:\n"
        "• *«Напомни завтра в 14:00 встреча с инвестором»*\n"
        "• *«Через 30 минут забрать посылку»*\n"
        "• *«Оплата интернета 1 числа в 09:00»*"
    )
    await message.answer(prompt_msg, parse_mode="Markdown")


@dp.message(Command("clear"))
@dp.message(F.text == "🔄 Сброс диалога")
async def handle_clear(message: types.Message):
    """Сброс контекста диалога с ИИ."""
    user_id = message.from_user.id
    cleared = gemini_service.clear_user_chat(user_id)
    if cleared:
        await message.answer("🔄 **Контекст общения с ИИ сброшен!**", parse_mode="Markdown")
    else:
        await message.answer("ℹ️ История общения пуста.", parse_mode="Markdown")


# --- ОБРАБОТЧИКИ INLINE КНОПОК ---

@dp.callback_query(F.data.startswith("rem_done:"))
async def handle_reminder_done(callback: types.CallbackQuery):
    """Отметка напоминания как выполненного."""
    rem_id = int(callback.data.split(":")[1])
    database.mark_reminder_completed(rem_id)
    await callback.answer("✅ Отмечено как выполненное!")
    await callback.message.edit_text("✅ **Напоминание выполнено и перенесено в архив!**", parse_mode="Markdown")


@dp.callback_query(F.data.startswith("rem_del:"))
async def handle_reminder_delete(callback: types.CallbackQuery):
    """Удаление напоминания."""
    rem_id = int(callback.data.split(":")[1])
    database.delete_reminder(rem_id, callback.from_user.id)
    await callback.answer("🗑️ Напоминание удалено!")
    await callback.message.edit_text("🗑️ **Напоминание успешно удалено.**", parse_mode="Markdown")


@dp.callback_query(F.data.startswith("rem_snooze:"))
async def handle_reminder_snooze(callback: types.CallbackQuery):
    """Откладывание напоминания на N минут."""
    parts = callback.data.split(":")
    rem_id = int(parts[1])
    minutes = int(parts[2])

    new_dt = datetime.now() + timedelta(minutes=minutes)
    database.snooze_reminder(rem_id, new_dt)

    new_time_str = new_dt.strftime("%Y-%m-%d %H:%M:%S")
    await callback.answer(f"⏰ Отложено на {minutes} мин!")
    await callback.message.edit_text(
        f"⏰ **Напоминание отложено!**\nНовое время: `{new_time_str}`",
        parse_mode="Markdown"
    )


# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---

@dp.message(F.text)
async def handle_user_text(message: types.Message, state: FSMContext):
    """Главный обработчик текста: парсит напоминание либо отвечает через ИИ."""
    user_id = message.from_user.id
    user_text = message.text

    await state.clear()
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # 1. Пробуем распознать напоминание в тексте через Gemini AI или локальный парсер
    parsed = await gemini_service.parse_reminder_with_ai(user_text)

    if parsed and parsed.get("remind_at") and parsed.get("title"):
        title = parsed["title"]
        remind_at = parsed["remind_at"]

        # Если время напоминания в прошлом, переносим на будущее или на 1 минуту
        if remind_at <= datetime.now():
            remind_at = datetime.now() + timedelta(minutes=1)

        rem_id = database.add_reminder(user_id, title, remind_at)
        time_str = remind_at.strftime("%d.%m.%Y в %H:%M:%S")

        confirm_text = (
            f"✅ **Напоминание успешно создано!**\n\n"
            f"📌 **Дело/Встреча:** {title}\n"
            f"🕒 **Дата и время:** `{time_str}`\n\n"
            f"🔔 Я пришлю вам уведомление точно в указанное время!"
        )
        await message.answer(confirm_text, parse_mode="Markdown")
        return

    # 2. Если это не напоминание, отправляем вопрос в свободный ИИ чат Gemini
    response_text = await gemini_service.generate_response(user_id, user_text)
    chunks = split_message(response_text)

    for chunk in chunks:
        try:
            await message.answer(chunk, parse_mode="Markdown")
        except Exception:
            await message.answer(chunk)


async def main():
    logger.info("Запуск Telegram Бота Напоминаний с Gemini ИИ...")

    # Запуск фоновой задачи проверки напоминаний
    asyncio.create_task(start_reminder_scheduler(bot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
