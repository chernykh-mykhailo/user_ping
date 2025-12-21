"""
Telegram Ping Bot - Main Entry Point
Архітектура з SOLID принципами та ООП
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram import F
from aiogram.types import BotCommand, BotCommandScopeDefault

# Version
from __version__ import __version__

# Конфігурація
from config import (
    API_ID, API_HASH, SESSION_NAME,
    BOT_TOKEN, DB_FILE, USE_USERBOT
)

# Core components
from core import JSONDatabase, ChatRepository, PremiumRepository, ChatPremiumRepository, ReferralRepository

# Userbot
from userbot import UserbotCollector

# Handlers
from handlers import (
    AdminHandler,
    PingHandler,
    UserHandler,
    PaymentHandler,
    SettingsHandler
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
        self.chat_premium_repo = ChatPremiumRepository(self.db)
        self.referral_repo = ReferralRepository(self.db)
        
        # Bot та Dispatcher
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher()
        
        # Userbot (Dynamic state)
        self.use_userbot = self.chat_repo.get_global_setting("use_userbot", USE_USERBOT)
        
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
        
        # Реєструємо Middleware (v1.6.0)
        from core.middleware import ActivityMiddleware
        self.dp.message.outer_middleware(ActivityMiddleware(self.chat_repo))
        
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
            self.chat_premium_repo,
            self.referral_repo,
            self.bot,
            self.userbot
        )
        
        self.settings_handler = SettingsHandler(
            self.chat_repo,
            self.premium_repo
        )
        
        # Реєстрація роутерів
        self._register_routers()
    
    def _register_routers(self):
        """Реєструє всі роутери"""
        # Порядок важливий! Специфічні хендлери мають бути першими
        self.dp.include_router(self.admin_handler.get_router())
        self.logger.info("✓ Admin router registered")

        self.dp.include_router(self.payment_handler.get_router())
        self.logger.info("✓ Payment router registered")
        
        self.dp.include_router(self.settings_handler.get_router())
        self.logger.info("✓ Settings router registered")
        
        self.dp.include_router(self.user_handler.get_router())
        self.logger.info("✓ User router registered")
        
        # PingHandler реєструємо останнім, бо він має catch-all хендлер
        self.dp.include_router(self.ping_handler.get_router())
        self.logger.info("✓ Ping router registered")

    async def _setup_commands(self):
        """Встановлює команди бота для меню"""
        commands = [
            BotCommand(command="all", description="📢 Викликати всіх"),
            BotCommand(command="stop", description="🛑 Зупинити виклик"),
            BotCommand(command="settings", description="⚙️ Налаштування"),
            BotCommand(command="stats", description="📊 Статистика"),
            BotCommand(command="sync", description="🔄 Оновити базу"),
            BotCommand(command="help", description="ℹ️ Довідка"),
            BotCommand(command="premium", description="👑 Premium меню"),
            BotCommand(command="emoji", description="🤪 Виклик емодзі"),
            BotCommand(command="admins", description="👮 Виклик адмінів"),
            BotCommand(command="anybody", description="🎲 Випадковий юзер"),
            BotCommand(command="unreg", description="🔇 Вимкнути пінг (тимчасово)"),
            BotCommand(command="superunreg", description="🚫 Вимкнути пінг (Premium)"),
            BotCommand(command="reg", description="🔔 Увімкнути пінг"),
            BotCommand(command="gunreg", description="🌍 Глобальний анрег (всі чати)"),
            BotCommand(command="gsuperunreg", description="👑 Глобальний SuperUnreg"),
            BotCommand(command="greg", description="🔔 Глобальний рег"),
        ]
        
        try:
            await self.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
            self.logger.info("✓ Bot commands registered")
        except Exception as e:
            self.logger.error(f"Failed to register commands: {e}")
    
    async def _handle_pending_updates(self):
        """Обробляє накопичені повідомлення після перезапуску"""
        try:
            # Отримуємо всі накопичені оновлення (до 100)
            updates = await self.bot.get_updates()
            
            if not updates:
                return
            
            from utils.helpers import get_clean_chat_id
            
            last_update = updates[-1]
            last_command_update = None
            
            # Шукаємо останню команду або звернення серед накопичених
            # (переглядаємо з кінця, щоб знайти найсвіжішу команду)
            for upd in reversed(updates):
                if upd.message and upd.message.text:
                    text = upd.message.text.strip()
                    if not text:
                        continue
                        
                    # 1. Перевірка на явний префікс команди
                    is_command = text.startswith(('/', '!'))
                    
                    # 2. Перевірка на кастомні тригери без префіксів
                    if not is_command:
                        chat_id = get_clean_chat_id(upd.message.chat.id)
                        first_word = text.split()[0].lower()
                        
                        custom = self.chat_repo.get_custom_ping_triggers(chat_id)
                        chat_t = self.chat_repo.get_call_triggers(chat_id)
                        
                        if first_word in custom or first_word in chat_t:
                            is_command = True
                    
                    if is_command:
                        last_command_update = upd
                        break
            
            # Якщо знайшли команду - повідомляємо про перезапуск
            if last_command_update:
                try:
                    chat_id = get_clean_chat_id(last_command_update.message.chat.id)
                    should_notify = self.chat_repo.get_setting(chat_id, "restart_notice", True)
                    
                    if should_notify:
                        await self.bot.send_message(
                            last_command_update.message.chat.id,
                            "🔄 <b>Бот перезапущено!</b>\n\n"
                            "Ви надсилали команду поки бот був офлайн. Будь ласка, <b>повторіть її</b>.",
                            parse_mode="HTML",
                            reply_to_message_id=last_command_update.message.message_id
                        )
                        self.logger.info(f"Restart notification sent to {last_command_update.message.chat.id}")
                    else:
                        self.logger.info(f"Restart notification suppressed by setting in chat {chat_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to send restart notification: {e}")
            
            # У будь-якому випадку пропускаємо всі старі updates
            await self.bot.get_updates(offset=last_update.update_id + 1)
            self.logger.info(f"Skipped {len(updates)} pending updates after restart")
            
        except Exception as e:
            self.logger.warning(f"Error handling pending updates: {e}")
    
    async def start(self):
        """Запускає бота"""
        try:
            # Запускаємо userbot тільки якщо він увімкнений
            if self.use_userbot:
                success = await self.userbot.start()
                if not success:
                    self.logger.warning("⚠️ Юзербот не зміг запуститися (необхідна авторизація). Основний бот працюватиме без функцій збору.")
            else:
                self.logger.info("Userbot is DISABLED by global setting")
            
            # Реєструємо команди
            await self._setup_commands()
            
            # Обробляємо накопичені повідомлення
            await self._handle_pending_updates()
            
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
        if self.use_userbot:
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