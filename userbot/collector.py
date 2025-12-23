"""
Userbot collector - збір даних через Telethon (SRP)
"""
import logging
import asyncio
from datetime import datetime
from telethon import TelegramClient, events as t_events, types
from core.database import ChatRepository
from utils.helpers import get_clean_chat_id
import os
from .session_manager import SmartSessionManager


class UserbotCollector:
    """
    Відповідає за збір даних користувачів через userbot
    Single Responsibility: тільки збір даних
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        chat_repo: ChatRepository
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.chat_repo = chat_repo
        self.logger = logging.getLogger(__name__)
        
        # v2.4.0: Smart Session Management
        base_name = os.path.basename(session_name)
        sessions_dir = os.path.dirname(session_name) or "sessions"
        self.session_manager = SmartSessionManager(sessions_dir, base_name)
        
        # Тимчасовий клієнт (буде перевизначено в start)
        self.client = None
        
        # Реєструємо обробники будуть викликані після створення клієнта
    
    def _register_handlers(self):
        """Реєструє обробники подій"""
        self.client.on(t_events.ChatAction())(self._on_chat_action)
        self.client.on(t_events.NewMessage())(self._on_new_message)
    
    async def _on_chat_action(self, event):
        """Відстежує вихід або бан користувачів"""
        if event.user_left or event.user_kicked:
            if event.user_id:
                chat_id = get_clean_chat_id(event.chat_id)
                user_id = str(event.user_id)
                self.chat_repo.remove_user(chat_id, user_id)
                self.logger.info(f"Видалено користувача {user_id} з чату {chat_id}")
        elif event.user_joined or event.user_added:
            # При вході нового юзера - одразу ловимо його активність
            user = await event.get_user()
            if user and not user.bot:
                chat_id = get_clean_chat_id(event.chat_id)
                self.chat_repo.save_user(chat_id, str(user.id), user.first_name or "Учасник")

    async def _on_new_message(self, event):
        """Відстежує повідомлення для оновлення активності"""
        if event.is_private:
            return
            
        chat_id = get_clean_chat_id(event.chat_id)
        sender = await event.get_sender()
        
        if sender and hasattr(sender, 'id') and not getattr(sender, 'bot', False):
            user_id = str(sender.id)
            name = getattr(sender, 'first_name', "Учасник") or "Учасник"
            
            # v2.2.0: Ignore commands to prevent race conditions with unreg
            text = event.text or ""
            if text.startswith(('/', '!')):
                # For commands, we only update the name/last_seen but DON'T remove unreg
                self.chat_repo.save_user(chat_id, user_id, name, source="message", update_unreg=False)
            else:
                # For normal messages, update and clear temp unreg
                self.chat_repo.save_user(chat_id, user_id, name, source="message", update_unreg=True)
    
    async def sync_participants(self, chat_id: int) -> int:
        """
        Синхронізує всіх учасників чату
        """
        if not self.client.is_connected() or not await self.client.is_user_authorized():
            raise Exception("Userbot not authorized")

        clean_chat_id = get_clean_chat_id(chat_id)
        count = 0
        
        async for user in self.client.iter_participants(chat_id):
            if not user.bot:
                user_id = str(user.id)
                name = user.first_name or "Учасник"
                
                # Витягуємо статус із профілю (v1.8.5)
                profile_time = self._parse_user_status(user)
                
                # При синхронізації НІКОЛИ не знімаємо анрег і вказуємо source="profile"
                self.chat_repo.save_user(
                    clean_chat_id, 
                    user_id, 
                    name, 
                    update_unreg=False, 
                    source="profile",
                    profile_time=profile_time
                )
                count += 1
        
        return count

    def _parse_user_status(self, user) -> str:
        """Перетворює статус Telethon у ISO рядок часу (v1.8.6: з офсетами)"""
        status = user.status
        if not status:
            return None
            
        now = datetime.now()
        if isinstance(status, types.UserStatusOnline):
            return now.isoformat()
        elif isinstance(status, types.UserStatusOffline):
            return status.was_online.isoformat()
        elif isinstance(status, types.UserStatusRecently):
            # Був нещодавно (до 3 днів) -> ставимо -2 години для сортування нижче онлайн юзерів
            from datetime import timedelta
            return (now - timedelta(hours=2)).isoformat()
        elif isinstance(status, types.UserStatusLastWeek):
            # До 7 днів -> ставимо -4 дні
            from datetime import timedelta
            return (now - timedelta(days=4)).isoformat()
        elif isinstance(status, types.UserStatusLastMonth):
            # До місяця -> ставимо -15 днів
            from datetime import timedelta
            return (now - timedelta(days=15)).isoformat()
        
        return None
    
    async def start(self):
        """
        Запускає userbot з підтримкою автоматичного вибору сесії
        """
        try:
            # Отримуємо найкращу існуючу сесію
            current_session = self.session_manager.get_best_session()
            self.logger.info(f"🔄 Спроба запуску з сесією: {current_session}")
            
            self.client = TelegramClient(current_session, self.api_id, self.api_hash)
            self._register_handlers()
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.warning(f"⚠️ Сесія {current_session} не авторизована!")
                # Якщо це була існуюча сесія, але вона не ок - можливо вона бита
                if os.path.exists(f"{current_session}.session"):
                    self.session_manager.mark_broken(current_session)
                return False
                
            self.logger.info(f"✅ Userbot успішно підключено (Сесія: {current_session})")
            # Чистимо старе сміття
            self.session_manager.cleanup_old_broken()
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ Помилка старту Userbot: {e}")
            
            # Якщо сесія бита (наприклад, IP changed)
            if "authorization" in error_msg.lower() or "key" in error_msg.lower():
                 if self.client and hasattr(self.client, 'session'):
                     self.session_manager.mark_broken(self.client.session.filename)
            
            return False

    # === Login Methods (v1.7.0) ===

    async def request_phone_code(self, phone: str):
        """Запитує код підтвердження для входу"""
        try:
            if not self.client.is_connected():
                await self.client.connect()
            return await self.client.send_code_request(phone)
        except Exception as e:
            if self.client.is_connected():
                await self.client.disconnect()
            raise e

    async def sign_in_with_code(self, phone: str, code: str, phone_code_hash: str):
        """Вхід за кодом"""
        try:
            await self.client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            return {"status": "success"}
        except Exception as e:
            if "Password" in str(e) or "SessionPasswordNeededError" in str(type(e)):
                return {"status": "password_needed"}
            raise e

    async def sign_in_with_password(self, password: str):
        """Вхід за паролем (2FA)"""
        await self.client.sign_in(password=password)
        return {"status": "success"}
    
    async def stop(self):
        """Зупиняє userbot"""
        try:
            if self.client and self.client.is_connected():
                # Даємо час фоновим задачам завершитись
                await asyncio.sleep(1)
                await self.client.disconnect()
                self.logger.info("Userbot зупинено успішно")
        except Exception as e:
            self.logger.error(f"Помилка при зупинці Userbot: {e}")

    async def switch_account(self, api_id: int, api_hash: str, session_name: str):
        """Перемикає акаунт юзербота (v1.7.0)"""
        await self.stop()
        
        # Оновлюємо облікові дані та менеджер сесій
        self.api_id = api_id
        self.api_hash = api_hash
        
        base_name = os.path.basename(session_name)
        sessions_dir = os.path.dirname(session_name) or "sessions"
        self.session_manager = SmartSessionManager(sessions_dir, base_name)
        
        self.logger.info(f"🔄 Перемикання на акаунт з базовою назвою: {base_name}")
        
        # start() сам створить новий клієнт і знайде найкращу сесію
        return await self.start()
