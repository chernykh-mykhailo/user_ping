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
