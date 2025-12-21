"""
Middlewares for Aiogram (v1.6.0)
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from utils.helpers import get_clean_chat_id


class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для відстеження активності користувачів.
    Знімає тимчасовий анрег, якщо користувач пише звичайне повідомлення.
    """
    def __init__(self, chat_repo):
        self.chat_repo = chat_repo
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Працюємо тільки з повідомленнями
        if isinstance(event, Message) and event.chat and event.chat.type in ["group", "supergroup"]:
            if event.from_user and not event.from_user.is_bot:
                text = event.text or event.caption or ""
                
                # Якщо це НЕ команда і НЕ тригер (вони починаються з / або !)
                if text and not text.startswith(('/', '!')):
                    # Список слів-команд без префіксів (додатковий захист)
                    word_commands = ['анрег', 'рег', 'всі', 'хтось', 'стата', 'стоп']
                    first_word = text.strip().lower().split()[0] if text else ""
                    
                    if first_word not in word_commands:
                        chat_id = get_clean_chat_id(event.chat.id)
                        user_id = str(event.from_user.id)
                        name = event.from_user.first_name or "Учасник"
                        
                        # Оновлюємо ім'я та знімаємо анрег
                        self.chat_repo.save_user(chat_id, user_id, name, update_unreg=True)
        
        return await handler(event, data)
