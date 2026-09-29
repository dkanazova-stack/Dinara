import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from google import genai
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        if api_key and api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f" Ошибка инициализации Gemini Client: {e}")

        self.user_chats = {}

    def get_user_chat(self, user_id: int):
        """Получает или создает чат сессию для конкретного пользователя."""
        if not self.client:
            return None
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

    async def parse_reminder_with_ai(self, user_text: str) -> Optional[Dict[str, Any]]:
        """
        Использует Gemini для извлечения названия дела/встречи и точного времени напоминания.
        """
        if not self.client:
            return self._fallback_parse_reminder(user_text)

        now = datetime.now()
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S (%A)")

        prompt = f"""
Ты — умный ассистент органайзера и напоминаний.
Текущие дата и время: {current_time_str}.

Проанализируй текст пользователя и определи, содержит ли он запрос на создание напоминания или задачи/встречи.
Если текст содержит запрос на напоминание, извлеки:
1. "title": Краткое название дела или встречи (без слов "напомни", "напоминание" и т.п.).
2. "datetime": Точные дата и время в формате "YYYY-MM-DD HH:MM:SS".

Если дата не указана явно (например "в 18:00"), предполагай сегодня, а если текущее время уже позже 18:00 — тогда завтра.
Если указано "завтра", "через N минут/часов", "в понедельник" и т.д. — высчитай точную дату от текущей даты {current_time_str}.

Верни строго JSON объект следующего вида (без дополнительных слов и разметки):
{{
  "is_reminder": true,
  "title": "Встреча с клиентом",
  "datetime": "2026-09-30 15:00:00"
}}

Если текст НЕ содержит запроса на создание напоминания, верни:
{{
  "is_reminder": false
}}

Текст пользователя: "{user_text}"
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            if response and response.text:
                clean_text = response.text.strip()
                # Удаляем markdown-блоки кода если модель их добавила
                clean_text = re.sub(r"^```json\s*", "", clean_text)
                clean_text = re.sub(r"^```\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text).strip()

                data = json.loads(clean_text)
                if data.get("is_reminder") and data.get("title") and data.get("datetime"):
                    try:
                        parsed_dt = datetime.strptime(data["datetime"], "%Y-%m-%d %H:%M:%S")
                        return {
                            "title": data["title"],
                            "remind_at": parsed_dt
                        }
                    except ValueError:
                        logger.warning(f"Неверный формат даты от Gemini: {data.get('datetime')}")
        except Exception as e:
            logger.error(f"Ошибка при запросе парсинга к Gemini: {e}")

        # Если ИИ не вернул результат, используем запасной регулярный парсер
        return self._fallback_parse_reminder(user_text)

    def _fallback_parse_reminder(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Запасной локальный парсер для простых временных интервалов (через X минут/часов/дней).
        """
        lower = text.lower().strip()
        now = datetime.now()

        # Регулярки для "через N минут/часов/дней"
        match_min = re.search(r"через\s+(\d+)\s*(мин|минуту|минут|минуты)", lower)
        match_hour = re.search(r"через\s+(\d+)\s*(час|часа|часов)", lower)
        match_day = re.search(r"через\s+(\d+)\s*(день|дня|дней)", lower)

        target_dt = None
        clean_title = text

        if match_min:
            minutes = int(match_min.group(1))
            target_dt = now + timedelta(minutes=minutes)
            clean_title = re.sub(r"напомни(ть)?|через\s+\d+\s*(мин|минуту|минут|минуты)", "", text, flags=re.IGNORECASE).strip()
        elif match_hour:
            hours = int(match_hour.group(1))
            target_dt = now + timedelta(hours=hours)
            clean_title = re.sub(r"напомни(ть)?|через\s+\d+\s*(час|часа|часов)", "", text, flags=re.IGNORECASE).strip()
        elif match_day:
            days = int(match_day.group(1))
            target_dt = now + timedelta(days=days)
            clean_title = re.sub(r"напомни(ть)?|через\s+\d+\s*(день|дня|дней)", "", text, flags=re.IGNORECASE).strip()

        if target_dt:
            # Чистим заголовок от лишних знаков
            clean_title = re.sub(r"^(о|про|что|мне|напомни|напоминание)\s+", "", clean_title, flags=re.IGNORECASE).strip()
            if not clean_title:
                clean_title = "Напоминание"
            return {
                "title": clean_title.capitalize(),
                "remind_at": target_dt
            }

        return None

    async def generate_response(self, user_id: int, prompt_text: str) -> str:
        """Отправляет сообщение в Gemini API и возвращает ответ для свободного общения."""
        if not self.client:
            return "⚠️ Gemini API ключ не настроен. Напоминания всё равно работают через прямой ввод!"

        try:
            chat = self.get_user_chat(user_id)
            if not chat:
                return "⚠️ Не удалось создать сессию Gemini."
            response = chat.send_message(prompt_text)

            if response and response.text:
                return response.text
            else:
                return "⚠️ Модель вернула пустой ответ."

        except APIError as e:
            logger.error(f"Ошибка Gemini API для пользователя {user_id}: {e}")
            return f"❌ Ошибка Gemini API: {e.message if hasattr(e, 'message') else str(e)}"
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при запросе к Gemini: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}"

def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Разбивает длинный текст на части не превышающие max_length символов."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at].strip())
        text = text[split_at:].lstrip()

    return chunks
