from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    kb = [
        [KeyboardButton(text="➕ Новое напоминание"), KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="💡 Справка и Команды"), KeyboardButton(text="🔄 Сброс диалога")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_reminders_list_keyboard(reminders: list) -> InlineKeyboardMarkup:
    """Генерирует списочную инлайн-клавиатуру с кнопками управления каждым напоминанием."""
    builder = InlineKeyboardBuilder()
    for rem in reminders:
        rem_id = rem["id"]
        title = rem["title"][:20]  # Обрезаем длинный заголовок для кнопки
        builder.button(text=f"✅ {title}", callback_data=f"rem_done:{rem_id}")
        builder.button(text=f"🗑️", callback_data=f"rem_del:{rem_id}")

    builder.adjust(2)  # По 2 кнопки в ряд (Завершить | Удалить)
    return builder.as_markup()
