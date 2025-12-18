"""
Telegram Ping Bot - Main Entry Point
Архітектура з SOLID принципами та ООП
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram import F

# Version
from __version__ import __version__

# Конфігурація
from config import (
    API_ID, API_HASH, SESSION_NAME,
    BOT_TOKEN, DB_FILE
)

# Core components
from core import JSONDatabase, ChatRepository, PremiumRepository

# Userbot
from userbot import UserbotCollector

# Handlers
from handlers import (
    AdminHandler,
    PingHandler,
    UserHandler,
    PaymentHandler
)


class PingBot:
    """
    Головний клас бота
    Dependency Injection: всі залежності передаються ззовні
    """
    
    def __init__(self):
        # Налаштування логування
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s:%(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Ініціалізація компонентів (Dependency Injection)
        self.db = JSONDatabase(DB_FILE)
        self.chat_repo = ChatRepository(self.db)
        self.premium_repo = PremiumRepository(self.db)
        
        # Bot та Dispatcher
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher()
        
        # Userbot
        self.userbot = UserbotCollector(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=SESSION_NAME,
            chat_repo=self.chat_repo
        )
        
        # Handlers (кожен відповідає за свою частину)
        self.admin_handler = AdminHandler(
            self.chat_repo,
            self.premium_repo,
            self.bot,
            self.userbot
        )
        
        self.ping_handler = PingHandler(
            self.chat_repo,
            self.premium_repo,
            self.bot
        )
        
        self.user_handler = UserHandler(
            self.chat_repo,
            self.premium_repo
        )
        
        self.payment_handler = PaymentHandler(
            self.chat_repo,
            self.premium_repo,
            self.bot
        )
        
        # Реєстрація роутерів
        self._register_routers()
    
    def _register_routers(self):
        """Реєструє всі роутери"""
        # Порядок важливий! Специфічні хендлери мають бути першими
        self.dp.include_router(self.admin_handler.get_router())
        self.logger.info("✓ Admin router registered")
        
        self.dp.include_router(self.ping_handler.get_router())
        self.logger.info("✓ Ping router registered")
        
        self.dp.include_router(self.user_handler.get_router())
        self.logger.info("✓ User router registered")
        
        self.dp.include_router(self.payment_handler.get_router())
        self.logger.info("✓ Payment router registered")
    
    async def start(self):
        """Запускає бота"""
        try:
            # Запускаємо userbot
            await self.userbot.start()
            
            self.logger.info("=" * 50)
            self.logger.info(f"🚀 TELEGRAM PING BOT v{__version__}")
            self.logger.info("=" * 50)
            
            # Запускаємо polling
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            self.logger.error(f"Критична помилка: {e}")
            raise
    
    async def stop(self):
        """Зупиняє бота"""
        await self.userbot.stop()
        await self.bot.session.close()
        self.logger.info("=" * 50)
        self.logger.info("🛑 СИСТЕМА ЗУПИНЕНА")
        self.logger.info("=" * 50)


async def main():
    """Головна функція"""
    bot = PingBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logging.info("Отримано сигнал зупинки...")
        await bot.stop()
    except Exception as e:
        logging.error(f"Фатальна помилка: {e}")
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Не виводимо traceback, просто чисте повідомлення
        print("\n" + "=" * 50)
        print("🛑 СИСТЕМА ЗУПИНЕНА")
        print("=" * 50)
    except Exception as e:
        logging.error(f"Критична помилка: {e}")