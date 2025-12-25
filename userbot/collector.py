"""
Userbot collector - збір даних через Telethon (SRP)
v2.6.0: Використовує StringSession замість файлових сесій (fix readonly database)
"""
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events as t_events, types
from telethon.sessions import StringSession
from core.database import ChatRepository
from utils.helpers import get_clean_chat_id
import os
from .string_session_manager import StringSessionManager


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
        
        # v2.6.0: StringSession Manager (NO MORE SQLITE FILES!)
        self.account_name = os.path.basename(session_name)
        self.session_manager = StringSessionManager()
        
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
        Запускає userbot з StringSession (без SQLite файлів)
        """
        try:
            self.logger.info(f"🔄 Спроба запуску акаунта: {self.account_name}")
            
            # Отримуємо StringSession з JSON
            session = self.session_manager.get_session(self.account_name)
            
            self.client = TelegramClient(session, self.api_id, self.api_hash)
            self._register_handlers()
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.warning(f"⚠️ Акаунт {self.account_name} не авторизований!")
                return False
                
            # Зберігаємо оновлену сесію після успішного підключення
            self.session_manager.save_session(self.account_name, self.client.session)
            
            self.logger.info(f"✅ Userbot успішно підключено (Акаунт: {self.account_name})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Помилка старту Userbot: {e}")
            return False

    # === Login Methods (v2.6.0 - StringSession) ===

    async def request_phone_code(self, phone: str):
        """Запитує код підтвердження для входу"""
        try:
            # Створюємо нову порожню StringSession для логіну
            session = StringSession()
            self.client = TelegramClient(session, self.api_id, self.api_hash)
            
            if not self.client.is_connected():
                await self.client.connect()
            return await self.client.send_code_request(phone)
        except Exception as e:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            raise e

    async def sign_in_with_code(self, phone: str, code: str, phone_code_hash: str):
        """Вхід за кодом"""
        try:
            await self.client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            
            # Зберігаємо сесію після успішного входу
            self.session_manager.save_session(self.account_name, self.client.session)
            self.logger.info(f"💾 Сесію {self.account_name} збережено після входу")
            
            return {"status": "success"}
        except Exception as e:
            if "Password" in str(e) or "SessionPasswordNeededError" in str(type(e)):
                return {"status": "password_needed"}
            raise e

    async def sign_in_with_password(self, password: str):
        """Вхід за паролем (2FA)"""
        await self.client.sign_in(password=password)
        
        # Зберігаємо сесію після 2FA
        self.session_manager.save_session(self.account_name, self.client.session)
        self.logger.info(f"💾 Сесію {self.account_name} збережено після 2FA")
        
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
        """Перемикає акаунт юзербота (v2.6.0 - StringSession)"""
        await self.stop()
        
        # Оновлюємо облікові дані
        self.api_id = api_id
        self.api_hash = api_hash
        self.account_name = os.path.basename(session_name)
        
        self.logger.info(f"🔄 Перемикання на акаунт: {self.account_name}")
        
        # start() сам завантажить StringSession для цього акаунта
        return await self.start()
