"""
Userbot collector - збір даних через Telethon (SRP)
"""
import logging
import asyncio
from telethon import TelegramClient, events as t_events
from core.database import ChatRepository
from utils.helpers import get_clean_chat_id


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
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.chat_repo = chat_repo
        self.logger = logging.getLogger(__name__)
        
        # Реєструємо обробники
        self._register_handlers()
    
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
            # Оновлюємо activity
            self.chat_repo.save_user(chat_id, user_id, name)
    
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
                # При синхронізації НІКОЛИ не знімаємо анрег
                self.chat_repo.save_user(clean_chat_id, user_id, name, update_unreg=False)
                count += 1
        
        return count
    
    async def start(self):
        """
        Запускає userbot (Headless режим)
        """
        try:
            if not self.client.is_connected():
                await self.client.connect()
            
            if not await self.client.is_user_authorized():
                self.logger.warning("Userbot НЕ авторизований!")
                return False
                
            self.logger.info("Userbot успішно підключено та авторизовано")
            return True
        except Exception as e:
            self.logger.error(f"Помилка підключення Userbot: {e}")
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
        self.client = TelegramClient(session_name, api_id, api_hash)
        self._register_handlers()
        self.logger.info(f"Юзербот перемкнуто на сесію: {session_name}")
        return await self.start()
