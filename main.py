import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart, Command

import config
from gemini_service import GeminiService, split_message

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Проверка конфигурации перед инициализацией
if not config.validate_config():
    sys.exit(1)

# Инициализация бота и сервиса Gemini
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
gemini_service = GeminiService(
    api_key=config.GEMINI_API_KEY,
    model_name=config.GEMINI_MODEL
)


@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """Обработчик команды /start"""
    welcome_text = (
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        f"Я Telegram бот с искусственным интеллектом на базе **Google Gemini** ({config.GEMINI_MODEL}).\n\n"
        "💡 **Как использовать:**\n"
        "• Просто отправь мне любое текстовое сообщение или вопрос.\n"
        "• Я помню контекст текущего диалога!\n\n"
        "🛠 **Доступные команды:**\n"
        "• /clear — сбросить контекст диалога\n"
        "• /help — справка по работе с ботом"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("help"))
async def handle_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 **Справка по ИИ-Боту:**\n\n"
        "1. **Общение:** Напишите любой вопрос, тему для обсуждения или задачу.\n"
        "2. **Контекст:** Бот запоминает историю беседы с вами.\n"
        "3. **Сброс диалога:** Чтобы начать тему с чистого листа, отправьте команду `/clear`.\n"
        "4. **Модель:** Используется актуальная модель Google Gemini API.\n"
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("clear"))
async def handle_clear(message: types.Message):
    """Обработчик команды /clear (сброс истории контекста)"""
    user_id = message.from_user.id
    cleared = gemini_service.clear_user_chat(user_id)
    if cleared:
        await message.answer("🔄 **История контекста вашего диалога успешно сброшена!**\nТеперь вы можете начать новую тему.", parse_mode="Markdown")
    else:
        await message.answer("ℹ️ У вас не было активного контекста диалога.", parse_mode="Markdown")


@dp.message(F.text)
async def handle_text_message(message: types.Message):
    """Обработчик текстовых сообщений от пользователя"""
    user_id = message.from_user.id
    user_input = message.text

    # Отправляем индикатор печатания "typing..."
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # Запрос к Gemini
    response_text = await gemini_service.generate_response(user_id, user_input)

    # Разбиваем текст на части, если он превышает лимит Telegram в 4000 символов
    chunks = split_message(response_text)

    for chunk in chunks:
        try:
            # Сначала пробуем отправить в формате Markdown
            await message.answer(chunk, parse_mode="Markdown")
        except Exception:
            # Если возникла ошибка разметки Markdown, отправляем обычным текстом
            await message.answer(chunk)


async def main():
    logger.info("Запуск бота Telegram с Gemini API...")
    try:
        # Пропуск накопившихся обновлений при выключенном боте
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
