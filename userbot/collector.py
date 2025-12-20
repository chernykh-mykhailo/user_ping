"""
Userbot collector - збір даних через Telethon (SRP)
"""
import logging
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
        self.client.on(t_events.NewMessage())(self._on_message)
        self.client.on(t_events.ChatAction())(self._on_chat_action)
    
    async def _on_message(self, event):
        """Обробляє нові повідомлення для збору даних"""
        # Перевіряємо що це група, є sender, і це не бот і не канал
        if event.is_group and event.sender and not getattr(event.sender, 'bot', False):
            # Перевіряємо що sender це User, а не Channel
            if not hasattr(event.sender, 'first_name'):
                return
            
            chat_id = get_clean_chat_id(event.chat_id)
            user_id = str(event.sender_id)
            name = event.sender.first_name or "Учасник"
            
            self.chat_repo.save_user(chat_id, user_id, name)
    
    async def _on_chat_action(self, event):
        """Відстежує вихід або бан користувачів"""
        if event.user_left or event.user_kicked:
            if event.user_id:
                chat_id = get_clean_chat_id(event.chat_id)
                user_id = str(event.user_id)
                
                self.chat_repo.remove_user(chat_id, user_id)
                self.logger.info(f"Видалено користувача {user_id} з чату {chat_id}")
    
    async def sync_participants(self, chat_id: int) -> int:
        """
        Синхронізує всіх учасників чату
        
        Args:
            chat_id: ID чату
            
        Returns:
            Кількість зібраних користувачів
        """
        clean_chat_id = get_clean_chat_id(chat_id)
        count = 0
        
        async for user in self.client.iter_participants(chat_id):
            if not user.bot:
                user_id = str(user.id)
                name = user.first_name or "Учасник"
                self.chat_repo.save_user(clean_chat_id, user_id, name)
                count += 1
        
        return count
    
    async def start(self):
        """Запускає userbot"""
        await self.client.start()
        self.logger.info("Userbot запущено")
    
    async def stop(self):
        """Зупиняє userbot"""
        await self.client.disconnect()
        self.logger.info("Userbot зупинено")
