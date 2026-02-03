"""
Middlewares for Aiogram (v1.6.0)
"""

import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message
from utils.helpers import get_clean_chat_id, get_user_name


class ActivityMiddleware(BaseMiddleware):
    """
    Middleware для відстеження активності користувачів.
    Знімає тимчасовий анрег, якщо користувач пише звичайне повідомлення.
    """

    def __init__(self, chat_repo, bot: Bot = None):
        self.chat_repo = chat_repo
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        # (chat_id, mentioned_user_id) -> timestamp
        self._warning_cooldowns = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Працюємо тільки з повідомленнями
        if (
            isinstance(event, Message)
            and event.chat
            and event.chat.type in ["group", "supergroup"]
        ):
            if event.from_user and not event.from_user.is_bot:
                text = event.text or event.caption or ""

                chat_id = get_clean_chat_id(event.chat.id)

                # v2.6.2: Обробка нових учасників через сервісні повідомлення (Backup)
                if event.new_chat_members:
                    for member in event.new_chat_members:
                        if not member.is_bot:
                            member_name = get_user_name(
                                first_name=member.first_name,
                                last_name=member.last_name,
                                username=member.username,
                                user_id=member.id,
                            )
                            self.chat_repo.save_user(
                                chat_id,
                                str(member.id),
                                member_name,
                                update_unreg=False,
                                username=member.username,
                            )
                            self.logger.info(
                                f"Service Join: Користувач {member.id} доданий через сервісне повідомлення"
                            )

                # Визначаємо чи це команда (щоб не знімати анрег помилково)
                word_commands = [
                    "анрег",
                    "рег",
                    "суперанрег",
                    "ганрег",
                    "гсуперанрег",
                    "грег",
                    "всі",
                    "хтось",
                    "стата",
                    "фулстата",
                    "стоп",
                    "unreg",
                    "reg",
                    "superunreg",
                    "gunreg",
                    "gsuperunreg",
                    "greg",
                    "all",
                    "stats",
                    "fullstats",
                    "stop",
                    "help",
                    "адміни",
                    "admins",
                    "збір",
                    "sync",
                    "преміум",
                    "premium",
                ]
                first_word = text.strip().lower().split()[0] if text else ""
                is_command = text.startswith(("/", "!")) or first_word in word_commands

                chat_id = get_clean_chat_id(event.chat.id)
                user_id = str(event.from_user.id)
                name = get_user_name(
                    first_name=event.from_user.first_name,
                    last_name=event.from_user.last_name,
                    username=event.from_user.username,
                    user_id=event.from_user.id,
                )

                # Перевіряємо чи був в temp_unreg
                was_in_unreg = self.chat_repo.unreg.is_in_unreg(chat_id, user_id).get(
                    "temp", False
                )

                # Оновлюємо ім'я та знімаємо анрег ТІЛЬКИ якщо це не команда.
                # v2.8.4: Додано обробку стікерів та медіа як активності.
                # Якщо це не команда (текст, стікер, фото тощо) - знімаємо тимчасовий анрег.
                # Але last_seen оновлюється ЗАВЖДИ (навіть для команд), щоб уникнути видалення учасника при синхронізації.
                should_update_unreg = not is_command

                self.chat_repo.save_user(
                    chat_id,
                    user_id,
                    name,
                    update_unreg=should_update_unreg,
                    username=event.from_user.username,
                )

                # Якщо був в анрегі і це не команда - сповіщаємо (якщо налаштування увімкнено)
                unreg_notify = self.chat_repo.get_setting(
                    chat_id, "unreg_notify", False
                )
                if was_in_unreg and should_update_unreg and self.bot and unreg_notify:
                    try:
                        # Отримуємо поточну статистику
                        stats = self.chat_repo.get_stats(chat_id)
                        remaining = stats["temp_unreg"]

                        msg = f"✅ <b>{name}</b> повернувся до активних!\n"
                        if remaining > 0:
                            msg += f"📊 В анрегі залишилось: {remaining} осіб"
                        else:
                            msg += "📊 Всі в активних!"

                        sent = await self.bot.send_message(
                            event.chat.id, msg, parse_mode="HTML"
                        )

                        # Автовидалення через 10 секунд
                        import asyncio

                        asyncio.create_task(self._delete_after(sent, 10))
                    except Exception as e:
                        self.logger.debug(
                            f"Couldn't send unreg return notification: {e}"
                        )

                # v2.4.0: Mention Protection (Захист від тегів)
                if event.entities:
                    import time

                    current_time = time.time()

                    mentioned_ids = set()
                    for entity in event.entities:
                        if entity.type == "text_mention" and entity.user:
                            mentioned_ids.add(str(entity.user.id))

                    if mentioned_ids:
                        chat_id = get_clean_chat_id(event.chat.id)
                        # Отримуємо списки
                        chat_data = self.chat_repo.get_chat_data(chat_id)
                        local_puper = set(
                            map(str, chat_data.get("super_puper_unreg", []))
                        )

                        for whom_id in mentioned_ids:
                            # Mention Protection ТІЛЬКИ для Super Puper Unreg (v2.7.0)
                            is_protected = whom_id in local_puper

                            if is_protected:
                                # Перевірка кулдауну (1 хв)
                                key = (chat_id, whom_id)
                                last_warn = self._warning_cooldowns.get(key, 0)

                                if current_time - last_warn > 60:
                                    user_info = chat_data.get("users", {}).get(whom_id)
                                    whom_name = (
                                        user_info.get("name", "Користувач")
                                        if isinstance(user_info, dict)
                                        else "Користувач"
                                    )

                                    # Logic v2.4.1: Delete & Repost mechanism
                                    try:
                                        # 1. Спроба видалити повідомлення порушника
                                        try:
                                            await event.delete()
                                            deleted = True
                                        except Exception:
                                            deleted = False

                                        # 2. Формування повідомлення-заміни
                                        sender = event.from_user
                                        sender_name = sender.first_name
                                        if sender.last_name:
                                            sender_name += f" {sender.last_name}"

                                        # Посилання на користувача (безпечне)
                                        if sender.username:
                                            sender_link = f"@{sender.username}"
                                        else:
                                            sender_link = f"<a href='tg://user?id={sender.id}'>{sender_name}</a>"

                                        # Визначаємо контент
                                        is_media = False
                                        content_text = ""

                                        if event.content_type == "text":
                                            content_text = event.text or ""
                                        else:
                                            is_media = True
                                            content_text = f"<i>[{event.content_type.capitalize()} Message]</i>"
                                            if event.caption:
                                                content_text += f"\n{event.caption}"

                                        # 3. Відправка повідомлення
                                        if deleted:
                                            # Якщо вдалося видалити - постимо "від імені" користувача + варн
                                            repost_text = (
                                                f"👤 <b>{sender_link}</b>:\n"
                                                f"{content_text}\n\n"
                                                f"⚠️ <b>{whom_name}</b> вийшов з закликів, не турбуйте"
                                            )
                                            warn_msg = await self.bot.send_message(
                                                event.chat.id,
                                                repost_text,
                                                parse_mode="HTML",
                                            )
                                            # Видаляємо це повідомлення через 30 сек (щоб не засмічувати чат навічно)
                                            # або залишаємо? Користувач казав "повідомлення зберігається, але без пінгу"
                                            # Тому НЕ видаляємо, або ставимо довгий таймер.
                                            # User request: "повідомлення зберігається" -> so NO auto-delete for the repost itself.
                                            # Але варн частина є... Хм.
                                            # "Мишко вийшов з закликів, не турбуйте" - це частина повідомлення.
                                            # Лишаємо як є.
                                        else:
                                            # Fallback: якщо не вдалося видалити (нема прав), просто кидаємо варн реплаєм + тег порушника
                                            await self.bot.send_message(
                                                event.chat.id,
                                                f"⚠️ {sender_link}, <b>{whom_name}</b> вийшов з закликів, не турбуйте!",
                                                parse_mode="HTML",
                                                reply_to_message_id=event.message_id,
                                            )

                                        self._warning_cooldowns[key] = current_time

                                    except Exception as e:
                                        self.logger.error(
                                            f"Error in Mention Protection logic: {e}"
                                        )

        return await handler(event, data)

    async def _delete_after(self, message: Message, delay: int):
        """Видаляє повідомлення після затримки"""
        import asyncio

        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass
