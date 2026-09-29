import logging
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)
        # Словарь для хранения историй сессий пользователей: user_id -> Chat object
        self.user_chats = {}

    def get_user_chat(self, user_id: int):
        """Получает или создает чат сессию для конкретного пользователя."""
        if user_id not in self.user_chats:
            logger.info(f"Создание новой сессии Gemini для пользователя {user_id}")
            self.user_chats[user_id] = self.client.chats.create(model=self.model_name)
        return self.user_chats[user_id]

    def clear_user_chat(self, user_id: int) -> bool:
        """Сбрасывает контекст диалога с Gemini для пользователя."""
        if user_id in self.user_chats:
            del self.user_chats[user_id]
            logger.info(f"Сессия пользователя {user_id} сброшена")
            return True
        return False

    async def generate_response(self, user_id: int, prompt_text: str) -> str:
        """Отправляет сообщение в Gemini API и возвращает ответ."""
        try:
            chat = self.get_user_chat(user_id)
            # Отправка сообщения в модель в рамках диалога
            response = chat.send_message(prompt_text)
            
            if response and response.text:
                return response.text
            else:
                return "⚠️ Модель вернула пустой ответ или ответ был заблокирован фильтрами безопасности."

        except APIError as e:
            logger.error(f"Ошибка Gemini API для пользователя {user_id}: {e}")
            return f"❌ Ошибка Gemini API: {e.message if hasattr(e, 'message') else str(e)}"
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при запросе к Gemini: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}"

def split_message(text: str, max_length: int = 4000) -> list[str]:
    """
    Разбивает длинный текст на части не превышающие max_length символов
    для безопасной отправки в Telegram (лимит 4096 символов).
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Ищем подходящее место для разрыва (абзац или пробел)
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at].strip())
        text = text[split_at:].lstrip()

    return chunks
