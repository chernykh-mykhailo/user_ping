"""
Ping handlers - команди пінгування (SRP)
"""
import logging
import asyncio
import random
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from config import CHUNK_SIZE, PING_DELAY, EMOJIS


class PingHandler(BaseHandler):
    """
    Обробляє команди пінгування
    Single Responsibility: тільки пінги
    """
    
    def __init__(self, chat_repo, premium_repo, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери пінгування"""
        self.router.message(Command("all"))(self.cmd_all)
        self.router.message(F.text.regexp(r'^!?кнагє', flags=0))(self.cmd_all)
        
        self.router.message(Command("emoji"))(self.cmd_emoji)
        self.router.message(F.text.regexp(r'^!?емодзі', flags=0))(self.cmd_emoji)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            return member.status in ['creator', 'administrator']
        except:
            return True
    
    async def _send_pings(
        self,
        chat_id: int,
        users: dict,
        call_text: str,
        use_emoji: bool = False
    ):
        """
        Відправляє пінги групами
        
        Args:
            chat_id: ID чату
            users: Словник {user_id: name}
            call_text: Текст повідомлення
            use_emoji: Використовувати емодзі замість імен
        """
        user_ids = list(users.keys())
        
        for i in range(0, len(user_ids), CHUNK_SIZE):
            chunk = user_ids[i:i + CHUNK_SIZE]
            mentions = []
            
            for uid in chunk:
                if use_emoji:
                    label = random.choice(EMOJIS)
                else:
                    label = users[uid]
                
                mentions.append(f'<a href="tg://user?id={uid}">{label}</a>')
            
            try:
                await self.bot.send_message(
                    chat_id,
                    f"<b>{call_text}</b>\n\n" + " ".join(mentions),
                    parse_mode="HTML"
                )
                await asyncio.sleep(PING_DELAY)
            except:
                continue
    
    async def cmd_all(self, message: Message):
        """Пінгує всіх користувачів"""
        self.logger.info(f"Отримано команду закликання від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Увага!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        try:
            await message.delete()
        except:
            pass
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
    
    async def cmd_emoji(self, message: Message):
        """Пінгує всіх користувачів емодзі"""
        self.logger.info(f"Отримано команду емодзі від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Увага!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        try:
            await message.delete()
        except:
            pass
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=True)
