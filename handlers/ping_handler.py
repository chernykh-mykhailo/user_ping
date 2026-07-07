"""
Ping handlers - команди пінгування (SRP)
"""

import logging
import asyncio
import random
import re
from datetime import datetime, timedelta
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id, render_emoji, extract_custom_emoji_id

from config import PING_LIMITS, EMOJIS, ADMIN_USER_ID
from aiogram.exceptions import TelegramBadRequest, TelegramServerError
from utils.image_utils import create_summary_image
import os


class PingHandler(BaseHandler):
    """
    Обробляє команди пінгування
    Single Responsibility: тільки пінги
    """

    def __init__(
        self, chat_repo, premium_repo, bot: Bot, userbot=None, use_userbot=False
    ):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._active_pings = set()
        self.userbot = userbot
        self.use_userbot = use_userbot
        
        # v2.11.0: Flood protection and request queue for roles panel
        self._panel_locks = {}  # chat_id: asyncio.Lock()
        self._panel_queues = {}  # chat_id: asyncio.Queue()
        self._panel_processing = {}  # chat_id: bool
        self._last_panel_action = {}  # user_id: timestamp
        
        super().__init__(chat_repo, premium_repo)

    def register_handlers(self):
        """Реєструє хендлери пінгування"""
        # Базові виклики
        self.router.message(Command("all"))(self.cmd_all)
        self.router.message(F.text.regexp(re.compile(r"^[!/]кнагє", re.I)))(self.cmd_all)

        self.router.message(Command("emoji"))(self.cmd_emoji)
        self.router.message(F.text.regexp(re.compile(r"^[!/]емодзі", re.I)))(self.cmd_emoji)

        # Нові команди v1.1.0
        self.router.message(Command("admins"))(self.cmd_admins)
        self.router.message(F.text.regexp(re.compile(r"^[!/]адміни", re.I)))(self.cmd_admins)

        self.router.message(Command("anybody"))(self.cmd_anybody)
        self.router.message(F.text.regexp(re.compile(r"^[!/]хтось", re.I)))(self.cmd_anybody)

        self.router.message(Command("active"))(self.cmd_active)
        self.router.message(F.text.regexp(re.compile(r"^[!/]активні", re.I)))(self.cmd_active)

        self.router.message(Command("active_week"))(self.cmd_active_week)
        self.router.message(F.text.regexp(re.compile(r"^[!/]актив_тиждень", re.I)))(
            self.cmd_active_week
        )

        self.router.message(Command("writers"))(self.cmd_writers)
        self.router.message(F.text.regexp(re.compile(r"^[!/]писали", re.I)))(self.cmd_writers)

        self.router.message(Command("online"))(self.cmd_online)
        self.router.message(F.text.regexp(re.compile(r"^[!/]онлайн", re.I)))(self.cmd_online)

        self.router.message(Command("stop", "stopcall"))(self.cmd_stop)
        self.router.message(F.text.regexp(re.compile(r"^[!/]стоп", re.I)))(self.cmd_stop)

        # Sticker Handler
        self.router.message(Command("set_sticker"))(self.cmd_set_sticker)

        # Шаблони викликів
        self.router.message(F.text.regexp(re.compile(r"^!cpatterns$", re.I)))(
            self.cmd_list_templates
        )
        self.router.message(F.text.regexp(re.compile(r"^!addcpattern\s+(\S+)", re.I)))(
            self.cmd_add_template
        )
        self.router.message(F.text.regexp(re.compile(r"^!delcpattern\s+(\S+)", re.I)))(
            self.cmd_del_template
        )

        # Тригери викликів v1.2.0
        self.router.message(F.text.regexp(re.compile(r"^!calls$", re.I)))(self.cmd_list_triggers)
        self.router.message(F.text.regexp(re.compile(r"^!callinfo\s+(\S+)", re.I)))(
            self.cmd_trigger_info
        )
        self.router.message(F.text.regexp(re.compile(r"^!addcall\s+(\S+)", re.I)))(
            self.cmd_add_trigger
        )
        self.router.message(F.text.regexp(re.compile(r"^!delcall\s+(\S+)", re.I)))(
            self.cmd_del_trigger
        )
        self.router.message(F.text.regexp(re.compile(r"^!adduser\s+(\S+)", re.I)))(
            self.cmd_add_user_to_trigger
        )
        self.router.message(F.text.regexp(re.compile(r"^!deluser\s+(\S+)", re.I)))(
            self.cmd_del_user_from_trigger
        )

        # Self-Service Roles v1.3.0
        self.router.message(F.text.startswith("!addtrigger"))(
            self.cmd_add_custom_trigger
        )
        self.router.message(F.text.startswith("!addemojitrigger"))(
            self.cmd_add_custom_emoji_trigger
        )
        self.router.message(F.text.startswith("!addactivetrigger"))(
            self.cmd_add_custom_active_trigger
        )
        self.router.message(F.text.startswith("!addactiveweektrigger"))(
            self.cmd_add_custom_active_week_trigger
        )
        self.router.message(F.text.startswith("!addwritertrigger"))(
            self.cmd_add_custom_writer_trigger
        )
        self.router.message(F.text.startswith("!addonlinetrigger"))(
            self.cmd_add_custom_online_trigger
        )
        self.router.message(F.text.startswith("!deltrigger"))(
            self.cmd_del_custom_trigger
        )
        self.router.message(F.text == "!triggers")(self.cmd_list_custom_triggers)

        # 2. Specific System Commands
        self.router.message(Command("roles_panel"))(self.cmd_roles_panel)
        self.router.message(F.text.regexp(re.compile(r"^!roles_panel$", re.I)))(
            self.cmd_roles_panel
        )
        self.router.message(F.text.regexp(re.compile(r"^!set_role_emoji\s+(\S+)\s+(.+)", re.I)))(
            self.cmd_set_role_emoji
        )
        self.router.callback_query(F.data.startswith("role_"))(
            self.callback_role_toggle
        )
        self.router.callback_query(F.data == "stop_ping")(self.callback_stop_ping)
        
        # Admin Panel for Triggers (v2.11.0)
        self.router.message(Command("admin_panel"))(self.cmd_admin_panel)
        self.router.message(F.text.regexp(re.compile(r"^!admin_panel$", re.I)))(
            self.cmd_admin_panel
        )
        self.router.callback_query(F.data.startswith("admin_"))(
            self.callback_admin_panel
        )
        
        # FSM handlers for admin panel
        from aiogram.fsm.state import State
        self.router.message(AdminStates.waiting_for_trigger_name)(
            self.handle_trigger_creation
        )
        self.router.message(AdminStates.waiting_for_emoji)(
            self.handle_emoji_input
        )

        # 3. Dynamic Triggers (Regex !word)
        self.router.message(Command("allow_unreg"))(self.cmd_allow_unreg)
        self.router.message(Command("deny_unreg"))(self.cmd_deny_unreg)
        self.router.message(Command("set_watermark"))(self.cmd_set_watermark)
        self.router.message(F.text.regexp(re.compile(r"^!(\S+)$", re.I)))(self.cmd_call_trigger)

        # 4. Generic Custom Trigger Handler (Catch-all for no-prefix words)
        # Should be LAST
        self.router.message(F.text)(self.handle_custom_triggers)

    async def cmd_allow_unreg(self, message: Message):
        """Дозволяє використання команди /unreg конкретному користувачу (або всьому чату)"""
        user_id = message.from_user.id
        chat_id = message.chat.id

        # 1. Permission Check
        is_owner = False
        try:
            member = await self.bot.get_chat_member(chat_id, user_id)
            if member.status == "creator":
                is_owner = True
        except Exception:
            pass

        is_bot_admin = str(user_id) == str(ADMIN_USER_ID)
        if not is_owner and not is_bot_admin:
            await message.reply("⚠️ Ця команда доступна тільки власнику чату.")
            return

        clean_chat_id = get_clean_chat_id(chat_id)

        # 2. Identify target user
        target_uid = None
        target_name = "користувачу"

        if message.reply_to_message:
            target_uid = str(message.reply_to_message.from_user.id)
            target_name = message.reply_to_message.from_user.full_name
        else:
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                target_uid = args[1]

        # 3. Action
        if target_uid:
            self.chat_repo.add_to_unreg_whitelist(clean_chat_id, target_uid)
            await message.reply(
                f"✅ Користувачу <b>{target_name}</b> (<code>{target_uid}</code>) дозволено використовувати /unreg у цьому чаті.",
                parse_mode="HTML",
            )
        else:
            # Fallback to chat-wide toggle if no user specified
            self.chat_repo.set_setting(clean_chat_id, "allow_unreg", True)
            await message.reply(
                "✅ Команду /unreg увімкнено для <b>всіх</b> учасників цього чату.",
                parse_mode="HTML",
            )

    async def cmd_deny_unreg(self, message: Message):
        """Забороняє використання команди /unreg конкретному користувачу (або всьому чату)"""
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await self._is_admin(chat_id, user_id):
            return

        clean_chat_id = get_clean_chat_id(chat_id)
        target_uid = None
        target_name = "користувачу"

        if message.reply_to_message:
            target_uid = str(message.reply_to_message.from_user.id)
            target_name = message.reply_to_message.from_user.full_name
        else:
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                target_uid = args[1]

        if target_uid:
            self.chat_repo.remove_from_unreg_whitelist(clean_chat_id, target_uid)
            await message.reply(
                f"❌ Користувачу <b>{target_name}</b> більше не дозволено використовувати /unreg персонально.",
                parse_mode="HTML",
            )
        else:
            self.chat_repo.set_setting(clean_chat_id, "allow_unreg", False)
            await message.reply(
                "❌ Команду /unreg вимкнено для всіх учасників цього чату (крім білого списку).",
                parse_mode="HTML",
            )

    async def cmd_set_watermark(self, message: Message):
        """Встановлює маленький текст знизу справа на зображенні"""
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await self._is_admin(chat_id, user_id):
            await message.reply(
                "⚠️ Тільки адміністратори можуть змінювати водяний знак."
            )
            return

        parts = message.text.split(maxsplit=1)
        watermark = parts[1].strip() if len(parts) > 1 else None

        clean_chat_id = get_clean_chat_id(chat_id)
        self.chat_repo.set_setting(clean_chat_id, "summary_watermark", watermark)

        if watermark:
            await message.reply(
                f"✅ Встановлено водяний знак: <code>{watermark}</code>",
                parse_mode="HTML",
            )
        else:
            await message.reply("🗑 Водяний знак видалено.")

    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        # v2.2.0: Глобальний персонал бота (від модератора і вище) має доступ всюди
        if self.chat_repo.is_bot_moderator(user_id):
            return True

        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            return member.status in ["creator", "administrator"]
        except Exception:
            return False

    async def _get_admin_users(self, chat_id: int) -> dict:
        """Повертає тільки адміністраторів з активних користувачів"""
        clean_chat_id = get_clean_chat_id(chat_id)
        all_users = await self.chat_repo.get_active_users(clean_chat_id)

        admin_users = {}
        for uid, name in all_users.items():
            try:
                member = await self.bot.get_chat_member(chat_id, int(uid))
                if member.status in ["creator", "administrator"]:
                    admin_users[uid] = name
            except Exception:
                continue

        return admin_users

    async def _send_pings(
        self,
        chat_id: int,
        users: dict,
        call_text: str,
        use_emoji: bool = False,
        show_names: bool = False,
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

        # v2.10.22: Захист від подвійних викликів
        if clean_chat_id in self._active_pings:
            try:
                sent = await self.bot.send_message(
                    chat_id,
                    "⚠️ <b>У цьому чаті вже запущено один виклик.</b>\n"
                    "Зачекайте завершення попереднього або зупиніть його командою /stop.",
                    parse_mode="HTML",
                )
                asyncio.create_task(self.auto_cleanup(sent))
            except Exception:
                pass
            return

        self._active_pings.add(clean_chat_id)
        try:
            user_ids = list(users.keys())

            # Логування для дебагу
            old_flag = self.chat_repo.get_stop_flag(clean_chat_id)
            self.logger.info(
                f"[DEBUG] Початок пінгування: stop_flag={old_flag}, users={len(user_ids)}"
            )

            # Скидаємо прапорець зупинки перед початком
            self.chat_repo.set_stop_flag(clean_chat_id, False)
            self.logger.info("[DEBUG] Stop flag скинуто")

            # Отримуємо налаштування чату
            pin_enabled = self.chat_repo.get_setting(clean_chat_id, "pin_enabled", True)
            first_msg_stop = self.chat_repo.get_setting(
                clean_chat_id, "first_msg_stop", True
            )
            silent_mode = self.chat_repo.get_setting(
                clean_chat_id, "silent_mode", False
            )
            show_count = self.chat_repo.get_setting(clean_chat_id, "show_count", True)

            # Динамічні налаштування з урахуванням лімітів
            ping_delay = self.chat_repo.get_setting(
                clean_chat_id, "ping_delay", PING_LIMITS["default_delay"]
            )
            chunk_size = self.chat_repo.get_setting(
                clean_chat_id, "chunk_size", PING_LIMITS["default_chunk"]
            )

            # Перевірка глобальних налаштувань (Global Override)
            # Якщо в панелі /apanel стоїть затримка, вона стає МІНІМАЛЬНОЮ (для захисту від флуду)
            global_delay = self.chat_repo.get_global_setting("ping_delay")
            if global_delay is not None:
                ping_delay = max(ping_delay, global_delay)

            # Hard Limits Safety Check
            if ping_delay < PING_LIMITS["min_delay"]:
                ping_delay = PING_LIMITS["min_delay"]
            if ping_delay > PING_LIMITS["max_delay"]:
                ping_delay = PING_LIMITS["max_delay"]
            if chunk_size < PING_LIMITS["min_chunk"]:
                chunk_size = PING_LIMITS["min_chunk"]
            if chunk_size > PING_LIMITS["max_chunk"]:
                chunk_size = PING_LIMITS["max_chunk"]

            chunk_size = int(chunk_size)

            # Список повідомлень з кнопкою стоп для видалення в кінці (v1.6.3)
            stop_messages = []

            for i in range(0, len(user_ids), chunk_size):
                # Перевіряємо прапорець зупинки
                if self.chat_repo.get_stop_flag(clean_chat_id):
                    self.logger.info(f"Виклик зупинено в чаті {clean_chat_id}")
                    try:
                        sent_stop = await self.bot.send_message(
                            chat_id, "⏸ <b>Виклик зупинено</b>", parse_mode="HTML"
                        )
                        # Чистимо сповіщення про зупинку
                        await self.auto_cleanup(sent_stop)
                    except Exception:
                        pass
                    break

                # v2.10.18: Dynamic Unreg Check - refresh unreg lists per chunk using centralized logic
                (
                    temp_unreg,
                    super_unreg,
                    super_puper,
                    global_unreg,
                    global_super,
                    local_reg,
                ) = self.chat_repo.unreg.get_all_unreg_sets(clean_chat_id)

                chunk = user_ids[i : i + chunk_size]
                mentions = []

                for uid in chunk:
                    # Late check for unreg (v2.10.18: consistent with get_active_users)
                    is_local_unreg = (
                        uid in temp_unreg or uid in super_unreg or uid in super_puper
                    )
                    is_global_unreg = uid in global_unreg or uid in global_super

                    if is_local_unreg or (is_global_unreg and uid not in local_reg):
                        continue

                    label = users[uid]

                    # v2.6.7: Оновлення імен "на льоту" для ID-користувачів або автоматичне видалення тих, хто вийшов
                    # Ми робимо це тільки якщо ім'я - це ID, або періодично (але тут тільки для ID для швидкості)
                    if not use_emoji and (
                        label.startswith("ID:") or label == "Користувач"
                    ):
                        try:
                            # Retry logic for Bad Gateway
                            member = None
                            for attempt in range(3):
                                try:
                                    member = await self.bot.get_chat_member(
                                        chat_id, int(uid)
                                    )
                                    break
                                except TelegramServerError:
                                    if attempt == 2:
                                        raise
                                    await asyncio.sleep(0.5)
                                except Exception:
                                    raise

                            if member:
                                if member.status in ["left", "kicked"]:
                                    self.logger.info(
                                        f"Cleanup: Користувач {uid} вийшов з чату. Видаляю з бази."
                                    )
                                    self.chat_repo.remove_user(clean_chat_id, uid)
                                    continue  # Пропускаємо пінгування цього юзера

                                if member.user:
                                    from utils.helpers import (
                                        get_user_name as resolve_name,
                                    )

                                    new_name = resolve_name(
                                        first_name=member.user.first_name,
                                        last_name=member.user.last_name,
                                        username=member.user.username,
                                        user_id=member.user.id,
                                    )
                                    if not new_name.startswith("ID:"):
                                        label = new_name
                                        # Зберігаємо оновлене ім'я в базу
                                        self.chat_repo.save_user(
                                            clean_chat_id,
                                            uid,
                                            label,
                                            update_unreg=False,
                                        )

                            # Add small delay to prevent flood
                            await asyncio.sleep(0.1)

                        except Exception as e:
                            # Якщо помилка "user not found" або подібні - він точно вийшов або ID недійсний
                            err_msg = str(e).lower().replace("_", " ")
                            if any(
                                x in err_msg
                                for x in [
                                    "user not found",
                                    "participant id invalid",
                                    "user id invalid",
                                    "member not found",
                                ]
                            ):
                                self.logger.info(
                                    f"Cleanup: Користувач {uid} більше не в чаті ({err_msg}). Видаляю з бази."
                                )
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
                                asyncio.create_task(
                                    self.bot.send_message(
                                        831190060, error_msg, parse_mode="HTML"
                                    )
                                )
                            except Exception:
                                pass

                        except Exception:
                            pass

                    # FINAL SAFETY: Never show ID in chat
                    if not use_emoji and label.startswith("ID:"):
                        label = "Користувач"

                    # Зберігаємо ім'я користувача до того, як label буде перезаписано емодзі
                    user_name = label

                    if use_emoji:
                        personal = self.chat_repo.get_user_setting(
                            uid, "personal_emoji"
                        )

                        # v2.10.11: Логіка розділення:
                        # 1. Якщо є персональний емодзі - використовуємо його завжди.
                        # 2. Якщо немає:
                        #    - У команді з іменами (/all) - нічого не додаємо (просто ім'я).
                        #    - У команді БЕЗ імен (/emoji) - ставимо рандомний емодзі, щоб не палити ім'я.
                        emoji_label = personal
                        if not emoji_label:
                            emoji_label = random.choice(EMOJIS)

                        # v2.10.4: ПРЕМІУМ-ЕМОДЗІ - зберігаємо ID для entities
                        if emoji_label and str(emoji_label).startswith("tg-emoji:"):
                            emoji_id = emoji_label.split(":")[1]
                            # Спробуємо знайти alt-символ в мапінгу
                            alt = (
                                self.chat_repo.emoji_packs.get_registered_emoji_alt(
                                    emoji_id
                                )
                                or "✨"
                            )
                            # Зберігаємо: (type, emoji_id, uid, user_name, alt)
                            mentions.append(
                                ("custom_emoji", emoji_id, uid, user_name, alt)
                            )
                        elif emoji_label:
                            import html

                            safe_emoji = html.escape(str(emoji_label))
                            mentions.append(("regular", safe_emoji, uid, user_name))
                        else:
                            # Якщо емодзі немає - просто текст (але для /emoji це може бути порожньо)
                            import html

                            safe_name = html.escape(user_name)
                            mentions.append(("text", safe_name, uid, user_name))
                    else:
                        # v2.10.26: У виклику з іменами (/all) також додаємо персональний емодзі поруч
                        personal = self.chat_repo.get_user_setting(uid, "personal_emoji")
                        
                        if personal:
                            if str(personal).startswith("tg-emoji:"):
                                emoji_id = str(personal).split(":")[1]
                                alt = self.chat_repo.emoji_packs.get_registered_emoji_alt(emoji_id) or "✨"
                                mentions.append(("custom_emoji", emoji_id, uid, user_name, alt))
                            else:
                                import html
                                safe_emoji = html.escape(str(personal))
                                mentions.append(("regular", safe_emoji, uid, user_name))
                        else:
                            import html
                            safe_label = html.escape(str(label))
                            mentions.append(("text", safe_label, uid, user_name))

                try:
                    # Визначаємо чи потрібна кнопка стоп
                    is_first_chunk = i == 0
                    add_stop_button = True

                    if first_msg_stop and not is_first_chunk:
                        add_stop_button = False

                    keyboard = None
                    footer_text = ""

                    if add_stop_button:
                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="🛑 Стоп", callback_data="stop_ping"
                                    )
                                ]
                            ]
                        )
                        footer_text = "\n\n(стоп - зупинити)"

                    # Додаємо к-сть ТІЛЬКИ в перше повідомлення (v1.6.1)
                    count_text = ""
                    if is_first_chunk and show_count:
                        count_text = f" (👥 {len(user_ids)})"

                    import html

                    sent_message = None
                    while not sent_message:
                        try:
                            # v2.10.25: НЕ ескейпимо call_text тут, бо він може містити HTML розмітку від хендлерів
                            # Але ескейпимо лічильник, щоб бути в безпеці
                            text_parts = [f"{call_text}{html.escape(count_text)}\n\n"]

                            for mention_data in mentions:
                                if not isinstance(mention_data, tuple):
                                    continue

                                type_ = mention_data[0]
                                uid = mention_data[2]
                                user_name = (
                                    mention_data[3]
                                    if len(mention_data) > 3
                                    else "Користувач"
                                )
                                safe_name = html.escape(user_name)

                                if type_ == "custom_emoji":
                                    emoji_id = mention_data[1]
                                    alt = (
                                        mention_data[4]
                                        if len(mention_data) > 4
                                        else "✨"
                                    )

                                    if show_names:
                                        # 🌸 <a href="...">Мишко</a>
                                        # Клік по емодзі відкриє пак, клік по імені - профіль. Обидва пінгують.
                                        text_parts.append(
                                            f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>'
                                        )
                                        text_parts.append(
                                            f' <a href="tg://user?id={uid}">{safe_name}</a>'
                                        )
                                    else:
                                        # ПРЕМИУМ ЕМОДЗІ + НЕВИДИМИЙ ПІНГ
                                        # <tg-emoji> відкриває пак, <a> з ZWSP робить невидимий пінг поруч
                                        text_parts.append(
                                            f'<tg-emoji emoji-id="{emoji_id}">{alt}</tg-emoji>'
                                        )
                                        text_parts.append(
                                            f'<a href="tg://user?id={uid}">&#8203;</a>'
                                        )

                                    text_parts.append(" ")
                                else:
                                    # ЗВИЧАЙНИЙ ЕМОДЗІ або ТЕКСТ
                                    val = mention_data[1]

                                    if show_names:
                                        if type_ == "text":
                                            # Тільки ім'я-посилання: <a href="...">Ім'я</a>
                                            text_parts.append(
                                                f'<a href="tg://user?id={uid}">{safe_name}</a>'
                                            )
                                        else:
                                            # Емодзі + ім'я-посилання: 🦾 <a href="...">Ім'я</a>
                                            text_parts.append(
                                                f'{val} <a href="tg://user?id={uid}">{safe_name}</a>'
                                            )
                                    else:
                                        # Тільки емодзі-посилання: <a href="...">🦾</a>
                                        text_parts.append(
                                            f'<a href="tg://user?id={uid}">{val}</a>'
                                        )

                                    text_parts.append(" ")

                            full_message = "".join(text_parts).rstrip() + html.escape(
                                footer_text
                            )

                            sent_message = await self.bot.send_message(
                                chat_id,
                                full_message,
                                parse_mode="HTML",
                                reply_markup=keyboard,
                                disable_notification=silent_mode,
                            )

                        except Exception as e:
                            if "retry after" in str(e).lower():
                                # Витягуємо час очікування
                                import re

                                wait_match = re.search(r"after (\d+)", str(e).lower())
                                wait_time = (
                                    int(wait_match.group(1)) if wait_match else 30
                                )

                                self.logger.warning(
                                    f"Flood Control! Чекаємо {wait_time}с у чаті {chat_id}"
                                )

                                # Повідомляємо юзерів, якщо очікування довге
                                if wait_time > 10:
                                    try:
                                        wait_msg = await self.bot.send_message(
                                            chat_id,
                                            f"⏳ <b>Telegram обмежив швидкість.</b>\nАвтоматично продовжу через {wait_time} сек...",
                                            parse_mode="HTML",
                                        )
                                        asyncio.create_task(self.auto_cleanup(wait_msg))
                                    except Exception:
                                        pass

                                await asyncio.sleep(wait_time + 1)

                                # Перевіряємо, чи не натиснули СТОП поки ми спали
                                if self.chat_repo.get_stop_flag(clean_chat_id):
                                    return
                            else:
                                # Якщо помилка "Invalid custom emoji", спробуємо відправити без них
                                if "invalid custom emoji" in str(e).lower():
                                    self.logger.warning(
                                        f"Invalid emoji in chunk {i}, retrying without custom tags"
                                    )
                                    # Очищаємо mentions від тегів <tg-emoji>
                                    import re

                                    clean_mentions = [
                                        re.sub(
                                            r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", m
                                        )
                                        for m in mentions
                                    ]
                                    try:
                                        sent_message = await self.bot.send_message(
                                            chat_id,
                                            f"<b>{call_text}{count_text}</b>\n\n"
                                            + " ".join(clean_mentions)
                                            + footer_text,
                                            parse_mode="HTML",
                                            reply_markup=keyboard,
                                            disable_notification=silent_mode,
                                        )
                                        continue  # Спрацювало!
                                    except Exception as e2:
                                        self.logger.error(
                                            f"Failed even without emojis: {e2}"
                                        )

                                self.logger.error(
                                    f"Помилка при відправці чанку {i}: {e}"
                                )
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
                            await self.bot.pin_chat_message(
                                chat_id,
                                sent_message.message_id,
                                disable_notification=True,
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"Не вдалося закріпити повідомлення: {e}"
                            )

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

                    # Check for sticker configuration
                    sticker_path = self.chat_repo.get_setting(
                        clean_chat_id, "summary_sticker"
                    )

                    info_lines = [
                        "✅ Виклик завершено!",
                        f"👥 Пропінговано: {len(users)}",
                        f"🔕 Анрегнуто: {stats['temp_unreg']} / {stats['super_unreg']} пост.",
                    ]
                    text_msg = "\n".join(info_lines)

                    sent = None
                    if sticker_path and os.path.exists(sticker_path):
                        # Generate image
                        output_path = f"data/temp_{clean_chat_id}.webp"
                        watermark = self.chat_repo.get_setting(
                            clean_chat_id, "summary_watermark"
                        )
                        result_path = create_summary_image(
                            sticker_path, info_lines, output_path, watermark=watermark
                        )

                        if result_path:
                            from aiogram.types import FSInputFile

                            sticker_file = FSInputFile(result_path)
                            sent = await self.bot.send_sticker(chat_id, sticker_file)
                            # Clean up temp file
                            try:
                                os.remove(result_path)
                            except Exception:
                                pass
                        else:
                            # Fallback to text
                            sent = await self.bot.send_message(
                                chat_id, text_msg, parse_mode="HTML"
                            )
                    else:
                        sent = await self.bot.send_message(
                            chat_id, text_msg, parse_mode="HTML"
                        )

                    if sent:
                        asyncio.create_task(self.auto_cleanup(sent))
                except Exception as e:
                    self.logger.debug(f"Could not send completion message: {e}")
        finally:
            self._active_pings.discard(clean_chat_id)

    async def cmd_set_sticker(self, message: Message):
        """Встановлює або видаляє стікер для фону підсумків"""
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await self._is_admin(chat_id, user_id):
            return

        clean_chat_id = get_clean_chat_id(chat_id)

        # Якщо це не реплай на стікер — видаляємо налаштування
        if not message.reply_to_message or not message.reply_to_message.sticker:
            old_path = self.chat_repo.get_setting(clean_chat_id, "summary_sticker")
            self.chat_repo.set_setting(clean_chat_id, "summary_sticker", None)

            if old_path and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass

            await message.reply(
                "🗑 Стікер для підсумків видалено. Тепер будуть надсилатись звичайні текстові звіти."
            )
            return

        try:
            sticker = message.reply_to_message.sticker
            chat_id = get_clean_chat_id(message.chat.id)

            # Витягуємо текст після команди (водамарка)
            text_parts = message.text.split(maxsplit=1)
            watermark = text_parts[1].strip() if len(text_parts) > 1 else None

            # Create stickers directory if not exists
            stickers_dir = "data/stickers"
            if not os.path.exists(stickers_dir):
                os.makedirs(stickers_dir)

            # Define path
            file_ext = "webp"  # Default for stickers
            save_path = f"{stickers_dir}/{chat_id}.{file_ext}"

            # Download
            await self.bot.download(sticker, destination=save_path)

            # Save settings
            self.chat_repo.set_setting(chat_id, "summary_sticker", save_path)
            self.chat_repo.set_setting(chat_id, "summary_watermark", watermark)

            msg_text = "✅ Стікер встановлено! Тепер він буде використовуватись для підсумків виклику."
            if watermark:
                msg_text += f"\n✍️ Встановлено підпис: {watermark}"

            await message.reply(msg_text)
        except Exception as e:
            self.logger.error(f"Failed to set sticker: {e}")
            await message.reply(f"❌ Помилка при збереженні стікера: {e}")

    async def cmd_all(self, message: Message):
        """Пінгує всіх користувачів"""
        self.logger.info(f"Отримано команду закликання від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import html

        parts = message.text.split(maxsplit=1)
        user_text = parts[1] if len(parts) > 1 else "📣 Увага!"

        # Перевірка на шаблон
        if len(parts) > 1:
            chat_id = get_clean_chat_id(message.chat.id)
            templates = self.chat_repo.get_call_templates(chat_id)
            template_name = parts[1].strip()

            if template_name in templates:
                # Шаблон може містити HTML (наприклад, <b>), тому ми його НЕ ескейпимо
                # (власник шаблону сам відповідає за валідність HTML)
                call_text = templates[template_name]
            else:
                call_text = html.escape(user_text)
        else:
            call_text = html.escape(user_text)

        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)

        if not users:
            return

        # v2.10.20: Отримуємо налаштування типу /all з бази
        all_ping_emoji = self.chat_repo.get_setting(chat_id, "all_ping_emoji", False)

        # Якщо all_ping_emoji=True -> Тільки емодзі (show_names=False)
        # Якщо all_ping_emoji=False -> Імена + емодзі (show_names=True)
        show_names = not all_ping_emoji

        await self._send_pings(
            message.chat.id, users, call_text, use_emoji=True, show_names=show_names
        )
        # Чистимо саму команду
        await self.auto_cleanup(message)

    async def cmd_emoji(self, message: Message):
        """Пінгує всіх користувачів емодзі"""
        self.logger.info(f"Отримано команду емодзі від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import html

        parts = message.text.split(maxsplit=1)
        call_text = html.escape(parts[1]) if len(parts) > 1 else "📣 Увага!"

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

        import html

        parts = message.text.split(maxsplit=1)
        call_text = html.escape(parts[1]) if len(parts) > 1 else "📣 Виклик адмінів!"

        admin_users = await self._get_admin_users(message.chat.id)

        if not admin_users:
            sent = await message.answer("❌ Не знайдено адміністраторів")
            await self.auto_cleanup(message, sent)
            return

        await self._send_pings(message.chat.id, admin_users, call_text, use_emoji=True, show_names=True)

        # Чистимо саму команду
        await self.auto_cleanup(message)

    async def cmd_active(self, message: Message):
        """Пінгує тільки тих, хто був активним останні 24 години"""
        self.logger.info(
            f"Отримано команду активного виклику від {message.from_user.id}"
        )

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import html

        parts = message.text.split(maxsplit=1)
        call_text = (
            html.escape(parts[1]) if len(parts) > 1 else "🔥 Виклик найактивніших!"
        )

        chat_id = get_clean_chat_id(message.chat.id)
        recent_users = await self._get_recently_active_users(chat_id, hours=24)

        if not recent_users:
            sent = await message.answer(
                "ℹ️ За останні 24 години активності не зафіксовано (або всі в анрегу)."
            )
            await self.auto_cleanup(message, sent)
            return

        await self._send_pings(
            message.chat.id, recent_users, call_text, use_emoji=True, show_names=True
        )
        await self.auto_cleanup(message)

    async def cmd_active_week(self, message: Message):
        """Пінгує тільки тих, хто був активним останні 7 днів"""
        self.logger.info(
            f"Отримано команду тижневого активного виклику від {message.from_user.id}"
        )

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import html

        parts = message.text.split(maxsplit=1)
        call_text = (
            html.escape(parts[1])
            if len(parts) > 1
            else "📅 Виклик активних за тиждень!"
        )

        chat_id = get_clean_chat_id(message.chat.id)
        recent_users = await self._get_recently_active_users(
            chat_id, hours=168
        )  # 7 днів

        if not recent_users:
            sent = await message.answer(
                "ℹ️ За останній тиждень активності не зафіксовано."
            )
            await self.auto_cleanup(message, sent)
            return

        await self._send_pings(
            message.chat.id, recent_users, call_text, use_emoji=True, show_names=True
        )
        await self.auto_cleanup(message)

    async def cmd_writers(self, message: Message):
        """Пінгує тільки тих, хто реально писав у чат (24г)"""
        self.logger.info(f"Отримано команду писали від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import html

        parts = message.text.split(maxsplit=1)
        call_text = (
            html.escape(parts[1])
            if len(parts) > 1
            else "✍️ Виклик тих, хто спілкувався!"
        )

        chat_id = get_clean_chat_id(message.chat.id)
        users = await self._get_filtered_users(chat_id, source="message", hours=24)

        if not users:
            sent = await message.answer(
                "ℹ️ За останні 24 години ніхто не писав (або всі в анрегу)."
            )
            await self.auto_cleanup(message, sent)
            return

        await self._send_pings(message.chat.id, users, call_text, use_emoji=True, show_names=True)
        await self.auto_cleanup(message)

    async def cmd_online(self, message: Message):
        """Пінгує тих, хто зараз онлайн або був активним нещодавно (v2.10.24)"""
        self.logger.info(f"Отримано команду онлайн від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        parts = message.text.split(maxsplit=1)
        chat_id = get_clean_chat_id(message.chat.id)

        # v2.10.24: Гібридний підхід — UserBot + База (Профілі + Активність)
        users = {}
        using_userbot = False

        # 1. Спроба через UserBot (найсвіжіші дані)
        if self.use_userbot and self.userbot:
            try:
                bot_users = await self.userbot.get_online_users(message.chat.id)
                if bot_users:
                    users.update(bot_users)
                    using_userbot = True
            except Exception as e:
                self.logger.error(f"Userbot online check failed: {e}")

        # 2. Додаємо тих, хто писав у чат недавно (3 години) — фікс приватності
        # Бо навіть якщо статус приховано, факт повідомлення — це активність
        active_writers = await self._get_filtered_users(
            chat_id, source="message", hours=3
        )
        users.update(active_writers)

        # 3. Додаємо тих, чиї профілі ми бачили (24 години) як запасний варіант
        recent_profiles = await self._get_filtered_users(
            chat_id, source="profile", hours=24
        )
        users.update(recent_profiles)

        if not users:
            sent = await message.answer(
                "ℹ️ Зараз немає нікого онлайн (або всі приховані)."
            )
            await self.auto_cleanup(message, sent)
            return

        # Додаємо помітку для UX
        prefix = ""
        if using_userbot:
            prefix = "⚡️ <i>(Актуально через UB)</i>\n"
        elif active_writers:
            prefix = "🕒 <i>(За активністю в чаті)</i>\n"

        import html

        # Текст користувача ескейпимо окремо, а префікс має бути сирим HTML (v2.10.25)
        user_text = (
            html.escape(parts[1]) if len(parts) > 1 else "🌐 Виклик тих, хто в мережі!"
        )

        if prefix:
            call_text = prefix + user_text
        else:
            call_text = user_text

        await self._send_pings(message.chat.id, users, call_text, use_emoji=True, show_names=True)
        await self.auto_cleanup(message)

    async def _get_filtered_users(
        self, chat_id: str, source: str = "both", hours: int = 24
    ) -> dict:
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
            if (
                uid in temp_unreg
                or uid in super_unreg
                or uid in global_unreg
                or uid in global_super
            ):
                continue

            if not isinstance(val, dict):
                continue

            ls_str = val.get("last_seen", "2000-01-01T00:00:00")
            ps_str = val.get("profile_seen", "2000-01-01T00:00:00")

            # v2.3.0: Handle mixed timezone-aware and naive datetimes
            try:
                ls = datetime.fromisoformat(
                    ls_str.replace("+00:00", "").replace("Z", "")
                )
                ps = datetime.fromisoformat(
                    ps_str.replace("+00:00", "").replace("Z", "")
                )
            except Exception:
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
        self.logger.info(
            f"Отримано команду випадкового виклику від {message.from_user.id}"
        )

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
                parse_mode="HTML",
            )
            return

        # Вибираємо випадкового
        user_id = random.choice(list(users.keys()))
        user_name = users[user_id]
        # v2.9.0: Fix for special characters
        import html

        user_name = html.escape(str(user_name))

        sent = await message.answer(
            f"🎯 <b>Випадковий учасник:</b> <a href='tg://user?id={user_id}'>{user_name}</a>\n\n"
            f"💭 {call_text}",
            parse_mode="HTML",
        )

        # Чистимо команду та результат
        await self.auto_cleanup(message, sent)


    async def cmd_stop(self, message: Message):
        """Зупиняє активний виклик"""
        self.logger.info(f"Отримано команду зупинки від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        chat_id = get_clean_chat_id(message.chat.id)

        # v2.10.25: Перевіряємо чи є активний виклик перед тим як писати про зупинку
        if chat_id not in self._active_pings:
            # Якщо виклику немає, просто видаляємо команду стоп без зайвих повідомлень (або можна відповісти)
            # await message.reply("ℹ️ Зараз немає активних викликів.")
            await self.auto_cleanup(message)
            return

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
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        template_list = "\n".join(
            [f"• <code>{name}</code>" for name in templates.keys()]
        )
        sent = await message.answer(
            f"📋 <b>Шаблони викликів:</b>\n\n{template_list}", parse_mode="HTML"
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

        match = re.search(r"^!addcpattern\s+(\S+)", message.text)
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
            parse_mode="HTML",
        )
        await self.auto_cleanup(message, sent)

    async def cmd_del_template(self, message: Message):
        """Видаляє шаблон виклику"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import re

        match = re.search(r"^!delcpattern\s+(\S+)", message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву шаблону")
            await self.auto_cleanup(message, sent)
            return

        template_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)

        if self.chat_repo.remove_call_template(chat_id, template_name):
            sent = await message.answer(
                f"✅ Шаблон <code>{template_name}</code> видалено", parse_mode="HTML"
            )
        else:
            sent = await message.answer(
                f"❌ Шаблон <code>{template_name}</code> не знайдено", parse_mode="HTML"
            )
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
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        trigger_list = "\n".join(
            [
                f"• <code>!{name}</code> {render_emoji(emojis.get(name, ''))}"
                for name in triggers.keys()
            ]
        )
        sent = await message.answer(
            f"🎯 <b>Групи викликів:</b>\n\n{trigger_list}\n\n"
            f"ℹ️ Використовуйте <code>!callinfo [назва]</code> для деталі",
            parse_mode="HTML",
        )
        await self.auto_cleanup(message, sent)

    async def cmd_trigger_info(self, message: Message):
        """Показує інформацію про тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import re

        match = re.search(r"^!callinfo\s+(\S+)", message.text)
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
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        # Отримуємо імена користувачів
        chat_data = self.chat_repo.get_chat_data(chat_id)
        all_users = chat_data.get("users", {})

        user_list = ""
        for uid in user_ids:
            name = all_users.get(uid, f"User {uid}")
            # v2.10.26: Додаємо емодзі премів
            personal = self.chat_repo.get_user_setting(uid, "personal_emoji")
            emoji_prefix = ""
            if personal:
                emoji_prefix = f"{render_emoji(personal)} "
            
            user_list += f"• {emoji_prefix}{name}\n"

        emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name) or ""
        info = (
            f"🎯 <b>Група:</b> !{trigger_name} {render_emoji(emoji)}\n"
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
        match = re.search(r"^!addcall\s+(\S+)(?:\s+(.+))?", message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву тригера")
            await self.auto_cleanup(message, sent)
            return

        trigger_name = match.group(1)

        # v2.10.28: Покращене автоматичне витягування емодзі (будь-де у слові)
        import re
        # Шукаємо перший символ-не-слово (емодзі)
        emoji_match = re.search(r'([^\w\s\d])', trigger_name)
        
        custom_id = extract_custom_emoji_id(message)
        if custom_id:
            emoji = f"tg-emoji:{custom_id}"
        else:
            emoji = match.group(2).strip() if match.group(2) else None

        if not emoji and emoji_match:
            emoji = emoji_match.group(1)
            # Видаляємо емодзі з назви тригера
            trigger_name = trigger_name.replace(emoji, "").strip()
            if not trigger_name:
                trigger_name = emoji
                emoji = None

        chat_id = get_clean_chat_id(message.chat.id)

        if self.chat_repo.create_call_trigger(chat_id, trigger_name):
            # Якщо вказано емодзі - встановлюємо одразу
            if emoji:
                self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji)
                display_emoji = render_emoji(emoji)
                sent = await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено з емодзі {display_emoji}!\n\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>\n"
                    f"Панель реєстрації: <code>!roles_panel</code>",
                    parse_mode="HTML",
                )
            else:
                sent = await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено!\n\n"
                    f"Встановити емодзі: <code>!set_role_emoji {trigger_name} 🎯</code>\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>",
                    parse_mode="HTML",
                )
        else:
            sent = await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> вже існує", parse_mode="HTML"
            )
        await self.auto_cleanup(message, sent)

    async def cmd_del_trigger(self, message: Message):
        """Видаляє тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import re

        match = re.search(r"^!delcall\s+(\S+)", message.text)
        if not match:
            sent = await message.answer("❌ Вкажіть назву тригера")
            await self.auto_cleanup(message, sent)
            return

        trigger_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)

        if self.chat_repo.delete_call_trigger(chat_id, trigger_name):
            sent = await message.answer(
                f"✅ Тригер <code>!{trigger_name}</code> видалено", parse_mode="HTML"
            )
        else:
            sent = await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено", parse_mode="HTML"
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

        match = re.search(r"^!adduser\s+(\S+)", message.text)
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
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено", parse_mode="HTML"
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
        match = re.search(r"^!deluser\s+(\S+)", message.text)
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
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"❌ Користувача не знайдено в тригері <code>!{trigger_name}</code>",
                parse_mode="HTML",
            )

    async def cmd_call_trigger(self, message: Message):
        """Викликає користувачів з тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        import re
        match = re.search(r"^!(\S+)$", message.text)
        if not match:
            return

        trigger_name = match.group(1)
        system_commands = ["кнагє", "емодзі", "адміни", "хтось", "стоп", "збір", "стата", "анрег", "суперанрег", "рег", "calls", "cpatterns", "upatterns"]
        if trigger_name.lower() in system_commands:
            return

        chat_id = get_clean_chat_id(message.chat.id)
        
        # 1. Alias Check
        custom_triggers = self.chat_repo.get_custom_ping_triggers(chat_id)
        type_ = custom_triggers.get(trigger_name.lower()) or self.chat_repo.get_global_ping_triggers().get(trigger_name.lower())

        if type_:
            self.logger.info(f"Custom trigger '{trigger_name}' activated")
            call_text = "📣 Увага!"
            users = self.chat_repo.get_active_users(chat_id)
            if not users: return
            try: await message.delete()
            except: pass
            
            if type_ == "active": users = await self._get_recently_active_users(chat_id, 24)
            elif type_ == "active_week": users = await self._get_recently_active_users(chat_id, 168)
            elif type_ == "writers": users = await self._get_filtered_users(chat_id, "message", 24)
            elif type_ == "online": users = await self._get_filtered_users(chat_id, "profile", 24)

            await self._send_pings(message.chat.id, users, call_text, use_emoji=True, show_names=True)
            return

        # 2. Group Check
        user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        if not user_ids: return

        all_users = self.chat_repo.get_all_users_with_names(chat_id)
        trigger_users = {uid: name for uid, name in all_users.items() if uid in user_ids}

        if not trigger_users:
            await message.answer(f"❌ Тригер <code>!{trigger_name}</code> порожній", parse_mode="HTML")
            return

        try: await message.delete()
        except: pass

        await self._send_pings(message.chat.id, trigger_users, f"🎯 Тригер: {trigger_name}", use_emoji=True, show_names=True)

    async def cmd_roles_panel(self, message: Message):
        """Створює панель самореєстрації з покращеним UI"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_call_triggers(chat_id)
        
        if not triggers:
            await message.answer(
                "❌ <b>Немає тригерів для панелі</b>\n\n"
                "Створіть тригери командою:\n"
                "<code>!addcall назва</code>",
                parse_mode="HTML"
            )
            return

        # v2.11.0: Initialize lock and queue for this chat
        if chat_id not in self._panel_locks:
            self._panel_locks[chat_id] = asyncio.Lock()
            self._panel_queues[chat_id] = asyncio.Queue()
            self._panel_processing[chat_id] = False

        await self._send_roles_panel(message.chat.id, chat_id)
        
        try: await message.delete()
        except: pass

    async def cmd_set_role_emoji(self, message: Message):
        """Встановлює емодзі для ролі"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r"^!set_role_emoji\s+(\S+)", message.text)
        if not match:
            await message.answer(
                "❌ <b>Формат:</b> <code>!set_role_emoji назва 🎯</code>\n\n"
                "Можна використовувати:\n"
                "• Звичайні емодзі: 🎯\n"
                "• Кастомні: відповісти на повідомлення з емодзі",
                parse_mode="HTML"
            )
            return
        
        trigger_name = match.group(1)
        custom_id = extract_custom_emoji_id(message)
        emoji = f"tg-emoji:{custom_id}" if custom_id else message.text.split()[-1]
        
        chat_id = get_clean_chat_id(message.chat.id)
        if self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji):
            await message.answer(
                f"✅ Для <code>!{trigger_name}</code> встановлено {render_emoji(emoji)}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Помилка встановлення")

    async def callback_role_toggle(self, callback: CallbackQuery):
        """Тобл реєстрації користувача з flood protection"""
        trigger = callback.data.replace("role_", "")
        uid = str(callback.from_user.id)
        cid = get_clean_chat_id(callback.message.chat.id)
        
        # v2.11.0: Flood wait protection (3 seconds between actions per user)
        import time
        current_time = time.time()
        last_action = self._last_panel_action.get(uid, 0)
        
        if current_time - last_action < 3:
            wait_time = int(3 - (current_time - last_action))
            await callback.answer(
                f"⏳ Зачекайте {wait_time}с перед наступною дією",
                show_alert=True
            )
            return
        
        self._last_panel_action[uid] = current_time
        
        # v2.11.0: Add to queue for processing
        if cid not in self._panel_queues:
            self._panel_queues[cid] = asyncio.Queue()
            self._panel_locks[cid] = asyncio.Lock()
            self._panel_processing[cid] = False
        
        await self._panel_queues[cid].put({
            'type': 'toggle',
            'callback': callback,
            'trigger': trigger,
            'uid': uid
        })
        
        # Start processor if not running
        if not self._panel_processing[cid]:
            asyncio.create_task(self._process_panel_queue(cid))
        
        await callback.answer("⏳ Обробка...")

    async def _send_roles_panel(self, chat_id: int, chat_id_str: str):
        """Відправляє панель реєстрації з кількістю зареєстрованих"""
        triggers = self.chat_repo.get_call_triggers(chat_id_str)
        if not triggers:
            return

        emojis = self.chat_repo.get_all_trigger_emojis(chat_id_str)
        buttons = []
        row = []
        
        for t in sorted(triggers.keys()):
            emoji = emojis.get(t, "🎯")
            # v2.11.0: Show registered count without brackets
            registered_count = len(self.chat_repo.get_trigger_users(chat_id_str, t))
            count_display = f" {registered_count}" if registered_count > 0 else ""
            label = f"{render_emoji(emoji)} {t.capitalize()}{count_display}"
            
            row.append(
                InlineKeyboardButton(text=label, callback_data=f"role_{t}")
            )
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ролі для отримання сповіщень:"
        )

        try:
            await self.bot.send_message(
                chat_id, panel_text, reply_markup=keyboard, parse_mode="HTML"
            )
        except Exception as e:
            self.logger.error(f"Failed to send roles panel: {e}")

    async def _update_roles_panel(self, message: Message, chat_id: str, user_id: str):
        """Оновлює повідомлення панелі ролей з кількістю зареєстрованих"""
        triggers = self.chat_repo.get_call_triggers(chat_id)
        if not triggers:
            return

        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        buttons = []
        row = []
        
        for t in sorted(triggers.keys()):
            emoji = emojis.get(t, "🎯")
            # v2.11.0: Show registered count without brackets
            registered_count = len(self.chat_repo.get_trigger_users(chat_id, t))
            count_display = f" {registered_count}" if registered_count > 0 else ""
            label = f"{render_emoji(emoji)} {t.capitalize()}{count_display}"
            
            row.append(
                InlineKeyboardButton(text=label, callback_data=f"role_{t}")
            )
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ролі для отримання сповіщень:"
        )

        try:
            await message.edit_text(
                panel_text, reply_markup=keyboard, parse_mode="HTML"
            )
        except Exception:
            pass

    async def _process_panel_queue(self, chat_id: str):
        """Обробляє чергу запитів панелі (запобігає флуду)"""
        self._panel_processing[chat_id] = True
        
        try:
            while not self._panel_queues[chat_id].empty():
                request = await self._panel_queues[chat_id].get()
                
                if request['type'] == 'toggle':
                    trigger = request['trigger']
                    uid = request['uid']
                    callback = request['callback']
                    
                    # Acquire lock for this chat
                    async with self._panel_locks.get(chat_id, asyncio.Lock()):
                        users = self.chat_repo.get_trigger_users(chat_id, trigger)
                        
                        if uid in users:
                            self.chat_repo.remove_user_from_trigger(chat_id, trigger, uid)
                            action_text = f"❌ Ви вийшли з !{trigger}"
                        else:
                            self.chat_repo.add_user_to_trigger(chat_id, trigger, uid)
                            action_text = f"✅ Ви підписались на !{trigger}"
                        
                        # Update panel
                        await self._update_roles_panel(callback.message, chat_id, uid)
                        
                        # Show confirmation
                        try:
                            await callback.answer(action_text, show_alert=False)
                        except Exception:
                            pass
                
                # Small delay between queue items
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error processing panel queue: {e}")
        finally:
            self._panel_processing[chat_id] = False

    async def callback_stop_ping(self, callback: CallbackQuery):
        """Обробляє натискання кнопки стоп"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id):
            try:
                await callback.answer(
                    "❌ Тільки адміни можуть зупиняти виклик", show_alert=True
                )
            except TelegramBadRequest:
                pass
            return

        chat_id = get_clean_chat_id(callback.message.chat.id)
        self.chat_repo.set_stop_flag(chat_id, True)

        # Отримуємо налаштування для звіту
        admin_stop_report = self.chat_repo.get_setting(
            chat_id, "admin_stop_report", True
        )
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
                callback.message.text + stop_text, parse_mode="HTML", reply_markup=None
            )
        except Exception:
            pass

    async def cmd_admin_panel(self, message: Message):
        """Відкриває адмін панель для керування тригерами"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        await self._show_admin_panel(message.chat.id, chat_id)
        
        try: await message.delete()
        except: pass

    async def _show_admin_panel(self, chat_id: int, chat_id_str: str):
        """Показує адмін панель для керування тригерами"""
        triggers = self.chat_repo.get_call_triggers(chat_id_str)
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id_str)
        
        keyboard = []
        
        # Header buttons
        keyboard.append([
            InlineKeyboardButton(
                text="➕ Створити тригер",
                callback_data="admin_create"
            )
        ])
        
        # List of existing triggers with manage buttons
        if triggers:
            keyboard.append([
                InlineKeyboardButton(
                    text="📋 <b>Список тригерів:</b>",
                    callback_data="admin_none"
                )
            ])
            
            for t in sorted(triggers.keys()):
                emoji = emojis.get(t, "🎯")
                user_count = len(self.chat_repo.get_trigger_users(chat_id_str, t))
                
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{render_emoji(emoji)} !{t} ({user_count})",
                        callback_data=f"admin_edit_{t}"
                    ),
                    InlineKeyboardButton(
                        text="🗑",
                        callback_data=f"admin_delete_{t}"
                    )
                ])
        
        # Help button
        keyboard.append([
            InlineKeyboardButton(
                text="ℹ️ Довідка",
                callback_data="admin_help"
            )
        ])
        
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        panel_text = (
            "🛠 <b>Адмін Панель Тригерів</b>\n\n"
            "Керуйте тригерами через інтерфейс:\n\n"
            "• ➕ Створити новий тригер\n"
            "• 📋 Переглянути/редагувати існуючі\n"
            "• 🗑 Видалити тригер\n\n"
            "<i>Всі дії зберігаються автоматично</i>"
        )
        
        try:
            await self.bot.send_message(
                chat_id, panel_text, reply_markup=markup, parse_mode="HTML"
            )
        except Exception as e:
            self.logger.error(f"Failed to send admin panel: {e}")

    async def callback_admin_panel(self, callback: CallbackQuery):
        """Обробляє натискання в адмін панелі"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id):
            await callback.answer("❌ Недостатньо прав", show_alert=True)
            return
        
        data = callback.data
        chat_id = get_clean_chat_id(callback.message.chat.id)
        
        if data == "admin_none":
            await callback.answer()
            return
        
        elif data == "admin_help":
            help_text = (
                "ℹ️ <b>Довідка</b>\n\n"
                "<b>Створення:</b>\n"
                "Натисніть ➕ і введіть назву тригера\n\n"
                "<b>Редагування:</b>\n"
                "Натисніть на тригер для зміни емодзі\n\n"
                "<b>Видалення:</b>\n"
                "Натисніть 🗑 поруч з тригером\n\n"
                "<b>Додати користувача:</b>\n"
                "Відповідайте на повідомлення: !adduser назва"
            )
            await callback.answer(help_text, show_alert=True)
            return
        
        elif data == "admin_create":
            # Set state for creating trigger
            from aiogram.fsm.context import FSMContext
            state = FSMContext(
                storage=callback.bot.redis_storage,
                key=f"admin_create_{callback.from_user.id}"
            )
            await state.set_state(AdminStates.waiting_for_trigger_name)
            await callback.message.edit_text(
                "➕ <b>Створення тригера</b>\n\n"
                "Введіть назву тригера (наприклад: <code>game</code>):",
                parse_mode="HTML"
            )
            return
        
        elif data.startswith("admin_delete_"):
            trigger_name = data.replace("admin_delete_", "")
            if self.chat_repo.delete_call_trigger(chat_id, trigger_name):
                await callback.answer(f"✅ Тригер !{trigger_name} видалено")
                await self._show_admin_panel(callback.message.chat.id, chat_id)
                await callback.message.delete()
            else:
                await callback.answer("❌ Помилка видалення", show_alert=True)
            return
        
        elif data.startswith("admin_edit_"):
            trigger_name = data.replace("admin_edit_", "")
            emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name) or "🎯"
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🎯 Змінити емодзі",
                        callback_data=f"admin_setemoji_{trigger_name}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👥 Переглянути учасників",
                        callback_data=f"admin_viewusers_{trigger_name}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="admin_back"
                    )
                ]
            ]
            
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.edit_text(
                f"✏️ <b>Редагування: !{trigger_name}</b>\n\n"
                f"Поточний емодзі: {render_emoji(emoji)}\n"
                f"Учасників: {len(self.chat_repo.get_trigger_users(chat_id, trigger_name))}",
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        
        elif data.startswith("admin_setemoji_"):
            trigger_name = data.replace("admin_setemoji_", "")
            from aiogram.fsm.context import FSMContext
            state = FSMContext(
                storage=callback.bot.redis_storage,
                key=f"admin_setemoji_{callback.from_user.id}"
            )
            await state.set_state(AdminStates.waiting_for_emoji)
            await state.update_data(trigger_name=trigger_name)
            await callback.message.edit_text(
                f"🎯 <b>Зміна емодзі для !{trigger_name}</b>\n\n"
                "Відправте новий емодзі або відповідайте на повідомлення з емодзі:",
                parse_mode="HTML"
            )
            return
        
        elif data.startswith("admin_viewusers_"):
            trigger_name = data.replace("admin_viewusers_", "")
            user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
            chat_data = self.chat_repo.get_chat_data(chat_id)
            all_users = chat_data.get("users", {})
            
            user_list = "\n".join([
                f"• {all_users.get(uid, f'User {uid}')}"
                for uid in user_ids[:20]
            ])
            
            if len(user_ids) > 20:
                user_list += f"\n... та ще {len(user_ids) - 20}"
            
            text = (
                f"👥 <b>Учасники !{trigger_name}:</b>\n\n"
                f"{user_list if user_list else 'Немає учасників'}"
            )
            
            keyboard = [[
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_edit_{trigger_name}")
            ]]
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            return
        
        elif data == "admin_back":
            await self._show_admin_panel(callback.message.chat.id, chat_id)
            await callback.message.delete()
            return
        
        await callback.answer()

# FSM States for Admin Panel
class AdminStates(StatesGroup):
    waiting_for_trigger_name = State()
    waiting_for_emoji = State()

# FSM Handlers for Admin Panel
@router.message(AdminStates.waiting_for_trigger_name)
async def handle_trigger_creation(self, message: Message, state):
    """Обробляє створення тригера через панель"""
    if not await self._is_admin(message.chat.id, message.from_user.id):
        await state.clear()
        return
    
    trigger_name = message.text.strip().lower()
    
    # Validation
    if not trigger_name or len(trigger_name) > 20:
        await message.answer(
            "❌ Назва тригера повинна бути від 1 до 20 символів",
            parse_mode="HTML"
        )
        return
    
    if not trigger_name.replace("_", "").isalnum():
        await message.answer(
            "❌ Назва може містити тільки літери, цифри та підкреслення",
            parse_mode="HTML"
        )
        return
    
    chat_id = get_clean_chat_id(message.chat.id)
    
    # Check if trigger already exists
    if self.chat_repo.get_trigger_users(chat_id, trigger_name) is not None:
        await message.answer(
            f"❌ Тригер <code>!{trigger_name}</code> вже існує",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Create trigger
    if self.chat_repo.create_call_trigger(chat_id, trigger_name):
        await message.answer(
            f"✅ Тригер <code>!{trigger_name}</code> створено!\n\n"
            f"Встановити емодзі: <code>!set_role_emoji {trigger_name} 🎯</code>\n"
            f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь)\n"
            f"Викликати: <code>!{trigger_name}</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Помилка при створенні тригера",
            parse_mode="HTML"
        )
    
    await state.clear()
    
    # Show updated admin panel
    await self._show_admin_panel(message.chat.id, chat_id)
    try: await message.delete()
    except: pass

@router.message(AdminStates.waiting_for_emoji)
async def handle_emoji_input(self, message: Message, state):
    """Обробляє встановлення емодзі для тригера"""
    if not await self._is_admin(message.chat.id, message.from_user.id):
        await state.clear()
        return
    
    # Get trigger name from state
    data = await state.get_data()
    trigger_name = data.get("trigger_name")
    
    if not trigger_name:
        await message.answer("❌ Помилка: тригер не вибрано")
        await state.clear()
        return
    
    # Extract emoji
    custom_id = extract_custom_emoji_id(message)
    emoji = f"tg-emoji:{custom_id}" if custom_id else message.text.strip()
    
    if not emoji:
        await message.answer(
            "❌ Відправте емодзі або відповідайте на повідомлення з емодзі",
            parse_mode="HTML"
        )
        return
    
    chat_id = get_clean_chat_id(message.chat.id)
    
    # Set emoji
    if self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji):
        await message.answer(
            f"✅ Для <code>!{trigger_name}</code> встановлено {render_emoji(emoji)}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Помилка встановлення емодзі")
    
    await state.clear()
    
    # Show updated admin panel
    await self._show_admin_panel(message.chat.id, chat_id)
    try: await message.delete()
    except: pass

# === Custom Triggers Logic ===

    async def cmd_add_custom_trigger(self, message: Message):
        """Додає кастомний текстовий тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addtrigger слово`", parse_mode="Markdown"
            )
            return

        trigger = args[1].strip().split()[0]  # Беремо перше слово
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "text")
        await message.answer(
            f"✅ Додано тригер виклику (текст): `{trigger}`", parse_mode="Markdown"
        )

    async def cmd_add_custom_emoji_trigger(self, message: Message):
        """Додає кастомний емодзі тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addemojitrigger слово`",
                parse_mode="Markdown",
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "emoji")
        await message.answer(
            f"✅ Додано тригер виклику (емодзі): `{trigger}`", parse_mode="Markdown"
        )

    async def cmd_add_custom_active_trigger(self, message: Message):
        """Додає кастомний тригер активних користувачів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addactivetrigger слово`",
                parse_mode="Markdown",
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "active")
        await message.answer(
            f"✅ Додано тригер виклику (активні 24г): `{trigger}`",
            parse_mode="Markdown",
        )

    async def cmd_add_custom_active_week_trigger(self, message: Message):
        """Додає кастомний тригер тижневої активності"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addactiveweektrigger слово`",
                parse_mode="Markdown",
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "active_week")
        await message.answer(
            f"✅ Додано тригер виклику (тижневий актив): `{trigger}`",
            parse_mode="Markdown",
        )

    async def cmd_add_custom_writer_trigger(self, message: Message):
        """Додає кастомний тригер для тих, хто писав"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addwritertrigger слово`",
                parse_mode="Markdown",
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "writers")
        await message.answer(
            f"✅ Додано тригер виклику (хто писав): `{trigger}`", parse_mode="Markdown"
        )

    async def cmd_add_custom_online_trigger(self, message: Message):
        """Додає кастомний тригер для тих, хто онлайн"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер: `!addonlinetrigger слово`",
                parse_mode="Markdown",
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        self.chat_repo.add_custom_ping_trigger(chat_id, trigger, "online")
        await message.answer(
            f"✅ Додано тригер виклику (online): `{trigger}`", parse_mode="Markdown"
        )

    async def cmd_del_custom_trigger(self, message: Message):
        """Видаляє кастомний тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Вкажіть слово-тригер для видалення", parse_mode="Markdown"
            )
            return

        trigger = args[1].strip().split()[0]
        chat_id = get_clean_chat_id(message.chat.id)

        if self.chat_repo.remove_custom_ping_trigger(chat_id, trigger):
            await message.answer(
                f"✅ Тригер `{trigger}` видалено", parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ Тригер `{trigger}` не знайдено", parse_mode="Markdown"
            )

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
            if type_ == "text":
                icon = "📢"
            elif type_ == "emoji":
                icon = "🤪"
            elif type_ == "active":
                icon = "🔥"
            elif type_ == "active_week":
                icon = "📅"
            elif type_ == "writers":
                icon = "✍️"
            elif type_ == "online":
                icon = "🌐"
            else:
                icon = "❓"
            text += f"• <code>{t}</code> ({icon})\n"

        await message.answer(text, parse_mode="HTML")

    async def handle_custom_triggers(self, message: Message):
        """Перевіряє чи повідомлення є кастомним тригером"""
        if not message.text:
            return

        # Get first word, lowercase, strip prefix
        first_word = message.text.split()[0].lower()
        cleaned_trigger = first_word.lstrip("!").lstrip("/")

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
            self.logger.info(
                f"Custom trigger '{cleaned_trigger}' activated by {message.from_user.id}"
            )

            # Extract Call Text (everything after trigger)
            parts = message.text.split(maxsplit=1)
            call_text = (
                parts[1]
                if len(parts) > 1
                else ("📣 Увага!" if found_type == "text" else "📣 Увага!")
            )

            # Execute Ping
            users = self.chat_repo.get_active_users(chat_id)
            if not users:
                return

            try:
                await message.delete()
            except Exception:
                pass

            if found_type == "emoji":
                await self._send_pings(
                    message.chat.id, users, call_text, use_emoji=True, show_names=True
                )
            elif found_type == "active":
                recent = await self._get_recently_active_users(chat_id, hours=24)
                if not recent:
                    sent = await message.answer("ℹ️ Немає активних учасників за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(
                    message.chat.id, recent, call_text, use_emoji=True, show_names=True
                )
            elif found_type == "active_week":
                recent = await self._get_recently_active_users(chat_id, hours=168)
                if not recent:
                    sent = await message.answer(
                        "ℹ️ Немає активних учасників за тиждень."
                    )
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(
                    message.chat.id, recent, call_text, use_emoji=True, show_names=True
                )
            elif found_type == "writers":
                recent = await self._get_filtered_users(
                    chat_id, source="message", hours=24
                )
                if not recent:
                    sent = await message.answer("ℹ️ Немає тих, хто писав за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(
                    message.chat.id, recent, call_text, use_emoji=True, show_names=True
                )
            elif found_type == "online":
                recent = await self._get_filtered_users(
                    chat_id, source="profile", hours=24
                )
                if not recent:
                    sent = await message.answer("ℹ️ Немає онлайн за 24г.")
                    await self.auto_cleanup(sent)
                    return
                await self._send_pings(
                    message.chat.id, recent, call_text, use_emoji=True, show_names=True
                )
            else:
                await self._send_pings(
                    message.chat.id, users, call_text, use_emoji=True, show_names=True
                )

    async def auto_cleanup(self, *messages):
        """Автоматично видаляє повідомлення через певний час"""
        if not messages:
            return

        chat_id = get_clean_chat_id(messages[0].chat.id)
        cleanup_time = self.chat_repo.get_setting(chat_id, "cleanup_time", 60)

        # Якщо час 0 - не видаляємо
        if cleanup_time <= 0:
            return

        await asyncio.sleep(cleanup_time)

        for msg in messages:
            if not msg:
                continue
            try:
                await msg.delete()
            except Exception:
                pass
