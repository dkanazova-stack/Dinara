import os
import sys
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

def validate_config():
    """Проверка наличия обязательных ключей в конфигурации."""
    errors = []
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here":
        errors.append("BOT_TOKEN не задан в .env файле (получите у @BotFather в Telegram)")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        errors.append("GEMINI_API_KEY не задан в .env файле (получите на https://aistudio.google.com/)")

    if errors:
        print("\n❌ Ошибка конфигурации:")
        for err in errors:
            print(f"  - {err}")
        print("\nПожалуйста, укажите реальные токены в файле .env перед запуском бота.\n")
        return False
    return True
