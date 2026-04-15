"""
Userbot collector - збір даних через Telethon (SRP)
v2.6.0: Використовує StringSession замість файлових сесій (fix readonly database)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events as t_events, types
from telethon.sessions import StringSession
from core import ChatRepository
from utils.helpers import get_clean_chat_id, get_user_name
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
        chat_repo: ChatRepository,
        session_storage: str = "data/sessions.json",
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.chat_repo = chat_repo
        self.logger = logging.getLogger(__name__)

        # v2.6.0: StringSession Manager (Isolated storage)
        self.account_name = os.path.basename(session_name)
        self.session_manager = StringSessionManager(session_storage)

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
                name = get_user_name(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    user_id=user.id,
                )
                self.chat_repo.save_user(
                    chat_id, str(user.id), name, username=user.username
                )

    async def _on_new_message(self, event):
        """Відстежує повідомлення для оновлення активності"""
        if event.is_private:
            return

        chat_id = get_clean_chat_id(event.chat_id)
        sender = await event.get_sender()

        if sender and hasattr(sender, "id") and not getattr(sender, "bot", False):
            user_id = str(sender.id)
            name = get_user_name(
                first_name=getattr(sender, "first_name", None),
                last_name=getattr(sender, "last_name", None),
                username=getattr(sender, "username", None),
                user_id=sender.id,
            )

            # v2.2.0: Ignore commands to prevent race conditions with unreg
            text = event.text or ""
            if text.startswith(("/", "!")):
                # For commands, we only update the name/last_seen but DON'T remove unreg
                self.chat_repo.save_user(
                    chat_id,
                    user_id,
                    name,
                    source="message",
                    update_unreg=False,
                    username=getattr(sender, "username", None),
                )
            elif not text.strip():
                # v2.8.0: If message has no text (Sticker, GIF, etc) - update activity BUT KEEP UNREG
                # This matches user expectation that "only writing text" breaks temp unreg
                self.chat_repo.save_user(
                    chat_id,
                    user_id,
                    name,
                    source="message",
                    update_unreg=False,
                    username=getattr(sender, "username", None),
                )
            else:
                # v2.6.3: Check word commands without prefix (анрег, рег, всі і т.д.)
                word_commands = [
                    "анрег",
                    "рег",
                    "суперанрег",
                    "суперпуперанрег",
                    "спа",
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
                    "superpuperunreg",
                    "spa",
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
                first_word = text.strip().lower().split()[0] if text.strip() else ""

                if first_word in word_commands:
                    # Word command - don't remove unreg
                    self.chat_repo.save_user(
                        chat_id,
                        user_id,
                        name,
                        source="message",
                        update_unreg=False,
                        username=getattr(sender, "username", None),
                    )
                else:
                    # Normal message - update and clear temp unreg
                    self.chat_repo.save_user(
                        chat_id,
                        user_id,
                        name,
                        source="message",
                        update_unreg=True,
                        username=getattr(sender, "username", None),
                    )

    async def sync_participants(self, chat_id: int) -> int:
        """
        Синхронізує всіх учасників чату та видаляє тих, хто вийшов
        """
        if not self.client.is_connected() or not await self.client.is_user_authorized():
            raise Exception("Userbot not authorized")

        clean_chat_id = get_clean_chat_id(chat_id)

        # Отримуємо список поточних учасників з БД
        db_users = set(self.chat_repo.get_all_user_ids(clean_chat_id))
        current_members = set()
        count = 0
        regular_found = 0
        me = await self.client.get_me()

        async for user in self.client.iter_participants(chat_id):
            # v2.10.22: Перевірка зупинки
            if self.chat_repo.get_stop_flag(clean_chat_id):
                self.logger.info(
                    f"Синхронізацію в чаті {clean_chat_id} зупинено користувачем"
                )
                break

            if not user.bot:
                user_id = str(user.id)
                current_members.add(user_id)

                # Перевірка ролі (v2.10.21)
                p = getattr(user, "participant", None)
                is_admin = isinstance(
                    p, (types.ChannelParticipantAdmin, types.ChannelParticipantCreator)
                )

                if user.id != me.id and not is_admin:
                    regular_found += 1

                name = get_user_name(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    user_id=user.id,
                )

                # Витягуємо статус із профілю (v1.8.5)
                profile_time = self._parse_user_status(user)

                # При синхронізації НІКОЛИ не знімаємо анрег і вказуємо source="profile"
                self.chat_repo.save_user(
                    clean_chat_id,
                    user_id,
                    name,
                    update_unreg=False,
                    source="profile",
                    profile_time=profile_time,
                    username=user.username,
                )
                count += 1

        # v2.10.21: Вдосконалений захист від Hide Members
        if len(db_users) > 5:
            # Сценарій А: Ми бачимо ЛИШЕ адмінів та себе (а в базі було більше людей)
            if regular_found == 0 and len(db_users) > len(current_members):
                self.logger.warning(
                    f"⚠️ PROTECT: Юзербот бачить лише себе та адмінів ({len(current_members)})! "
                    f"В базі {len(db_users)} учасників. Ймовірно увімкнено 'Hide Members'. Очищення бази пропущено."
                )
                return count

            # Сценарій Б: Різке падіння (менше 15% від попередньої кількості)
            retention_rate = len(current_members) / len(db_users)
            if retention_rate < 0.15:
                self.logger.warning(
                    f"⚠️ PROTECT: Юзербот бачить лише {len(current_members)} учасників з {len(db_users)}! "
                    f"Занадто великий перепад. Очищення бази пропущено для безпеки."
                )
                return count

        # Видаляємо тих, кого немає в поточному списку учасників
        stale_users = db_users - current_members

        # v2.8.3: Protection against "Hide Members" (fix user disappearance)
        # We don't remove user if they were seen writing in the last 30 days
        now_dt = datetime.now()
        active_threshold = now_dt - timedelta(days=30)

        # Read user data directly to check last_seen
        chat_data = self.chat_repo.get_chat_data(clean_chat_id)
        users_data = chat_data.get("users", {})

        for uid in stale_users:
            user_record = users_data.get(uid, {})
            if isinstance(user_record, dict):
                ls_str = user_record.get("last_seen", "2000-01-01T00:00:00")
                try:
                    ls_dt = datetime.fromisoformat(
                        ls_str.replace("+00:00", "").replace("Z", "")
                    )
                    if ls_dt > active_threshold:
                        # User is active but missing from member list (likely hidden)
                        continue
                except (ValueError, TypeError):
                    pass

            # v2.10.21: Останній шанс — якщо ім'я вже санітизоване і юзер був активний нещодавно, не чіпаємо
            self.chat_repo.remove_user(clean_chat_id, uid)
            self.logger.info(
                f"Cleanup: Видалено неіснуючого учасника {uid} з {clean_chat_id}"
            )

        return count

    async def get_online_users(self, chat_id: int) -> dict:
        """
        Швидке отримання онлайн-користувачів через UserBot (v2.10.23)
        Отримує тих, хто реально онлайн зараз + оновлює базу
        """
        if not self.client or not self.client.is_connected():
            return {}

        results = {}
        clean_chat_id = get_clean_chat_id(chat_id)
        
        try:
            # v2.10.23: Використовуємо filter для швидкості, якщо це можливо
            # ChannelParticipantsOnline повертає тих, хто Online
            async for user in self.client.iter_participants(chat_id, filter=types.ChannelParticipantsOnline):
                if user.bot:
                    continue
                    
                user_id = str(user.id)
                name = get_user_name(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    user_id=user.id,
                )
                results[user_id] = name
                
                # Попутно оновлюємо profile_seen в базі
                self.chat_repo.save_user(
                    clean_chat_id,
                    user_id,
                    name,
                    update_unreg=False,
                    source="profile",
                    profile_time=datetime.now().isoformat(),
                    username=user.username,
                )
                
            # Якщо нікого не знайшли через фільтр (або це звичайна група), 
            # спробуємо просто пробігтися по учасниках, але лімітовано
            if not results:
                async for user in self.client.iter_participants(chat_id, limit=200):
                    if user.bot:
                        continue
                        
                    status = user.status
                    if isinstance(status, (types.UserStatusOnline, types.UserStatusRecently)):
                        user_id = str(user.id)
                        name = get_user_name(
                            first_name=user.first_name,
                            last_name=user.last_name,
                            username=user.username,
                            user_id=user.id,
                        )
                        results[user_id] = name
                        
                        self.chat_repo.save_user(
                            clean_chat_id,
                            user_id,
                            name,
                            update_unreg=False,
                            source="profile",
                            profile_time=datetime.now().isoformat(),
                            username=user.username,
                        )
        except Exception as e:
            self.logger.error(f"Помилка при отриманні онлайн юзерів: {e}")
            
        return results

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

            # v2.6.4: Використовуємо реалістичні дані пристрою, щоб менше дратувати анти-флуд Телеграма
            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                device_model="Android 13",
                system_version="Pixel 7 Pro",
                app_version="10.3.2",
            )
            self._register_handlers()

            await self.client.connect()

            if not await self.client.is_user_authorized():
                self.logger.warning(f"⚠️ Акаунт {self.account_name} не авторизований!")
                return False

            # Зберігаємо оновлену сесію після успішного підключення
            self.session_manager.save_session(self.account_name, self.client.session)

            # v2.8.2: Кешуємо діалоги, щоб Telethon знав Entity ID (fix "Could not find input entity")
            await self.client.get_dialogs()

            self.logger.info(
                f"✅ Userbot успішно підключено (Акаунт: {self.account_name})"
            )
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
