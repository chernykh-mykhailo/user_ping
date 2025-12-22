"""
Base handler - Abstract base class (OCP, LSP)
"""
from abc import ABC, abstractmethod
from aiogram import Router
from aiogram.types import Message
from core.database import ChatRepository, PremiumRepository


class BaseHandler(ABC):
    """
    Базовий клас для всіх хендлерів
    Open/Closed Principle: відкритий для розширення, закритий для модифікації
    Liskov Substitution Principle: всі нащадки можуть замінити базовий клас
    """
    
    def __init__(
        self,
        chat_repo: ChatRepository,
        premium_repo: PremiumRepository
    ):
        self.chat_repo = chat_repo
        self.premium_repo = premium_repo
        self.router = Router()
        
        # Кожен нащадок реєструє свої хендлери
        self.register_handlers()
    
    @abstractmethod
    def register_handlers(self):
        """
        Реєструє хендлери для роутера
        Кожен нащадок повинен реалізувати цей метод
        """
        pass
    
    def get_router(self) -> Router:
        """Повертає роутер з зареєстрованими хендлерами"""
        return self.router
        
    async def auto_cleanup(self, message: Message, bot_message: Message = None, custom_delay: int = None):
        """
        Автоматично видаляє повідомлення користувача та бота через заданий час
        Спільно для всіх хендлерів
        """
        import asyncio
        from utils.helpers import get_clean_chat_id
        
        # Визначаємо затримку
        if custom_delay is not None:
            delay = custom_delay
        else:
            chat_id = get_clean_chat_id(message.chat.id)
            # Отримуємо налаштування (за замовчуванням 0 - вимкнено)
            delay = self.chat_repo.get_setting(chat_id, "auto_cleanup", 0)
        
        if delay > 0:
            await asyncio.sleep(delay)
            try:
                # Видаляємо повідомлення користувача
                await message.delete()
            except:
                pass
                
            if bot_message:
                try:
                    # Видаляємо повідомлення бота
                    await bot_message.delete()
                except:
                    pass
    async def _safe_answer(self, message: Message, text: str, **kwargs):
        """Відправляє відповідь з обробкою FloodControl (v1.6.6)"""
        import asyncio
        import re
        from aiogram.exceptions import TelegramRetryAfter
        
        while True:
            try:
                return await message.answer(text, **kwargs)
            except TelegramRetryAfter as e:
                # Якщо це Flood Control - чекаємо
                import logging
                logging.getLogger(__name__).warning(f"Flood Control! Чекаємо {e.retry_after}с перед відповіддю на {message.text}")
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Помилка при безпечній відправці: {e}")
                # Для звичайних помилок - один раз пробуємо просто відправити
                try: return await message.answer(text, **kwargs)
                except: return None
