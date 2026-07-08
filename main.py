import warnings

# 1. Придушуємо варнінги Pydantic ПЕРЕД усім іншим
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.*")
warnings.filterwarnings("ignore", message='.*protected namespace "model_".*')

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram import F
from aiogram.types import BotCommand, BotCommandScopeDefault

# Version
from __version__ import __version__
from datetime import datetime, timedelta

# Конфігурація
from config import (
    API_ID,
    API_HASH,
    SESSION_NAME,
    BOT_TOKEN,
    DB_FILE,
    USE_USERBOT,
    SESSION_STORAGE,
)

# Core components
from core import (
    JSONDatabase,
    ChatRepository,
    PremiumRepository,
    ChatPremiumRepository,
    ReferralRepository,
)

# Userbot
from userbot import UserbotCollector

# Handlers
from handlers import (
    AdminHandler,
    PingHandler,
    UserHandler,
    PaymentHandler,
    SettingsHandler,
)
from core.services.emoji_service import EmojiPackService


class PingBot:
    """
    Головний клас бота
    Dependency Injection: всі залежності передаються ззовні
    """

    def __init__(self):
        # Налаштування логування
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
        self.logger = logging.getLogger(__name__)

        # Ініціалізація компонентів (Dependency Injection)
        self.db = JSONDatabase(DB_FILE)
        self.chat_repo = ChatRepository(self.db)
        self.premium_repo = PremiumRepository(self.db)
        self.chat_premium_repo = ChatPremiumRepository(self.db)
        self.referral_repo = ReferralRepository(self.db)

        # Bot та Dispatcher
        self.bot = Bot(token=BOT_TOKEN)
        
        # FSM Storage (v2.11.0) - MUST be passed to Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        # Userbot (Dynamic state)
        self.use_userbot = self.chat_repo.get_global_setting("use_userbot", USE_USERBOT)

        # v2.6.2: Робимо назву сесії персистентною (беремо з бази, якщо є)
        active_session = self.chat_repo.get_global_setting(
            "active_session_name", SESSION_NAME
        )

        self.userbot = UserbotCollector(
            api_id=API_ID,
            api_hash=API_HASH,
            session_name=active_session,
            chat_repo=self.chat_repo,
            session_storage=SESSION_STORAGE,
        )

        # Services
        self.emoji_service = EmojiPackService(self.bot, self.chat_repo)

        # Handlers (кожен відповідає за свою частину)
        self.admin_handler = AdminHandler(
            self.chat_repo,
            self.premium_repo,
            self.bot,
            self.userbot,
            self.emoji_service,
        )

        # Реєструємо Middleware (v1.6.0)
        from core.middleware import ActivityMiddleware

        # Register ActivityMiddleware AFTER FSM middleware (use outer_middleware but FSM runs first)
        self.dp.message.outer_middleware(ActivityMiddleware(self.chat_repo, self.bot))

        self.ping_handler = PingHandler(
            self.chat_repo, self.premium_repo, self.bot, self.userbot, self.use_userbot, storage=self.storage
        )

        self.user_handler = UserHandler(
            self.chat_repo, self.premium_repo, self.emoji_service, self.bot
        )

        self.payment_handler = PaymentHandler(
            self.chat_repo,
            self.premium_repo,
            self.chat_premium_repo,
            self.referral_repo,
            self.bot,
            self.userbot,
        )

        self.settings_handler = SettingsHandler(self.chat_repo, self.premium_repo)

        # v2.3.0: Onboarding - Welcome message при додаванні бота
        from aiogram.types import ChatMemberUpdated
        from aiogram import F

        @self.dp.my_chat_member(
            F.new_chat_member.status.in_(["member", "administrator"])
            & F.old_chat_member.status.in_(["left", "kicked"])
        )
        async def bot_added_to_chat(event: ChatMemberUpdated):
            """Відправляє welcome message коли бота вперше додають в групу"""
            if event.chat.type in ["group", "supergroup"]:
                await self.bot.send_message(
                    event.chat.id,
                    "👋 <b>Вітаю! Ping Bot готовий до роботи!</b>\n\n"
                    "📋 <b>Швидкий старт:</b>\n"
                    "1️⃣ Зробіть мене <b>адміністратором</b> (необов'язково, але рекомендовано)\n"
                    "2️⃣ Виконайте <code>/sync</code> для синхронізації учасників\n"
                    "3️⃣ Готово! Тепер можна використовувати <code>/all</code>, <code>/anybody</code> та інші команди\n\n"
                    "💡 Синхронізація відбувається автоматично щоночі о 03:00, але для першого запуску краще зробити вручну.\n\n"
                    "❓ Всі команди: /help",
                    parse_mode="HTML",
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
            BotCommand(command="help", description="ℹ️ Довідка"),
            BotCommand(command="settings", description="⚙️ Налаштування"),
            BotCommand(command="stop", description="🛑 Зупинити виклик"),
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
                    is_command = text.startswith(("/", "!"))

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
                    should_notify = self.chat_repo.get_setting(
                        chat_id, "restart_notice", True
                    )

                    if should_notify:
                        await self.bot.send_message(
                            last_command_update.message.chat.id,
                            "🔄 <b>Бот перезапущено!</b>\n\n"
                            "Ви надсилали команду поки бот був офлайн. Будь ласка, <b>повторіть її</b>.",
                            parse_mode="HTML",
                            reply_to_message_id=last_command_update.message.message_id,
                        )
                        self.logger.info(
                            f"Restart notification sent to {last_command_update.message.chat.id}"
                        )
                    else:
                        self.logger.info(
                            f"Restart notification suppressed by setting in chat {chat_id}"
                        )
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
                    self.logger.warning(
                        "⚠️ Юзербот не зміг запуститися (необхідна авторизація). Основний бот працюватиме без функцій збору."
                    )
            else:
                self.logger.info("Userbot is DISABLED by global setting")

            # Реєструємо команди
            await self._setup_commands()

            # Обробляємо накопичені повідомлення
            await self._handle_pending_updates()

            # Запускаємо фонові завдання (v1.9.0)
            asyncio.create_task(self._nightly_sync_task())

            self.logger.info("=" * 50)
            self.logger.info(f"🚀 TELEGRAM PING BOT v{__version__}")
            self.logger.info("=" * 50)

            # Запускаємо polling з відстеженням виходу учасників
            allowed_updates = [
                "message",
                "callback_query",
                "chat_member",
                "my_chat_member",
                "pre_checkout_query",
            ]
            await self.dp.start_polling(self.bot, allowed_updates=allowed_updates)

        except Exception as e:
            self.logger.error(f"Критична помилка: {e}")

    async def _nightly_sync_task(self):
        """Фонове завдання для нічної синхронізації (v1.9.0)"""
        self.logger.info("Нічне фонове завдання синхронізації активовано")

        while True:
            try:
                # Обчислюємо час до 03:00 ночі
                now = datetime.now()
                target = now.replace(hour=3, minute=0, second=0, microsecond=0)

                if now >= target:
                    target += timedelta(days=1)

                wait_seconds = (target - now).total_seconds()
                self.logger.info(
                    f"Наступна синхронізація запланована на {target} (через {wait_seconds / 3600:.1f} год)"
                )

                await asyncio.sleep(wait_seconds)

                if not self.use_userbot:
                    continue

                self.logger.info("🌙 Починаю планову нічну синхронізацію...")

                # Отримуємо всі чати з бази
                chats = self.chat_repo.get_all_chats()

                for chat_id_str in chats:
                    try:
                        # Перетворюємо ID для Telethon (число)
                        try:
                            # Більшість ID чатів у Telegram - від'ємні числа
                            target_id = int(chat_id_str)
                        except:
                            target_id = chat_id_str  # Якщо це username (рідко для бази)

                        self.logger.info(f"🔄 Синхронізація чату {chat_id_str}...")
                        await self.userbot.sync_participants(target_id)

                        # Анти-флуд затримка 30 сек між чатами
                        await asyncio.sleep(30)
                    except Exception as e:
                        self.logger.error(
                            f"❌ Помилка синхронізації чату {chat_id_str}: {e}"
                        )

                self.logger.info("✅ Планова нічна синхронізація завершена")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"⚠️ Помилка у фоновому завданні: {e}")
                await asyncio.sleep(3600)  # Чекаємо годину при помилці

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
