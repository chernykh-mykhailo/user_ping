"""
Ping handlers - команди пінгування (SRP)
"""
import logging
import asyncio
import random
from datetime import datetime, timedelta
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from config import PING_LIMITS, EMOJIS
from aiogram.exceptions import TelegramBadRequest, TelegramServerError


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
        # Базові виклики
        self.router.message(Command("all"))(self.cmd_all)
        self.router.message(F.text.regexp(r'^!?кнагє', flags=0))(self.cmd_all)
        
        self.router.message(Command("emoji"))(self.cmd_emoji)
        self.router.message(F.text.regexp(r'^!?емодзі', flags=0))(self.cmd_emoji)
        
        # Нові команди v1.1.0
        self.router.message(Command("admins"))(self.cmd_admins)
        self.router.message(F.text.regexp(r'^!?адміни', flags=0))(self.cmd_admins)
        
        self.router.message(Command("anybody"))(self.cmd_anybody)
        self.router.message(F.text.regexp(r'^!?хтось', flags=0))(self.cmd_anybody)
        
        self.router.message(Command("active"))(self.cmd_active)
        self.router.message(F.text.regexp(r'^!?активні', flags=0))(self.cmd_active)
        
        self.router.message(Command("active_week"))(self.cmd_active_week)
        self.router.message(F.text.regexp(r'^!?актив_тиждень', flags=0))(self.cmd_active_week)
        
        self.router.message(Command("writers"))(self.cmd_writers)
        self.router.message(F.text.regexp(r'^!?писали', flags=0))(self.cmd_writers)
        
        self.router.message(Command("online"))(self.cmd_online)
        self.router.message(F.text.regexp(r'^!?онлайн', flags=0))(self.cmd_online)
        
        self.router.message(Command("stop", "stopcall"))(self.cmd_stop)
        self.router.message(F.text.regexp(r'^!?стоп', flags=0))(self.cmd_stop)
        
        # Шаблони викликів
        self.router.message(F.text.regexp(r'^!cpatterns$', flags=0))(self.cmd_list_templates)
        self.router.message(F.text.regexp(r'^!addcpattern\s+(\S+)', flags=0))(self.cmd_add_template)
        self.router.message(F.text.regexp(r'^!delcpattern\s+(\S+)', flags=0))(self.cmd_del_template)
        
        # Тригери викликів v1.2.0
        self.router.message(F.text.regexp(r'^!calls$', flags=0))(self.cmd_list_triggers)
        self.router.message(F.text.regexp(r'^!callinfo\s+(\S+)', flags=0))(self.cmd_trigger_info)
        self.router.message(F.text.regexp(r'^!addcall\s+(\S+)', flags=0))(self.cmd_add_trigger)
        self.router.message(F.text.regexp(r'^!delcall\s+(\S+)', flags=0))(self.cmd_del_trigger)
        self.router.message(F.text.regexp(r'^!adduser\s+(\S+)', flags=0))(self.cmd_add_user_to_trigger)
        self.router.message(F.text.regexp(r'^!deluser\s+(\S+)', flags=0))(self.cmd_del_user_from_trigger)
        
        # Self-Service Roles v1.3.0
        # 1. Custom Triggers Management (Specific Commands)
        self.router.message(F.text.startswith("!addtrigger"))(self.cmd_add_custom_trigger)
        self.router.message(F.text.startswith("!addemojitrigger"))(self.cmd_add_custom_emoji_trigger)
        self.router.message(F.text.startswith("!addactivetrigger"))(self.cmd_add_custom_active_trigger)
        self.router.message(F.text.startswith("!addactiveweektrigger"))(self.cmd_add_custom_active_week_trigger)
        self.router.message(F.text.startswith("!addwritertrigger"))(self.cmd_add_custom_writer_trigger)
        self.router.message(F.text.startswith("!addonlinetrigger"))(self.cmd_add_custom_online_trigger)
        self.router.message(F.text.startswith("!deltrigger"))(self.cmd_del_custom_trigger)
        self.router.message(F.text == "!triggers")(self.cmd_list_custom_triggers)
        
        # 2. Specific System Commands
        self.router.message(F.text.regexp(r'^!roles_panel$', flags=0))(self.cmd_roles_panel)
        self.router.message(F.text.regexp(r'^!set_role_emoji\s+(\S+)\s+(.+)', flags=0))(self.cmd_set_role_emoji)
        self.router.callback_query(F.data.startswith("role_"))(self.callback_role_toggle)
        self.router.callback_query(F.data == "stop_ping")(self.callback_stop_ping)
        
        # 3. Dynamic Triggers (Regex !word)
        # This catches !croco (Groups) AND !custom (Aliases)
        self.router.message(F.text.regexp(r'^!(\w+)$', flags=0))(self.cmd_call_trigger)
        
        # 4. Generic Custom Trigger Handler (Catch-all for no-prefix words)
        # Should be LAST
        self.router.message(F.text)(self.handle_custom_triggers)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        # v2.2.0: Глобальний персонал бота (від модератора і вище) має доступ всюди
        if self.chat_repo.is_bot_moderator(user_id):
            return True
            
        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            return member.status in ['creator', 'administrator']
        except:
            return False
    
    async def _get_admin_users(self, chat_id: int) -> dict:
        """Повертає тільки адміністраторів з активних користувачів"""
        clean_chat_id = get_clean_chat_id(chat_id)
        all_users = await self.chat_repo.get_active_users(clean_chat_id)
        
        admin_users = {}
        for uid, name in all_users.items():
            try:
                member = await self.bot.get_chat_member(chat_id, int(uid))
                if member.status in ['creator', 'administrator']:
                    admin_users[uid] = name
            except:
                continue
        
        return admin_users
    
    async def _send_pings(
        self,
        chat_id: int,
        users: dict,
        call_text: str,
        use_emoji: bool = False
    ):
        """
        Відправляє пінги групами з підтримкою зупинки
        
        Args:
            chat_id: ID чату
            users: Словник {user_id: name}
            call_text: Текст повідомлення
            use_emoji: Використовувати емодзі замість імен
        """
        clean_chat_id = get_clean_chat_id(chat_id)
        user_ids = list(users.keys())
        
        # Логування для дебагу
        old_flag = self.chat_repo.get_stop_flag(clean_chat_id)
        self.logger.info(f"[DEBUG] Початок пінгування: stop_flag={old_flag}, users={len(user_ids)}")
        
        # Скидаємо прапорець зупинки перед початком
        self.chat_repo.set_stop_flag(clean_chat_id, False)
        self.logger.info(f"[DEBUG] Stop flag скинуто")
        
        # Отримуємо налаштування чату
        pin_enabled = self.chat_repo.get_setting(clean_chat_id, "pin_enabled", True)
        first_msg_stop = self.chat_repo.get_setting(clean_chat_id, "first_msg_stop", True)
        silent_mode = self.chat_repo.get_setting(clean_chat_id, "silent_mode", False)
        show_count = self.chat_repo.get_setting(clean_chat_id, "show_count", True)
        
        # Динамічні налаштування з урахуванням лімітів
        ping_delay = self.chat_repo.get_setting(clean_chat_id, "ping_delay", PING_LIMITS["default_delay"])
        chunk_size = self.chat_repo.get_setting(clean_chat_id, "chunk_size", PING_LIMITS["default_chunk"])
        
        # Перевірка глобальних налаштувань (Global Override)
        # Якщо в панелі /apanel стоїть затримка, вона стає МІНІМАЛЬНОЮ (для захисту від флуду)
        global_delay = self.chat_repo.get_global_setting("ping_delay")
        if global_delay is not None:
            ping_delay = max(ping_delay, global_delay)
            
        # Hard Limits Safety Check
        if ping_delay < PING_LIMITS["min_delay"]: ping_delay = PING_LIMITS["min_delay"]
        if ping_delay > PING_LIMITS["max_delay"]: ping_delay = PING_LIMITS["max_delay"]
        if chunk_size < PING_LIMITS["min_chunk"]: chunk_size = PING_LIMITS["min_chunk"]
        if chunk_size > PING_LIMITS["max_chunk"]: chunk_size = PING_LIMITS["max_chunk"]
        
        chunk_size = int(chunk_size)
        
        # Список повідомлень з кнопкою стоп для видалення в кінці (v1.6.3)
        stop_messages = []
        
        for i in range(0, len(user_ids), chunk_size):
            # Перевіряємо прапорець зупинки
            if self.chat_repo.get_stop_flag(clean_chat_id):
                self.logger.info(f"Виклик зупинено в чаті {clean_chat_id}")
                try:
                    sent_stop = await self.bot.send_message(
                        chat_id,
                        "⏸ <b>Виклик зупинено</b>",
                        parse_mode="HTML"
                    )
                    # Чистимо сповіщення про зупинку
                    await self.auto_cleanup(sent_stop)
                except:
                    pass
                break
                break
            
            # v2.7.0: Dynamic Unreg Check - refresh unreg lists per chunk
            chat_data = self.chat_repo.get_chat_data(clean_chat_id)
            temp_unreg = set(map(str, chat_data.get("temp_unreg", [])))
            super_unreg = set(map(str, chat_data.get("super_unreg", [])))
            # Global unreg check
            db_data = self.chat_repo.db.load()
            global_unreg = set(map(str, db_data.get("global_unreg", {}).get("temp", [])))
            global_super = set(map(str, db_data.get("global_unreg", {}).get("super", [])))

            chunk = user_ids[i:i + chunk_size]
            mentions = []
            
            for uid in chunk:
                # Late check for unreg (in case they unreg during the call)
                if uid in temp_unreg or uid in super_unreg or uid in global_unreg or uid in global_super:
                    continue

                label = users[uid]
                
                # v2.6.7: Оновлення імен "на льоту" для ID-користувачів або автоматичне видалення тих, хто вийшов
                # Ми робимо це тільки якщо ім'я - це ID, або періодично (але тут тільки для ID для швидкості)
                if not use_emoji and (label.startswith("ID:") or label == "Користувач"):
                    try:
                        # Retry logic for Bad Gateway
                        member = None
                        for attempt in range(3):
                            try:
                                member = await self.bot.get_chat_member(chat_id, int(uid))
                                break
                            except TelegramServerError:
                                if attempt == 2: raise
                                await asyncio.sleep(0.5)
                            except Exception:
                                raise

                        if member:
                            if member.status in ['left', 'kicked']:
                                self.logger.info(f"Cleanup: Користувач {uid} вийшов з чату. Видаляю з бази.")
                                self.chat_repo.remove_user(clean_chat_id, uid)
                                continue # Пропускаємо пінгування цього юзера
                                
                            if member.user:
                                from utils.helpers import get_user_name as resolve_name
                                new_name = resolve_name(
                                    first_name=member.user.first_name,
                                    last_name=member.user.last_name,
                                    username=member.user.username,
                                    user_id=member.user.id
                                )
                                if not new_name.startswith("ID:"):
                                    label = new_name
                                    # Зберігаємо оновлене ім'я в базу
                                    self.chat_repo.save_user(clean_chat_id, uid, label, update_unreg=False)
                        
                        # Add small delay to prevent flood
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        # Якщо помилка "user not found" або подібні - він точно вийшов або ID недійсний
                        err_msg = str(e).lower().replace('_', ' ')
                        if any(x in err_msg for x in ["user not found", "participant id invalid", "user id invalid", "member not found"]):
                            self.logger.info(f"Cleanup: Користувач {uid} більше не в чаті ({err_msg}). Видаляю з бази.")
                            self.chat_repo.remove_user(clean_chat_id, uid)
                            continue
                            
                        self.logger.error(f"Could not resolve name for {uid}: {e}")
                        
                        # Alert Admin (831190060) about the error
                        try:
                            error_msg = (
                                f"⚠️ <b>Ping Name Error</b>\n"
                                f"Chat: {chat_id}\n"
                                f"User: {uid}\n"
                                f"Error: {str(e)[:100]}"
                            )
                            # Run in background to not block pings
                            asyncio.create_task(self.bot.send_message(831190060, error_msg, parse_mode="HTML"))
                        except: pass

                    except: pass
                
                # FINAL SAFETY: Never show ID in chat
                if not use_emoji and label.startswith("ID:"):
                    label = "Користувач"
                    # Alert Admin about ID fallback - DISABLED due to spam
                    # try:
                    #     error_msg = (
                    #         f"⚠️ <b>Ping ID Fallback</b>\n"
                    #         f"Chat: {chat_id}\n"
                    #         f"User: {uid}\n"
                    #         f"Reason: No name resolved"
                    #     )
                    #     asyncio.create_task(self.bot.send_message(831190060, error_msg, parse_mode="HTML"))
                    # except: pass

                if use_emoji:
                    personal = self.chat_repo.get_user_setting(uid, "personal_emoji")
                    label = personal if personal else random.choice(EMOJIS)
                
                mentions.append(f'<a href="tg://user?id={uid}">{label}</a>')


            
            try:
                # Визначаємо чи потрібна кнопка стоп
                is_first_chunk = (i == 0)
                add_stop_button = True
                
                if first_msg_stop and not is_first_chunk:
                    add_stop_button = False
                
                keyboard = None
                footer_text = ""
                
                if add_stop_button:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🛑 Стоп", callback_data="stop_ping")
                    ]])
                    footer_text = "\n\n(стоп - зупинити)"
                
                # Додаємо к-сть ТІЛЬКИ в перше повідомлення (v1.6.1)
                count_text = ""
                if is_first_chunk and show_count:
                    count_text = f" (👥 {len(user_ids)})"
                
                # Відправляємо повідомлення з повторами при FloodControl (v1.6.5)
                sent_message = None
                while not sent_message:
                    try:
                        sent_message = await self.bot.send_message(
                            chat_id,
                            f"<b>{call_text}{count_text}</b>\n\n" + " ".join(mentions) + footer_text,
                            parse_mode="HTML",
                            reply_markup=keyboard,
                            disable_notification=silent_mode
                        )
                    except Exception as e:
                        if "retry after" in str(e).lower():
                            # Витягуємо час очікування
                            import re
                            wait_match = re.search(r"after (\d+)", str(e).lower())
                            wait_time = int(wait_match.group(1)) if wait_match else 30
                            
                            self.logger.warning(f"Flood Control! Чекаємо {wait_time}с у чаті {chat_id}")
                            
                            # Повідомляємо юзерів, якщо очікування довге
                            if wait_time > 10:
                                try:
                                    wait_msg = await self.bot.send_message(
                                        chat_id, 
                                        f"⏳ <b>Telegram обмежив швидкість.</b>\nАвтоматично продовжу через {wait_time} сек...",
                                        parse_mode="HTML"
                                    )
                                    asyncio.create_task(self.auto_cleanup(wait_msg))
                                except: pass
                            
                            await asyncio.sleep(wait_time + 1)
                            
                            # Перевіряємо, чи не натиснули СТОП поки ми спали
                            if self.chat_repo.get_stop_flag(clean_chat_id):
                                return
                        else:
                            # Якщо інша помилка - логуємо і пропускаємо чанк
                            self.logger.error(f"Помилка при відправці чанку {i}: {e}")
                            break
                
                if not sent_message:
                    continue
                
                # Плануємо авточистку (v1.6.3)
                if not add_stop_button:
                    asyncio.create_task(self.auto_cleanup(sent_message))
                else:
                    stop_messages.append(sent_message)
                
                # Закріплюємо перше повідомлення
                if is_first_chunk and pin_enabled:
                    try:
                        await self.bot.pin_chat_message(chat_id, sent_message.message_id)
                    except Exception as e:
                        self.logger.warning(f"Не вдалося закріпити повідомлення: {e}")
                
                await asyncio.sleep(ping_delay)
            except Exception as e:
                self.logger.error(f"Глобальна помилка в циклі пінгів: {e}")
                continue
        
        # В кінці всіх пінгів плануємо видалення кнопок "Стоп" (v1.6.3)
        for msg in stop_messages:
            asyncio.create_task(self.auto_cleanup(msg))
        
        # Повідомлення про завершення (v2.3.1) - якщо увімкнено show_count
        show_count = self.chat_repo.get_setting(clean_chat_id, "show_count", True)
        if show_count and not self.chat_repo.get_stop_flag(clean_chat_id):
            try:
                stats = self.chat_repo.get_stats(clean_chat_id)
                completion_msg = (
                    f"✅ <b>Виклик завершено!</b>\n"
                    f"👥 Пропінговано: {len(users)}\n"
                    f"🔕 В анрегі: {stats['temp_unreg']} тимч. / {stats['super_unreg']} пост."
                )
                sent = await self.bot.send_message(
                    chat_id, 
                    completion_msg, 
                    parse_mode="HTML"
                )
                asyncio.create_task(self.auto_cleanup(sent))
            except Exception as e:
                self.logger.debug(f"Could not send completion message: {e}")
    
    async def cmd_all(self, message: Message):
        """Пінгує всіх користувачів"""
        self.logger.info(f"Отримано команду закликання від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Увага!"
        
        # Перевірка на шаблон
        if len(parts) > 1:
            chat_id = get_clean_chat_id(message.chat.id)
            templates = self.chat_repo.get_call_templates(chat_id)
            template_name = parts[1].strip()
            
            if template_name in templates:
                call_text = templates[template_name]
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        # v2.8.0: Check default ping type setting
        chat_id_str = get_clean_chat_id(message.chat.id)
        use_emoji = self.chat_repo.get_setting(chat_id_str, "all_ping_emoji", False)
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=use_emoji)
        # Чистимо саму команду
        await self.auto_cleanup(message)
    
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
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=True)
        # Чистимо саму команду
        await self.auto_cleanup(message)
    
    async def cmd_admins(self, message: Message):
        """Пінгує тільки адміністраторів"""
        self.logger.info(f"Отримано команду виклику адмінів від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Виклик адмінів!"
        
        admin_users = await self._get_admin_users(message.chat.id)
        
        if not admin_users:
            sent = await message.answer("❌ Не знайдено адміністраторів")
            await self.auto_cleanup(message, sent)
            return
        
        await self._send_pings(message.chat.id, admin_users, call_text, use_emoji=False)
        # Чистимо саму команду
        await self.auto_cleanup(message)

    async def cmd_active(self, message: Message):
        """Пінгує тільки тих, хто був активним останні 24 години"""
        self.logger.info(f"Отримано команду активного виклику від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "🔥 Виклик найактивніших!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        recent_users = await self._get_recently_active_users(chat_id, hours=24)
        
        if not recent_users:
            sent = await message.answer("ℹ️ За останні 24 години активності не зафіксовано (або всі в анрегу).")
            await self.auto_cleanup(message, sent)
            return
            
        await self._send_pings(message.chat.id, recent_users, call_text, use_emoji=False)
        await self.auto_cleanup(message)

    async def cmd_active_week(self, message: Message):
        """Пінгує тільки тих, хто був активним останні 7 днів"""
        self.logger.info(f"Отримано команду тижневого активного виклику від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📅 Виклик активних за тиждень!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        recent_users = await self._get_recently_active_users(chat_id, hours=168) # 7 днів
        
        if not recent_users:
            sent = await message.answer("ℹ️ За останній тиждень активності не зафіксовано.")
            await self.auto_cleanup(message, sent)
            return
            
        await self._send_pings(message.chat.id, recent_users, call_text, use_emoji=False)
        await self.auto_cleanup(message)

    async def cmd_writers(self, message: Message):
        """Пінгує тільки тих, хто реально писав у чат (24г)"""
        self.logger.info(f"Отримано команду писали від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "✍️ Виклик тих, хто спілкувався!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = await self._get_filtered_users(chat_id, source="message", hours=24)
        
        if not users:
            sent = await message.answer("ℹ️ За останні 24 години ніхто не писав (або всі в анрегу).")
            await self.auto_cleanup(message, sent)
            return
            
        await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
        await self.auto_cleanup(message)

    async def cmd_online(self, message: Message):
        """Пінгує тільки тих, хто онлайн у Telegram (24г)"""
        self.logger.info(f"Отримано команду онлайн від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "🌐 Виклик тих, хто в мережі!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = await self._get_filtered_users(chat_id, source="profile", hours=24)
        
        if not users:
            sent = await message.answer("ℹ️ Зараз немає нікого онлайн (нещодавно).")
            await self.auto_cleanup(message, sent)
            return
            
        await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
        await self.auto_cleanup(message)

    async def _get_filtered_users(self, chat_id: str, source: str = "both", hours: int = 24) -> dict:
        """Внутрішній метод фільтрації за типом активності"""
        chat_data = self.chat_repo.get_chat_data(chat_id)
        all_users = chat_data.get("users", {})
        
        temp_unreg = set(map(str, chat_data.get("temp_unreg", [])))
        super_unreg = set(map(str, chat_data.get("super_unreg", [])))
        db_data = self.chat_repo.db.load()
        global_unreg = set(map(str, db_data.get("global_unreg", {}).get("temp", [])))
        global_super = set(map(str, db_data.get("global_unreg", {}).get("super", [])))
        
        threshold = datetime.now() - timedelta(hours=hours)
        result = {}
        
        for uid, val in all_users.items():
            if uid in temp_unreg or uid in super_unreg or uid in global_unreg or uid in global_super:
                continue
            
            if not isinstance(val, dict): continue
            
            ls_str = val.get("last_seen", "2000-01-01T00:00:00")
            ps_str = val.get("profile_seen", "2000-01-01T00:00:00")
            
            # v2.3.0: Handle mixed timezone-aware and naive datetimes
            try:
                ls = datetime.fromisoformat(ls_str.replace('+00:00', '').replace('Z', ''))
                ps = datetime.fromisoformat(ps_str.replace('+00:00', '').replace('Z', ''))
            except:
                continue  # Skip invalid dates
            
            match_found = False
            if source == "message" and ls > threshold:
                match_found = True
            elif source == "profile" and ps > threshold:
                match_found = True
            elif source == "both" and max(ls, ps) > threshold:
                match_found = True
                
            if match_found:
                result[uid] = val["name"]
        return result

    async def _get_recently_active_users(self, chat_id: str, hours: int = 24) -> dict:
        """Повертає користувачів, які були активні останні N годин (Hybrid)"""
        return await self._get_filtered_users(chat_id, source="both", hours=hours)
    
    async def cmd_anybody(self, message: Message):
        """Викликає випадкового учасника"""
        self.logger.info(f"Отримано команду випадкового виклику від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "🎲 Випадковий учасник:"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            await message.answer(
                "❌ <b>Немає зареєстрованих учасників</b>\n\n"
                "Виконайте <code>/sync</code> для синхронізації учасників чату.",
                parse_mode="HTML"
            )
            return
        
        # Вибираємо випадкового
        user_id = random.choice(list(users.keys()))
        user_name = users[user_id]
        
        sent = await message.answer(
            f"🎯 <b>Випадковий учасник:</b> <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
            f"💭 {call_text}",
            parse_mode="HTML"
        )
        
        # Чистимо команду та результат
        await self.auto_cleanup(message, sent)
    
    async def cmd_stop(self, message: Message):
        """Зупиняє активний виклик"""
        self.logger.info(f"Отримано команду зупинки від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        self.chat_repo.set_stop_flag(chat_id, True)
        sent = await message.answer("⏸ Зупинка виклику...")
        await self.auto_cleanup(message, sent)
    
    async def cmd_list_templates(self, message: Message):
        """Показує список шаблонів викликів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        templates = self.chat_repo.get_call_templates(chat_id)
        
        if not templates:
            sent = await message.answer(
                "📝 <b>Шаблони викликів</b>\n\n"
                "Немає збережених шаблонів.\n\n"
                "Додати: <code>!addcpattern назва</code> (у відповідь на повідомлення з текстом)",
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent)
            return
        
        template_list = "\n".join([f"• <code>{name}</code>" for name in templates.keys()])
        sent = await message.answer(
            f"📋 <b>Шаблони викликів:</b>\n\n{template_list}",
            parse_mode="HTML"
        )
        await self.auto_cleanup(message, sent)
    
    async def cmd_add_template(self, message: Message):
        """Додає шаблон виклику"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        if not message.reply_to_message or not message.reply_to_message.text:
            sent = await message.answer(
                "❌ Використовуйте цю команду у відповідь на повідомлення з текстом шаблону"
            )
            await self.auto_cleanup(message, sent)
            return
        
        # Отримуємо назву шаблону з команди
        import re
        match = re.search(r'^!addcpattern\s+(\S+)', message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву шаблону")
            await self.auto_cleanup(message, sent)
            return
        
        template_name = match.group(1)
        template_text = message.reply_to_message.text
        
        chat_id = get_clean_chat_id(message.chat.id)
        self.chat_repo.add_call_template(chat_id, template_name, template_text)
        
        sent = await message.answer(
            f"✅ Шаблон <code>{template_name}</code> додано!\n\n"
            f"Використання: <code>/all {template_name}</code>",
            parse_mode="HTML"
        )
        await self.auto_cleanup(message, sent)
    
    async def cmd_del_template(self, message: Message):
        """Видаляє шаблон виклику"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!delcpattern\s+(\S+)', message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву шаблону")
            await self.auto_cleanup(message, sent)
            return
        
        template_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.remove_call_template(chat_id, template_name):
            sent = await message.answer(f"✅ Шаблон <code>{template_name}</code> видалено", parse_mode="HTML")
        else:
            sent = await message.answer(f"❌ Шаблон <code>{template_name}</code> не знайдено", parse_mode="HTML")
        await self.auto_cleanup(message, sent)
    
    # === Call Triggers v1.2.0 ===
    
    async def cmd_list_triggers(self, message: Message):
        """Показує список тригерів викликів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_call_triggers(chat_id)
        
        if not triggers:
            sent = await message.answer(
                "🎯 <b>Тригери викликів</b>\n\n"
                "Немає створених тригерів.\n\n"
                "Створити: <code>!addcall назва</code>\n"
                "Додати користувача: <code>!adduser назва</code> (у відповідь)\n"
                "Викликати: <code>!назва</code>",
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent)
            return
        
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        trigger_list = "\n".join([f"• <code>!{name}</code> {emojis.get(name, '')}" for name in triggers.keys()])
        sent = await message.answer(
            f"🎯 <b>Групи викликів:</b>\n\n{trigger_list}\n\n"
            f"ℹ️ Використовуйте <code>!callinfo [назва]</code> для деталі",
            parse_mode="HTML"
        )
        await self.auto_cleanup(message, sent)
    
    async def cmd_trigger_info(self, message: Message):
        """Показує інформацію про тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!callinfo\s+(\S+)', message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву тригера")
            await self.auto_cleanup(message, sent)
            return
        
        trigger_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if not user_ids:
            sent = await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено або порожній",
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent)
            return
        
        # Отримуємо імена користувачів
        chat_data = self.chat_repo.get_chat_data(chat_id)
        all_users = chat_data.get("users", {})
        
        user_list = ""
        for uid in user_ids:
            name = all_users.get(uid, f"User {uid}")
            user_list += f"• {name}\n"
        
        emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name) or ""
        info = (
            f"🎯 <b>Група:</b> !{trigger_name} {emoji}\n"
            f"👥 Учасників: {len(user_ids)}\n\n"
            f"<b>Список:</b>\n{user_list}"
        )
        sent = await message.answer(info, parse_mode="HTML")
        await self.auto_cleanup(message, sent)
    
    async def cmd_add_trigger(self, message: Message):
        """Створює новий тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        # Підтримуємо два формати: !addcall назва або !addcall назва емодзі
        match = re.search(r'^!addcall\s+(\S+)(?:\s+(.+))?', message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву тригера")
            await self.auto_cleanup(message, sent)
            return
        
        trigger_name = match.group(1)
        emoji = match.group(2).strip() if match.group(2) else None
        
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.create_call_trigger(chat_id, trigger_name):
            # Якщо вказано емодзі - встановлюємо одразу
            if emoji:
                self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji)
                sent = await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено з емодзі {emoji}!\n\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>\n"
                    f"Панель реєстрації: <code>!roles_panel</code>",
                    parse_mode="HTML"
                )
            else:
                sent = await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено!\n\n"
                    f"Встановити емодзі: <code>!set_role_emoji {trigger_name} 🎯</code>\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>",
                    parse_mode="HTML"
                )
        else:
            sent = await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> вже існує",
                parse_mode="HTML"
            )
        await self.auto_cleanup(message, sent)
    
    async def cmd_del_trigger(self, message: Message):
        """Видаляє тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!delcall\s+(\S+)', message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву тригера")
            await self.auto_cleanup(message, sent)
            return
        
        trigger_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.delete_call_trigger(chat_id, trigger_name):
            sent = await message.answer(
                f"✅ Тригер <code>!{trigger_name}</code> видалено",
                parse_mode="HTML"
            )
        else:
            sent = await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
            )
        await self.auto_cleanup(message, sent)
    
    async def cmd_add_user_to_trigger(self, message: Message):
        """Додає користувача до тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        if not message.reply_to_message:
            await message.answer(
                "❌ Використовуйте цю команду у відповідь на повідомлення користувача"
            )
            return
        
        import re
        match = re.search(r'^!adduser\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву тригера")
            return
        
        trigger_name = match.group(1)
        user_id = str(message.reply_to_message.from_user.id)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.add_user_to_trigger(chat_id, trigger_name, user_id):
            username = message.reply_to_message.from_user.first_name
            await message.answer(
                f"✅ Користувача <b>{username}</b> додано до тригера <code>!{trigger_name}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
            )
    
    async def cmd_del_user_from_trigger(self, message: Message):
        """Видаляє користувача з тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        if not message.reply_to_message:
            await message.answer(
                "❌ Використовуйте цю команду у відповідь на повідомлення користувача"
            )
            return
        
        import re
        match = re.search(r'^!deluser\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву тригера")
            return
        
        trigger_name = match.group(1)
        user_id = str(message.reply_to_message.from_user.id)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.remove_user_from_trigger(chat_id, trigger_name, user_id):
            username = message.reply_to_message.from_user.first_name
            await message.answer(
                f"✅ Користувача <b>{username}</b> видалено з тригера <code>!{trigger_name}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Користувача не знайдено в тригері <code>!{trigger_name}</code>",
                parse_mode="HTML"
            )
    
    async def cmd_call_trigger(self, message: Message):
        """Викликає користувачів з тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!(\w+)$', message.text)
        if not match:
            return
        
        trigger_name = match.group(1)
        
        # Ігноруємо системні команди
        system_commands = ['кнагє', 'емодзі', 'адміни', 'хтось', 'стоп', 'збір', 'стата', 
                          'анрег', 'суперанрег', 'рег', 'calls', 'cpatterns', 'upatterns']
        if trigger_name.lower() in system_commands:
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        
        # 1. Перевірка на кастомний тригер (Alias для Ping All)
        custom_triggers = self.chat_repo.get_custom_ping_triggers(chat_id)
        type_ = custom_triggers.get(trigger_name.lower())
        
        if not type_:
            # Check global
            global_triggers = self.chat_repo.get_global_ping_triggers()
            type_ = global_triggers.get(trigger_name.lower())
            
        if type_:
            # Це аліас для пінгу всіх!
            self.logger.info(f"Custom trigger (strict) '{trigger_name}' activated")
            
            # Для ! trigger без тексту використовуємо дефолтний
            call_text = "📣 Увага!"
            
            users = self.chat_repo.get_active_users(chat_id)
            if not users:
                return
                
            try:
                await message.delete()
            except:
                pass
                
            if type_ == "emoji":
                await self._send_pings(message.chat.id, users, call_text, use_emoji=True)
            elif type_ == "active":
                recent = await self._get_recently_active_users(chat_id, hours=24)
                if not recent:
                    await message.answer("ℹ️ Немає активних учасників за 24г.")
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif type_ == "active_week":
                recent = await self._get_recently_active_users(chat_id, hours=168)
                if not recent:
                    await message.answer("ℹ️ Немає активних учасників за тиждень.")
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif type_ == "writers":
                recent = await self._get_filtered_users(chat_id, source="message", hours=24)
                if not recent:
                    await message.answer("ℹ️ Немає тих, хто писав за 24г.")
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif type_ == "online":
                recent = await self._get_filtered_users(chat_id, source="profile", hours=24)
                if not recent:
                    await message.answer("ℹ️ Немає онлайн за 24г.")
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            else:
                await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
            return

        # 2. Перевірка на групу користувачів
        user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if not user_ids:
            # Тихо ігноруємо, якщо тригер не знайдено
            return
        
        # Отримуємо імена користувачів (враховуючи сортування за активністю)
        all_users = await self.chat_repo.get_active_users(chat_id)
        
        trigger_users = {}
        for uid, name in all_users.items():
            if uid in user_ids:
                trigger_users[uid] = name


        
        if not trigger_users:
            await message.answer(f"❌ Тригер <code>!{trigger_name}</code> порожній", parse_mode="HTML")
            return
        
        try:
            await message.delete()
        except:
            pass
        
        call_text = f"🎯 Тригер: {trigger_name}"
        await self._send_pings(message.chat.id, trigger_users, call_text, use_emoji=False)
    
    # === Self-Service Roles v1.3.0 ===
    
    async def cmd_roles_panel(self, message: Message):
        """Створює панель самореєстрації на тригери"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_call_triggers(chat_id)
        
        if not triggers:
            await message.answer(
                "❌ Немає створених тригерів.\n\n"
                "Спочатку створіть тригери:\n"
                "<code>!addcall croco</code>\n"
                "<code>!set_role_emoji croco 🐊</code>",
                parse_mode="HTML"
            )
            return
        
        # Отримуємо емодзі для тригерів
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        
        # Створюємо кнопки
        buttons = []
        row = []
        
        for trigger_name in sorted(triggers.keys()):
            emoji = emojis.get(trigger_name, "🎯")
            button_text = f"{emoji} {trigger_name.capitalize()}"
            callback_data = f"role_{trigger_name}"
            
            row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
            
            # По 2 кнопки в ряд
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        # Додаємо останній ряд якщо є
        if row:
            buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ігри/події, на які хочете отримувати сповіщення:\n\n"
            "<i>Натисніть кнопку щоб зареєструватись або вийти</i>"
        )
        
        try:
            await message.delete()
        except:
            pass
        
        await self.bot.send_message(
            message.chat.id,
            panel_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def cmd_set_role_emoji(self, message: Message):
        """Встановлює емодзі для тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!set_role_emoji\s+(\S+)\s+(.+)', message.text)
        if not match:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "Використання: <code>!set_role_emoji назва емодзі</code>\n\n"
                "Приклад:\n"
                "<code>!set_role_emoji croco 🐊</code>",
                parse_mode="HTML"
            )
            return
        
        trigger_name = match.group(1)
        emoji = match.group(2).strip()
        
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji):
            await message.answer(
                f"✅ Емодзі для тригера <code>!{trigger_name}</code> встановлено: {emoji}\n\n"
                f"Оновіть панель: <code>!roles_panel</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
            )
    
    async def callback_role_toggle(self, callback: CallbackQuery):
        """Обробляє натискання кнопки реєстрації"""
        trigger_name = callback.data.replace("role_", "")
        user_id = str(callback.from_user.id)
        chat_id = get_clean_chat_id(callback.message.chat.id)
        
        # Перевіряємо чи користувач вже в тригері
        trigger_users = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if user_id in trigger_users:
            # Видаляємо
            self.chat_repo.remove_user_from_trigger(chat_id, trigger_name, user_id)
            emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name)
            try:
                await callback.answer(
                    f"❌ Ви вийшли з {emoji} {trigger_name}",
                    show_alert=False
                )
            except TelegramBadRequest:
                pass
        else:
            # Додаємо
            self.chat_repo.add_user_to_trigger(chat_id, trigger_name, user_id)
            emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name)
            try:
                await callback.answer(
                    f"✅ Ви зареєструвались на {emoji} {trigger_name}!",
                    show_alert=False
                )
            except TelegramBadRequest:
                pass
        
        # Оновлюємо панель з поточним статусом
        await self._update_roles_panel(callback.message, chat_id, user_id)
    
    async def _update_roles_panel(self, message: Message, chat_id: str, user_id: str):
        """Оновлює панель ролей з позначками"""
        triggers = self.chat_repo.get_call_triggers(chat_id)
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        
        # Створюємо кнопки з позначками
        buttons = []
        row = []
        
        for trigger_name in sorted(triggers.keys()):
            emoji = emojis.get(trigger_name, "🎯")
            trigger_users = self.chat_repo.get_trigger_users(chat_id, trigger_name)
            
            # Додаємо ✅ якщо користувач зареєстрований
            if user_id in trigger_users:
                button_text = f"✅ {emoji} {trigger_name.capitalize()}"
            else:
                button_text = f"{emoji} {trigger_name.capitalize()}"
            
            callback_data = f"role_{trigger_name}"
            
            row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
            
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ігри/події, на які хочете отримувати сповіщення:\n\n"
            "<i>Натисніть кнопку щоб зареєструватись або вийти</i>"
        )
        
        try:
            await message.edit_text(panel_text, reply_markup=keyboard, parse_mode="HTML")
        except:
            pass

    async def callback_stop_ping(self, callback: CallbackQuery):
        """Обробляє натискання кнопки стоп"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id):
            try:
                await callback.answer("❌ Тільки адміни можуть зупиняти виклик", show_alert=True)
            except TelegramBadRequest:
                pass
            return

        chat_id = get_clean_chat_id(callback.message.chat.id)
        self.chat_repo.set_stop_flag(chat_id, True)
        
        # Отримуємо налаштування для звіту
        admin_stop_report = self.chat_repo.get_setting(chat_id, "admin_stop_report", True)
        stop_text = "\n\n🛑 <b>Зупинено користувачем</b>"
        
        if admin_stop_report:
            admin_name = callback.from_user.first_name
            stop_text = f"\n\n🛑 <b>Зупинено адміном: {admin_name}</b>"
        
        try:
            await callback.answer("✅ Зупиняємо виклик...")
        except TelegramBadRequest:
            pass
            
        try:
            await callback.message.edit_text(
                callback.message.text + stop_text,
                parse_mode="HTML",
                reply_markup=None
            )
        except:
            pass

    # === Custom Triggers Logic ===

    async def cmd_add_custom_trigger(self, message: Message):
        """Додає кастомний текстовий тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addtrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0] # Беремо перше слово
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "text")
        await message.answer(f"✅ Додано тригер виклику (текст): `{trigger}`", parse_mode="Markdown")

    async def cmd_add_custom_emoji_trigger(self, message: Message):
        """Додає кастомний емодзі тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addemojitrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "emoji")
        await message.answer(f"✅ Додано тригер виклику (емодзі): `{trigger}`", parse_mode="Markdown")

    async def cmd_add_custom_active_trigger(self, message: Message):
        """Додає кастомний тригер активних користувачів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addactivetrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "active")
        await message.answer(f"✅ Додано тригер виклику (активні 24г): `{trigger}`", parse_mode="Markdown")

    async def cmd_add_custom_active_week_trigger(self, message: Message):
        """Додає кастомний тригер тижневої активності"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addactiveweektrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "active_week")
        await message.answer(f"✅ Додано тригер виклику (тижневий актив): `{trigger}`", parse_mode="Markdown")

    async def cmd_add_custom_writer_trigger(self, message: Message):
        """Додає кастомний тригер для тих, хто писав"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addwritertrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "writers")
        await message.answer(f"✅ Додано тригер виклику (хто писав): `{trigger}`", parse_mode="Markdown")

    async def cmd_add_custom_online_trigger(self, message: Message):
        """Додає кастомний тригер для тих, хто онлайн"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер: `!addonlinetrigger слово`", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "online")
        await message.answer(f"✅ Додано тригер виклику (онлайн): `{trigger}`", parse_mode="Markdown")

    async def cmd_del_custom_trigger(self, message: Message):
        """Видаляє кастомний тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Вкажіть слово-тригер для видалення", parse_mode="Markdown")
            return
            
        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.remove_custom_ping_trigger(chat_id, trigger):
            await message.answer(f"✅ Тригер `{trigger}` видалено", parse_mode="Markdown")
        else:
            await message.answer(f"❌ Тригер `{trigger}` не знайдено", parse_mode="Markdown")

    async def cmd_list_custom_triggers(self, message: Message):
        """Показує список кастомних тригерів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
            
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_custom_ping_triggers(chat_id)
        
        if not triggers:
            await message.answer("📝 У чаті немає кастомних тригерів.")
            return
            
        text = "📝 <b>Кастомні тригери:</b>\n\n"
        for t, type_ in triggers.items():
            if type_ == "text": icon = "📢"
            elif type_ == "emoji": icon = "🤪"
            elif type_ == "active": icon = "🔥"
            elif type_ == "active_week": icon = "📅"
            elif type_ == "writers": icon = "✍️"
            elif type_ == "online": icon = "🌐"
            else: icon = "❓"
            text += f"• <code>{t}</code> ({icon})\n"
            
        await message.answer(text, parse_mode="HTML")

    async def handle_custom_triggers(self, message: Message):
        """Перевіряє чи повідомлення є кастомним тригером"""
        if not message.text:
            return
            
        # Get first word, lowercase, strip prefix
        first_word = message.text.split()[0].lower()
        cleaned_trigger = first_word.lstrip('!').lstrip('/')
        
        # Check privileges first (expensive check only if match found? No, better check triggers first since it's dict lookup)
        chat_id = get_clean_chat_id(message.chat.id)
        
        # 1. Check Chat Triggers
        triggers = self.chat_repo.get_custom_ping_triggers(chat_id)
        found_type = triggers.get(cleaned_trigger)
        
        # 2. Check Global Triggers if not found
        if not found_type:
            global_triggers = self.chat_repo.get_global_ping_triggers()
            found_type = global_triggers.get(cleaned_trigger)
            
        if found_type:
            # Check Admin
            if not await self._is_admin(message.chat.id, message.from_user.id):
                return
                
            # Log
            self.logger.info(f"Custom trigger '{cleaned_trigger}' activated by {message.from_user.id}")
            
            # Extract Call Text (everything after trigger)
            parts = message.text.split(maxsplit=1)
            call_text = parts[1] if len(parts) > 1 else ("📣 Увага!" if found_type == "text" else "📣 Увага!")
            
            # Execute Ping
            users = self.chat_repo.get_active_users(chat_id)
            if not users:
                return
                
            try:
                await message.delete()
            except:
                pass
                
            if found_type == "emoji":
                await self._send_pings(message.chat.id, users, call_text, use_emoji=True)
            elif found_type == "active":
                recent = await self._get_recently_active_users(chat_id, hours=24)
                if not recent:
                    sent = await message.answer("ℹ️ Немає активних учасників за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif found_type == "active_week":
                recent = await self._get_recently_active_users(chat_id, hours=168)
                if not recent:
                    sent = await message.answer("ℹ️ Немає активних учасників за тиждень.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif found_type == "writers":
                recent = await self._get_filtered_users(chat_id, source="message", hours=24)
                if not recent:
                    sent = await message.answer("ℹ️ Немає тих, хто писав за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            elif found_type == "online":
                recent = await self._get_filtered_users(chat_id, source="profile", hours=24)
                if not recent:
                    sent = await message.answer("ℹ️ Немає онлайн за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(message.chat.id, recent, call_text, use_emoji=False)
            else:
                await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
