"""
Admin handlers - команди для адміністраторів (SRP)
"""
import logging
import asyncio
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from userbot.collector import UserbotCollector
from config import ADMIN_USER_ID, PING_LIMITS


class AdminHandler(BaseHandler):
    """
    Обробляє команди адміністраторів
    Single Responsibility: тільки адмін-команди
    """
    
    def __init__(self, chat_repo, premium_repo, bot: Bot, userbot: UserbotCollector):
        self.bot = bot
        self.userbot = userbot
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери адміністраторів"""
        self.router.message(Command("sync"))(self.cmd_sync)
        self.router.message(F.text.regexp(r'^!?збір', flags=0))(self.cmd_sync)
        
        self.router.message(Command("stats"))(self.cmd_stats)
        self.router.message(F.text.regexp(r'^!?стата', flags=0))(self.cmd_stats)
        
        
        self.router.message(Command("admin_settings"))(self.cmd_admin_settings)
        self.router.message(Command("admin_add_trigger"))(self.cmd_admin_add_trigger)
        self.router.message(Command("admin_del_trigger"))(self.cmd_admin_del_trigger)
        self.router.message(Command("admin_toggle_userbot"))(self.cmd_admin_toggle_userbot)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            is_admin = member.status in ['creator', 'administrator']
            
            if not is_admin:
                self.logger.warning(
                    f"Користувач {user_id} має статус '{member.status}' у чаті {cid}"
                )
            return is_admin
            
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "not enough rights" in error_msg:
                self.logger.debug(f"Бот не є учасником чату {cid}")
                return True
            
            self.logger.error(f"Помилка перевірки прав: {e}")
            return True
    
    async def cmd_sync(self, message: Message):
        """Синхронізує учасників чату"""
        self.logger.info(
            f"Отримано команду синхронізації від {message.from_user.id} "
            f"у чаті {message.chat.id}"
        )
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            self.logger.warning(f"Користувач {message.from_user.id} не є адміном")
            return
        
        status = await message.answer("🔄 Синхронізація учасників...")
        
        try:
            # Перевіряємо чи увімкнено юзербота (v1.6.0)
            # Ми звертаємося до bot.use_userbot (це має бути доступно через атрібут в main.py, 
            # але краще перевірити напряму через репозиторій або передати стан)
            # В нашому випадку простіше перевірити через репозиторій
            is_enabled = self.chat_repo.get_global_setting("use_userbot", True)
            if not is_enabled:
                await status.edit_text("❌ Юзербота вимкнено в глобальних налаштуваннях. Синхронізація неможлива.")
                return

            count = await self.userbot.sync_participants(message.chat.id)
            await status.edit_text(f"✅ База оновлена! Учасників: {count}")
            self.logger.info(f"Синхронізація завершена: {count} осіб")
            
        except Exception as e:
            self.logger.error(f"Sync error: {e}")
            await status.edit_text("❌ Помилка: Не вдалося отримати список.")
        
        await self.auto_cleanup(message, status)
    
    async def cmd_stats(self, message: Message):
        """Показує статистику чату"""
        self.logger.info(f"Отримано команду статистики від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        stats = self.chat_repo.get_stats(chat_id)
        
        stats_text = (
            f"📈 <b>Статистика чату:</b>\n\n"
            f"👥 Всього в базі: {stats['total']}\n"
            f"✅ Активних (отримують пінги): {stats['active']}\n"
            f"🔕 Тимчасово вимкнено: {stats['temp_unreg']}\n"
            f"🚫 Постійно вимкнено: {stats['super_unreg']}"
        )
        
        sent = await message.answer(stats_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent)
        self.logger.info(f"Відправлено статистику: {stats['total']} осіб")

    async def cmd_admin_settings(self, message: Message):
        """Встановлює глобальні налаштування (тільки власник)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 3:
            current_delay = self.chat_repo.get_global_setting("ping_delay", PING_LIMITS["default_delay"])
            use_ub = self.chat_repo.get_global_setting("use_userbot", True)
            
            await message.answer(
                f"⚙️ <b>Global Settings</b>\n\n"
                f"• Delay: {current_delay}s\n"
                f"• Userbot: {'✅ ON' if use_ub else '❌ OFF'}\n\n"
                f"Usage:\n"
                f"<code>/admin_settings set_delay 0.5</code>\n"
                f"<code>/admin_toggle_userbot</code>"
            )
            return
            
        action = args[1]
        value = args[2]
        
        if action == "set_delay":
            try:
                delay = float(value)
                if delay < PING_LIMITS["min_delay"]: delay = PING_LIMITS["min_delay"]
                if delay > PING_LIMITS["max_delay"]: delay = PING_LIMITS["max_delay"]
                
                self.chat_repo.set_global_setting("ping_delay", delay)
                await message.answer(f"✅ Global Delay set to {delay}s")
            except ValueError:
                await message.answer("❌ Invalid number")

    async def cmd_admin_add_trigger(self, message: Message):
        """Додає глобальний тригер (Owner only)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_add_trigger [word] [text|emoji]")
            return
            
        trigger = args[1].lower()
        type_ = args[2].lower() if len(args) > 2 else "text"
        if type_ not in ["text", "emoji"]:
            type_ = "text"
            
        self.chat_repo.add_global_ping_trigger(trigger, type_)
        await message.answer(f"✅ Global Trigger '{trigger}' added as {type_}")

    async def cmd_admin_del_trigger(self, message: Message):
        """Видаляє глобальний тригер (Owner only)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_del_trigger [word]")
            return
            
        trigger = args[1].lower()
        if self.chat_repo.remove_global_ping_trigger(trigger):
            await message.answer(f"✅ Global Trigger '{trigger}' removed")
        else:
            await message.answer(f"❌ Global Trigger '{trigger}' not found")

    async def cmd_admin_toggle_userbot(self, message: Message):
        """Перемикає використання юзербота (Global)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        current = self.chat_repo.get_global_setting("use_userbot", True)
        new_state = not current
        
        self.chat_repo.set_global_setting("use_userbot", new_state)
        
        try:
            if new_state:
                await self.userbot.start()
                status = "УВІМКНЕНО ✅ (З'єднання встановлено)"
            else:
                await self.userbot.stop()
                status = "ВИМКНЕНО ❌ (Сесію закрито, акаунт вільний)"
        except Exception as e:
            self.logger.error(f"Error toggling userbot: {e}")
            status = f"{'УВІМКНЕНО' if new_state else 'ВИМКНЕНО'} (Але виникла помилка зв'язку: {e})"
        
        await message.answer(
            f"🤖 <b>Використання юзербота:</b> {status}\n\n"
            f"Тепер ви можете використовувати цей акаунт в іншому місці, якщо він вимкнений.",
            parse_mode="HTML"
        )
