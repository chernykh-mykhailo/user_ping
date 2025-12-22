"""
Middlewares for Aiogram (v1.6.0)
"""
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message
from utils.helpers import get_clean_chat_id


class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для відстеження активності користувачів.
    Знімає тимчасовий анрег, якщо користувач пише звичайне повідомлення.
    """
    def __init__(self, chat_repo, bot: Bot = None):
        self.chat_repo = chat_repo
        self.bot = bot
        self.logger = logging.getLogger(__name__)
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
                    word_commands = [
                        'анрег', 'рег', 'суперанрег', 'ганрег', 'гсуперанрег', 'грег',
                        'всі', 'хтось', 'стата', 'фулстата', 'стоп', 
                        'unreg', 'reg', 'superunreg', 'gunreg', 'gsuperunreg', 'greg',
                        'all', 'stats', 'fullstats', 'stop', 'help',
                        'адміни', 'admins', 'збір', 'sync', 'преміум', 'premium'
                    ]
                    first_word = text.strip().lower().split()[0] if text else ""
                    
                    if first_word not in word_commands:
                        chat_id = get_clean_chat_id(event.chat.id)
                        user_id = str(event.from_user.id)
                        name = event.from_user.first_name or "Учасник"
                        
                        # Перевіряємо чи був в temp_unreg
                        was_in_unreg = self.chat_repo.unreg.is_in_unreg(chat_id, user_id).get("temp", False)
                        
                        # Оновлюємо ім'я та знімаємо анрег
                        self.chat_repo.save_user(chat_id, user_id, name, update_unreg=True)
                        
                        # Якщо був в анрегі - сповіщаємо (якщо налаштування увімкнено)
                        unreg_notify = self.chat_repo.get_setting(chat_id, "unreg_notify", False)
                        if was_in_unreg and self.bot and unreg_notify:
                            try:
                                # Отримуємо поточну статистику
                                stats = self.chat_repo.get_stats(chat_id)
                                remaining = stats['temp_unreg']
                                
                                msg = f"✅ <b>{name}</b> повернувся до активних!\n"
                                if remaining > 0:
                                    msg += f"📊 В анрегі залишилось: {remaining} осіб"
                                else:
                                    msg += "📊 Всі в активних!"
                                
                                sent = await self.bot.send_message(
                                    event.chat.id, 
                                    msg, 
                                    parse_mode="HTML"
                                )
                                
                                # Автовидалення через 10 секунд
                                import asyncio
                                asyncio.create_task(self._delete_after(sent, 10))
                            except Exception as e:
                                self.logger.debug(f"Couldn't send unreg return notification: {e}")
        
        return await handler(event, data)
    
    async def _delete_after(self, message: Message, delay: int):
        """Видаляє повідомлення після затримки"""
        import asyncio
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass
