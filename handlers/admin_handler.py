"""
Admin handlers - команди для адміністраторів (SRP)
"""

import logging
import asyncio
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from utils.l10n import l10n
from userbot.collector import UserbotCollector
from config import ADMIN_USER_ID, PING_LIMITS, UB_ACCOUNTS
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


class LoginStates(StatesGroup):
    waiting_for_account = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()


class AdminHandler(BaseHandler):
    """
    Обробляє команди адміністраторів
    Single Responsibility: тільки адмін-команди
    """

    def __init__(
        self,
        chat_repo,
        premium_repo,
        bot: Bot,
        userbot: UserbotCollector,
        emoji_service=None,
    ):
        self.bot = bot
        self.userbot = userbot
        self.emoji_service = emoji_service
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)

    def register_handlers(self):
        """Реєструє хендлери адміністраторів"""
        self.router.message(Command("sync"))(self.cmd_sync)
        self.router.message(F.text.regexp(r"^!?збір", flags=0))(self.cmd_sync)

        self.router.message(Command("stats"))(self.cmd_stats)
        self.router.message(F.text.regexp(r"^!?стата", flags=0))(self.cmd_stats)

        self.router.message(Command("fullstats"))(self.cmd_fullstats)
        self.router.message(F.text.regexp(r"^!?фулстата", flags=0))(self.cmd_fullstats)

        self.router.message(Command("admin_settings", "apanel"))(
            self.cmd_admin_settings
        )
        self.router.message(Command("ahelp", "admin_help"))(self.cmd_ahelp)
        self.router.message(Command("admin_add_trigger"))(self.cmd_admin_add_trigger)
        self.router.message(Command("admin_del_trigger"))(self.cmd_admin_del_trigger)
        self.router.message(Command("admin_toggle_userbot"))(
            self.cmd_admin_toggle_userbot
        )

        # Admin management (v1.9.8)
        self.router.message(Command("admin_add"))(self.cmd_admin_add)
        self.router.message(Command("admin_del"))(self.cmd_admin_del)
        self.router.message(Command("admin_list"))(self.cmd_admin_list)

        self.router.message(Command("owner_add"))(self.cmd_owner_add)
        self.router.message(Command("owner_del"))(self.cmd_owner_del)

        self.router.message(Command("mod_add"))(self.cmd_mod_add)
        self.router.message(Command("mod_del"))(self.cmd_mod_del)

        self.router.message(Command("admod_add"))(self.cmd_admod_add)
        self.router.message(Command("admod_del"))(self.cmd_admod_del)

        # Userbot Login Flow (v1.7.0)
        self.router.message(Command("ub_login"))(self.cmd_ub_login)
        self.router.callback_query(F.data.startswith("ub_acc_"))(
            self.process_account_selection
        )
        self.router.message(Command("ub_cancel"))(self.cmd_ub_cancel)
        self.router.message(LoginStates.waiting_for_phone)(self.process_auth_phone)
        self.router.message(LoginStates.waiting_for_code)(self.process_auth_code)
        self.router.message(LoginStates.waiting_for_password)(
            self.process_auth_password
        )

        # Chat-wide unreg and premium (v2.5.0)
        self.router.message(Command("chat_unreg"))(self.cmd_chat_unreg)
        self.router.message(Command("chat_superunreg"))(self.cmd_chat_superunreg)
        self.router.message(Command("chat_regall"))(self.cmd_chat_regall)
        self.router.message(Command("admin_grant_chat_premium"))(
            self.cmd_admin_grant_chat_premium
        )

        # Admin Chats List (v2.7.0)
        self.router.message(Command("admin_chats", "achats"))(self.cmd_admin_chats)
        self.router.callback_query(F.data.startswith("admin_chat_"))(
            self.callback_admin_chat_settings
        )
        self.router.callback_query(F.data.startswith("admin_limit_"))(
            self.callback_admin_toggle_limit
        )
        self.router.callback_query(F.data.startswith("admin_toggle_reg_"))(
            self.callback_admin_toggle_reg
        )

        # Emoji Pack management (v2.10.0)
        self.router.message(Command("admin_emoji_packs"))(self.cmd_admin_emoji_packs)
        self.router.message(Command("admin_register_pack"))(
            self.cmd_admin_register_pack
        )

    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        cid = get_clean_chat_id(chat_id)

        # v2.2.0: Глобальний персонал бота (від модератора і вище) має доступ всюди
        if self.chat_repo.is_bot_moderator(user_id):
            return True

        try:
            member = await self.bot.get_chat_member(cid, user_id)
            is_admin = member.status in ["creator", "administrator"]

            if not is_admin:
                self.logger.warning(
                    f"Користувач {user_id} має статус '{member.status}' у чаті {cid}"
                )
            return is_admin

        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "not enough rights" in error_msg:
                self.logger.debug(f"Бот не є учасником чату {cid}")
                return True

            self.logger.error(f"Помилка перевірки прав: {e}")
            return True

    async def cmd_sync(self, message: Message):
        """Синхронізує учасників чату (Hybrid: Bot API + Userbot)"""
        self.logger.info(
            f"Отримано команду синхронізації від {message.from_user.id} "
            f"у чаті {message.chat.id}"
        )

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        status = await message.answer(
            "🔄 <b>Починаю синхронізацію...</b>", parse_mode="HTML"
        )
        chat_id = get_clean_chat_id(message.chat.id)

        try:
            # ЕТАП 1: Синхронізація Адміністраторів (Bot API)
            # Це працює завжди, навіть без юзербота
            admins = await self.bot.get_chat_administrators(message.chat.id)
            admin_count = 0
            for member in admins:
                if not member.user.is_bot:
                    user_id = str(member.user.id)
                    name = member.user.first_name or "Admin"
                    self.chat_repo.save_user(chat_id, user_id, name, update_unreg=False)
                    admin_count += 1

            self.logger.info(f"Синхронізовано {admin_count} адмінів через Bot API")

            # ЕТАП 2: Повна синхронізація (Userbot)
            is_ub_enabled = self.chat_repo.get_global_setting("use_userbot", True)

            if is_ub_enabled:
                await status.edit_text(
                    f"✅ Адміни ({admin_count}) оновлені.\n🛰 <b>Запускаю юзербота для повного збору...</b>",
                    parse_mode="HTML",
                )

                try:
                    total_count = await self.userbot.sync_participants(message.chat.id)
                    await status.edit_text(
                        f"✅ <b>Синхронізація завершена!</b>\n\n"
                        f"👥 Всього в базі чату: <b>{total_count}</b>\n"
                        f"👑 З них адмінів: {admin_count}\n"
                        f"🛰 Метод: Hybrid (Bot API + Userbot)",
                        parse_mode="HTML",
                    )
                except Exception as ub_err:
                    error_text = str(ub_err).lower()
                    self.logger.error(f"Userbot sync error: {ub_err}")

                    if "no workers running" in error_text or "timeout" in error_text:
                        # Це внутрішні глюки Telegram, а не відсутність адміна
                        await status.edit_text(
                            f"✅ <b>Адмін-склад: OK</b> (+{admin_count})\n\n"
                            f"⚠️ <b>Тимчасова помилка Telegram (500)</b>\n"
                            f"Сервери Telegram зараз перевантажені або нестабільні. Повний збір учасників неможливий у цей момент.\n\n"
                            f"🕒 Спробуйте ще раз через 5-10 хвилин.",
                            parse_mode="HTML",
                        )
                    else:
                        # Ймовірно, справді треба додати юзербота
                        await status.edit_text(
                            f"✅ <b>Синхронізація (Admin Rights): OK</b>\n"
                            f"👥 Знайдено адмінів: {admin_count}\n\n"
                            f"⚠️ <b>Повний збір пропущено</b>\n"
                            f"Для повного збору всіх учасників чату, нам потрібна допомога допоміжного акаунта.\n\n"
                            f"👉 <b>Рішення:</b>\n"
                            f"Додайте в чат: @you_can_try_this\n"
                            f"I повторіть /sync",
                            parse_mode="HTML",
                        )
            else:
                # Get total users in chat
                chat_data = self.chat_repo.get_chat_data(chat_id)
                total_users = len(chat_data.get("users", {}))

                await status.edit_text(
                    f"✅ <b>Синхронізація завершена!</b>\n\n"
                    f"👥 Всього в базі чату: {total_users}\n"
                    f"👑 Оновлено адмінів: {admin_count}\n\n"
                    f"<i>Для повного збору додайте нашого Support Admin: @you_can_try_this</i>",
                    parse_mode="HTML",
                )

        except Exception as e:
            self.logger.error(f"General sync error: {e}")
            await status.edit_text(f"❌ Помилка синхронізації: {e}")

        await self.auto_cleanup(message, status)

    async def cmd_stats(self, message: Message):
        """Показує статистику чату"""
        self.logger.info(f"Отримано команду статистики від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        chat_id = get_clean_chat_id(message.chat.id)
        stats = self.chat_repo.get_stats(chat_id)

        stats_text = (
            f"📈 <b>Статистика чату:</b>\n\n"
            f"👥 Всього в базі: {stats['total']}\n"
            f"✅ Активних (отримують пінги): {stats['active']}\n"
            f"🔕 Тимчасово вимкнено: {stats['temp_unreg']}\n"
            f"🚫 Постійно вимкнено: {stats['super_unreg']}"
        )

        sent = await self._safe_answer(message, stats_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent)
        self.logger.info(f"Відправлено статистику: {stats['total']} осіб")

    async def cmd_fullstats(self, message: Message):
        """Показує детальну статистику чату з іменами unreg юзерів"""
        self.logger.info(f"Отримано команду FULLSTATS від {message.from_user.id}")

        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        chat_id = get_clean_chat_id(message.chat.id)
        chat_data = self.chat_repo.get_chat_data(chat_id)

        # Get users dict
        users = chat_data.get("users", {})
        temp_unreg = chat_data.get("temp_unreg", [])
        super_unreg = chat_data.get("super_unreg", [])

        # Get global unreg
        data = self.chat_repo.storage.load()
        global_temp = data.get("global_unreg", {}).get("temp", [])
        global_super = data.get("global_unreg", {}).get("super", [])

        # Helper to get name
        def get_name(uid):
            uid = str(uid)
            if uid in users:
                u = users[uid]
                if isinstance(u, dict):
                    return u.get("name", uid)
                return u
            return f"ID:{uid}"

        # Build lists
        temp_list = [f"• {get_name(uid)}" for uid in temp_unreg[:15]]
        super_list = [f"• {get_name(uid)}" for uid in super_unreg[:15]]
        global_temp_list = [f"• {get_name(uid)}" for uid in global_temp[:10]]
        global_super_list = [f"• {get_name(uid)}" for uid in global_super[:10]]

        stats_text = f"📊 <b>FULL STATS</b> — чат {chat_id}\n\n"

        stats_text += f"👥 <b>Всього в базі:</b> {len(users)}\n\n"

        stats_text += f"🔕 <b>Temp Unreg ({len(temp_unreg)}):</b>\n"
        stats_text += "\n".join(temp_list) if temp_list else "— немає"
        if len(temp_unreg) > 15:
            stats_text += f"\n... +{len(temp_unreg) - 15} ще"

        stats_text += f"\n\n🚫 <b>Super Unreg ({len(super_unreg)}):</b>\n"
        stats_text += "\n".join(super_list) if super_list else "— немає"
        if len(super_unreg) > 15:
            stats_text += f"\n... +{len(super_unreg) - 15} ще"

        stats_text += f"\n\n🌐 <b>Global Temp ({len(global_temp)}):</b>\n"
        stats_text += "\n".join(global_temp_list) if global_temp_list else "— немає"

        stats_text += f"\n\n🌐 <b>Global Super ({len(global_super)}):</b>\n"
        stats_text += "\n".join(global_super_list) if global_super_list else "— немає"

        sent = await self._safe_answer(message, stats_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent, custom_delay=60)

    async def cmd_admin_settings(self, message: Message):
        """Встановлює глобальні налаштування (адміни бота)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        args = message.text.split()
        if len(args) < 3:
            current_delay = self.chat_repo.get_global_setting(
                "ping_delay", PING_LIMITS["default_delay"]
            )
            use_ub = self.chat_repo.get_global_setting("use_userbot", True)
            quote_mode = self.chat_repo.get_global_setting(
                "unreg_quote_mode", "premium"
            )

            text = (
                "🖥 <b>ГЛОБАЛЬНА ПАНЕЛЬ КЕРУВАННЯ</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛰 <b>Статус Юзербота:</b> {'✅ ПРАЦЮЄ' if use_ub else '❌ ВИМКНЕНО'}\n"
                f"⚡️ <b>Затримка (Global):</b> <code>{current_delay}s</code>\n"
                f"💬 <b>Режим цитат анрегу:</b> <code>{quote_mode}</code> (all/premium)\n\n"
                "📝 <b>Швидкі команди:</b>\n"
                "• <code>/apanel set_delay 0.5</code>\n"
                "• <code>/apanel set_quote_mode all</code> — Всім дозволити цитати\n"
                "• <code>/admin_toggle_userbot</code>\n"
                "• <code>/ub_login</code> — Вхід в акаунт\n"
                "• <code>/ahelp</code> — Всі команди"
            )
            await self._safe_answer(message, text, parse_mode="HTML")
            return

        action = args[1]
        value = args[2]

        if action == "set_delay":
            try:
                delay = float(value)
                if delay < PING_LIMITS["min_delay"]:
                    delay = PING_LIMITS["min_delay"]
                if delay > PING_LIMITS["max_delay"]:
                    delay = PING_LIMITS["max_delay"]

                self.chat_repo.set_global_setting("ping_delay", delay)
                await self._safe_answer(
                    message,
                    f"✅ <b>Global Delay встановлено:</b> {delay}s",
                    parse_mode="HTML",
                )
            except ValueError:
                await self._safe_answer(
                    message, "❌ Введіть коректне число (наприклад: 0.5)"
                )

        elif action == "set_quote_mode":
            mode = value.lower()
            if mode in ["all", "premium"]:
                self.chat_repo.set_global_setting("unreg_quote_mode", mode)
                await self._safe_answer(
                    message, f"✅ <b>Режим цитат анрегу:</b> {mode}", parse_mode="HTML"
                )
            else:
                await self._safe_answer(message, "❌ Доступні режими: all, premium")

    async def cmd_ahelp(self, message: Message):
        """Швидка допомога для персоналу бота (Staff Help)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        is_super = message.from_user.id == ADMIN_USER_ID
        is_owner = self.chat_repo.is_owner(message.from_user.id)

        help_text = (
            "🔐 <b>BOT STAFF HELP PANEL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍💻 <b>Для Адмінів:</b>\n"
            "• /admin_list — Список усього стаффу\n"
            "• /admin_help — Керування Premium та Stars\n"
            "• /admin_add_trigger [word] [text|emoji] — Глобальні тригери\n"
            "• /admin_del_trigger [word]\n\n"
            "👑 <b>Для Власників:</b>\n"
            "• /apanel — Глобальні налаштування бота\n"
            "• /admin_toggle_userbot — Швидке перемикання ЮБ\n"
            "• /ub_login — Авторизація Юзербота\n"
            "• /sync — Примусова синхронізація\n"
            "• /mod_add [id] — Додати модератора\n"
            "• /mod_del [id] — Видалити модератора\n"
        )

        if is_super:
            help_text += (
                "\n⭐️ <b>SuperOwner Only:</b>\n"
                "• /owner_add [id] — Додати співвласника\n"
                "• /owner_del [id] — Видалити власника\n"
                "• /admin_add [id] — Додати адміна бота\n"
                "• /admin_del [id] — Видалити адміна бота\n"
            )

        await self._safe_answer(message, help_text, parse_mode="HTML")

    async def cmd_admin_add_trigger(self, message: Message):
        """Додає глобальний тригер (Bot Admins)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_add_trigger [word] [text|emoji]")
            return

        trigger = args[1].lower()
        type_ = args[2].lower() if len(args) > 2 else "text"
        allowed_types = ["text", "emoji", "active", "active_week", "writers", "online"]
        if type_ not in allowed_types:
            type_ = "text"

        self.chat_repo.add_global_ping_trigger(trigger, type_)
        await message.answer(
            f"✅ Global Trigger '{trigger}' added as {type_}\nAllowed types: {', '.join(allowed_types)}"
        )

    async def cmd_admin_del_trigger(self, message: Message):
        """Видаляє глобальний тригер (Bot Admins)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_del_trigger [word]")
            return

        trigger = args[1].lower()
        if self.chat_repo.remove_global_ping_trigger(trigger):
            await message.answer(f"✅ Global Trigger '{trigger}' removed")
        else:
            await message.answer(f"❌ Global Trigger '{trigger}' not found")

    async def cmd_admin_toggle_userbot(self, message: Message):
        """Перемикає використання юзербота (Global)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        current = self.chat_repo.get_global_setting("use_userbot", True)
        new_state = not current

        self.chat_repo.set_global_setting("use_userbot", new_state)

        try:
            if new_state:
                await self.userbot.start()
                status = "УВІМКНЕНО ✅ (З'єднання встановлено)"
            else:
                await self.userbot.stop()
                status = "ВИМКНЕНО ❌ (Сесію закрито, акаунт вільний)"
        except Exception as e:
            self.logger.error(f"Error toggling userbot: {e}")
            status = f"{'УВІМКНЕНО' if new_state else 'ВИМКНЕНО'} (Але виникла помилка зв'язку: {e})"

        await self._safe_answer(
            message,
            f"🤖 <b>Використання юзербота:</b> {status}\n\n"
            f"Тепер ви можете використовувати цей акаунт в іншому місці, якщо він вимкнений.",
            parse_mode="HTML",
        )

    # === Userbot Login Flow Handlers ===

    async def cmd_ub_login(self, message: Message, state: FSMContext):
        """Починає процес авторизації юзербота (Bot Admins)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        await state.set_state(LoginStates.waiting_for_account)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Акаунт 2 (Старий)", callback_data="ub_acc_account2"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Акаунт 3 (Новий)", callback_data="ub_acc_account3"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Скасувати", callback_data="ub_acc_cancel"
                    )
                ],
            ]
        )

        await self._safe_answer(
            message,
            "🛰 <b>ВИБІР АКАУНТА ЮЗЕРБОТА</b>\n\n"
            "Оберіть акаунт, який хочете авторизувати. Кожен акаунт має свій API ID та файл сесії.\n\n"
            "<i>Акаунт 2 — той, що мав проблеми з Email (можна спробувати пізніше).</i>\n"
            "<i>Акаунт 3 — новий чистий акаунт.</i>",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def process_account_selection(
        self, callback: CallbackQuery, state: FSMContext
    ):
        """Обробляє вибір акаунта"""
        if callback.from_user.id != ADMIN_USER_ID:
            return

        account_id = callback.data.replace("ub_acc_", "")

        if account_id == "cancel":
            await state.clear()
            await callback.message.edit_text("❌ Авторизацію скасовано.")
            return

        acc_config = UB_ACCOUNTS.get(account_id)
        if not acc_config:
            await callback.answer("❌ Помилка конфігурації акаунта")
            return

        if not acc_config.get("api_id") or not acc_config.get("api_hash"):
            self.logger.error(f"Конфігурація для {account_id} неповна: {acc_config}")
            await callback.message.edit_text(
                f"❌ <b>Помилка конфігурації {account_id}!</b>\n\n"
                "Перевірте файл <code>.env</code> на сервері. Поля API_ID або API_HASH порожні.",
                parse_mode="HTML",
            )
            return

        # Зберігаємо обраний акаунт у стані
        await state.update_data(acc_id=account_id, acc_config=acc_config)

        # Перемикаємо клієнт на льоту!
        await callback.message.edit_text(
            f"⏳ Перемикаюся на <b>{account_id}</b>...\n(API: {acc_config['api_id']})",
            parse_mode="HTML",
        )
        try:
            success = await self.userbot.switch_account(
                api_id=acc_config["api_id"],
                api_hash=acc_config["api_hash"],
                session_name=acc_config["session"],
            )

            if success:
                # v2.6.5: Якщо сесія завантажена і клієнт авторизований - фініш!
                self.chat_repo.set_global_setting(
                    "active_session_name", acc_config["session"]
                )
                await callback.message.edit_text(
                    f"✅ <b>Акаунт {account_id} вже авторизований!</b>\n"
                    f"Юзербот успішно підключився за допомогою збереженої сесії.\n"
                    f"Вводити номер телефону та код не потрібно. 🚀",
                    parse_mode="HTML",
                )
                await state.clear()
                return

        except Exception as e:
            self.logger.error(f"Failed to switch account: {e}")
            await callback.message.edit_text(
                f"❌ <b>Помилка ініціалізації:</b>\n<code>{e}</code>", parse_mode="HTML"
            )
            await state.clear()
            return

        # Якщо сесії немає - просимо номер телефону
        await state.set_state(LoginStates.waiting_for_phone)
        await callback.message.edit_text(
            f"🛰 <b>АВТОРИЗАЦІЯ: {account_id.upper()}</b>\n\n"
            "Сесію не знайдено. Будь ласка, введіть телефон для входу:\n"
            "Приклад: <code>+380501112233</code>\n\n"
            "<i>Щоб скасувати, напишіть /ub_cancel</i>",
            parse_mode="HTML",
        )
        await state.update_data(chosen_acc=account_id)

    async def cmd_ub_cancel(self, message: Message, state: FSMContext):
        """Скасовує авторизацію"""
        if message.from_user.id != ADMIN_USER_ID:
            return

        await state.clear()
        await self._safe_answer(message, "❌ Авторизацію скасовано.")

    async def process_auth_phone(self, message: Message, state: FSMContext):
        """Обробляє номер телефону"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        phone = message.text.strip().replace(" ", "")
        self.logger.info(f"Спроба авторизації юзербота для номера: {phone}")

        status_msg = await self._safe_answer(
            message, "⏳ <b>Зв'язуюсь з Telegram...</b>", parse_mode="HTML"
        )

        try:
            sent_code = await self.userbot.request_phone_code(phone)
            await state.update_data(
                phone=phone, phone_code_hash=sent_code.phone_code_hash
            )
            await state.set_state(LoginStates.waiting_for_code)

            await status_msg.edit_text(
                f"✅ <b>Код відправлено на {phone}!</b>\n\n"
                "Перевірте ваші <b>повідомлення в Telegram</b> (код прийде від сервісного акаунту).\n\n"
                "Введіть отриманий код нижче:",
                parse_mode="HTML",
            )
            self.logger.info(f"Код успішно запитано для {phone}")
        except Exception as e:
            self.logger.error(f"Помилка при запиті коду: {e}")
            error_text = str(e)

            if "FLOOD_WAIT" in error_text:
                import re

                seconds = re.search(r"(\d+)", error_text)
                wait_time = seconds.group(1) if seconds else "кілька"
                msg = f"⏳ <b>Забагато спроб!</b>\n\nTelegram обмежив запити для цього номера. Будь ласка, зачекайте <b>{wait_time}</b> сек. перед наступною спробою."
            elif "EMAIL_INSTALL_MISSING" in error_text:
                msg = (
                    "⚠️ <b>Telegram вимагає підтвердження через Email.</b>\n\n"
                    "Це стається через занадто часті спроби входу або нові правила безпеки.\n\n"
                    "<b>Що зробити:</b>\n"
                    "1. Зачекайте 15-30 хвилин (обов'язково!).\n"
                    "2. Переконайтеся, що у вашому Telegram (Приватність) додана пошта.\n"
                    "3. Спробуйте пізніше командою /ub_login."
                )
            elif "PHONE_NUMBER_INVALID" in error_text:
                msg = "❌ <b>Невірний формат номера!</b>\n\nВведіть номер у міжнародному форматі, наприклад: <code>+380501112233</code>"
            else:
                msg = f"❌ <b>Помилка подорожі до Telegram:</b>\n<code>{error_text}</code>\n\nСпробуйте пізніше або зверніться до підтримки."

            await status_msg.edit_text(msg, parse_mode="HTML")
            await state.clear()

    async def process_auth_code(self, message: Message, state: FSMContext):
        """Обробляє код підтвердження"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        code = message.text.strip().replace(" ", "")
        data = await state.get_data()
        self.logger.info(f"Отримано код від адміна для {data.get('phone')}")

        status_msg = await self._safe_answer(
            message, "⏳ <b>Перевіряю код...</b>", parse_mode="HTML"
        )

        try:
            result = await self.userbot.sign_in_with_code(
                data["phone"], code, data["phone_code_hash"]
            )

            if result["status"] == "password_needed":
                await state.set_state(LoginStates.waiting_for_password)
                await status_msg.edit_text(
                    "🔐 <b>2FA активовано!</b>\n\n"
                    "Будь ласка, введіть ваш хмарний пароль (Cloud Password):",
                    parse_mode="HTML",
                )
            else:
                # Авторизація успішна без 2FA
                self.chat_repo.set_global_setting(
                    "active_session_name", self.userbot.account_name
                )
                await state.clear()
                await status_msg.edit_text(
                    "🎉 <b>Успіх! Юзербот авторизований.</b>", parse_mode="HTML"
                )
                await self.userbot.start()  # Перезавантажуємо клієнт

        except Exception as e:
            self.logger.error(f"Error signing in: {e}")
            error_text = str(e)

            if "PHONE_CODE_EXPIRED" in error_text:
                msg = "❌ <b>Термін дії коду вичерпано!</b>\nБудь ласка, почніть вхід заново: /ub_login"
            elif "PHONE_CODE_INVALID" in error_text:
                msg = "❌ <b>Невірний код!</b>\nВи ввели неправильні цифри. Спробуйте ще раз або почніть заново."
            elif "FLOOD_WAIT" in error_text:
                msg = "⏳ <b>Забагато спроб вводу коду!</b>\nTelegram заблокував вас на деякий час. Спробуйте через 15-30 хв."
            else:
                msg = f"❌ <b>Помилка при вході:</b>\n<code>{error_text}</code>\n\nСпробуйте /ub_login знову."

            await status_msg.edit_text(msg, parse_mode="HTML")
            await state.clear()

    async def process_auth_password(self, message: Message, state: FSMContext):
        """Обробляє 2FA пароль"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        password = message.text.strip()

        try:
            await self.userbot.sign_in_with_password(password)
            # Авторизація успішна
            self.chat_repo.set_global_setting(
                "active_session_name", self.userbot.account_name
            )
            await state.clear()
            await message.answer(
                f"✅ <b>Вхід успішний!</b>\nЮзербот активований для акаунта: <code>{self.userbot.account_name}</code>",
                parse_mode="HTML",
            )
            await self.userbot.start()  # Перезавантажуємо клієнт
            # Assuming user_id is available in message.from_user.id and self.user_states is a dict
            # If self.user_states is not used here, this line might need adjustment or removal based on context.
            # For now, keeping it as provided in the snippet.
            user_id = message.from_user.id
            # self.user_states.pop(user_id, None) # This line was commented out or removed in the original snippet, keeping it consistent.

        except Exception as e:
            self.logger.error(f"Error signing in with password: {e}")
            await self._safe_answer(
                message,
                f"❌ Невірний пароль або інша помилка: {e}\nСпробуйте знову: /ub_login",
            )
            await state.clear()

    # === Admin Management Commands (Owner Only) ===

    async def cmd_admin_add(self, message: Message):
        """Додає нового адміна бота (Власники+)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return

        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_add [user_id]")
            return

        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_admin(target_id)
            await message.answer(
                f"✅ Користувача <code>{target_id}</code> додано до адмінів бота.",
                parse_mode="HTML",
            )
        except ValueError:
            await message.answer("❌ Введіть коректний User ID (число).")

    async def cmd_admin_del(self, message: Message):
        """Видаляє адміна бота (Власники+)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return

        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_del [user_id]")
            return

        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_admin(target_id):
                await message.answer(
                    f"✅ Користувача <code>{target_id}</code> видалено з адмінів бота.",
                    parse_mode="HTML",
                )
            else:
                await message.answer("❌ Користувача не знайдено в списку адмінів.")
        except ValueError:
            await message.answer("❌ Введіть коректний User ID (число).")

    async def cmd_admin_list(self, message: Message):
        """Показує список усього стаффу бота"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return

        owners = self.chat_repo.get_bot_owners()
        admins = self.chat_repo.get_bot_admins()
        mods = self.chat_repo.get_bot_moderators()
        ad_mods = self.chat_repo.get_ad_moderators()
        super_owner = ADMIN_USER_ID

        text = "Staff List:\n\n"
        text += f"⭐️ <b>SuperOwner:</b> <code>{super_owner}</code>\n"

        if owners:
            text += "👑 <b>Власники (Owners):</b>\n"
            for o in owners:
                text += f"• <code>{o}</code>\n"
            text += "\n"

        if admins:
            text += "👨‍💻 <b>Адміни:</b>\n"
            for a in admins:
                text += f"• <code>{a}</code>\n"
            text += "\n"

        if mods:
            text += "🛡 <b>Модератори:</b>\n"
            for m in mods:
                text += f"• <code>{m}</code>\n"
            text += "\n"

        if ad_mods:
            text += "📢 <b>Модератори реклами:</b>\n"
            for am in ad_mods:
                text += f"• <code>{am}</code>\n"
            text += "\n"

        await message.answer(text, parse_mode="HTML")

    async def cmd_owner_add(self, message: Message):
        """Додає додаткового власника (тільки SuperOwner)"""
        if message.from_user.id != ADMIN_USER_ID:
            return

        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /owner_add [user_id]")

        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_owner(target_id)
            await message.answer(
                f"✅ Користувача <code>{target_id}</code> додано як <b>Власника</b>.",
                parse_mode="HTML",
            )
        except:
            await message.answer("❌ Помилка")

    async def cmd_owner_del(self, message: Message):
        """Видаляє власника (тільки SuperOwner)"""
        if message.from_user.id != ADMIN_USER_ID:
            return

        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /owner_del [user_id]")

        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_owner(target_id):
                await message.answer(
                    f"✅ Користувача <code>{target_id}</code> видалено зі списку власників.",
                    parse_mode="HTML",
                )
            else:
                await message.answer("❌ Власника не знайдено.")
        except:
            await message.answer("❌ Помилка")

    async def cmd_mod_add(self, message: Message):
        """Додає модератора (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /mod_add [id]")
        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_moderator(target_id)
            await message.answer(
                f"✅ Користувача <code>{target_id}</code> додано до модераторів.",
                parse_mode="HTML",
            )
        except:
            await message.answer("❌ Error")

    async def cmd_mod_del(self, message: Message):
        """Видаляє модератора (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /mod_del [id]")
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_moderator(target_id):
                await message.answer("✅ Видалено.")
            else:
                await message.answer("❌ Не знайдено.")
        except:
            await message.answer("❌ Error")

    async def cmd_admod_add(self, message: Message):
        """Додає адмода (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /admod_add [id]")
        try:
            target_id = int(args[1])
            self.chat_repo.add_ad_moderator(target_id)
            await message.answer(
                f"✅ Додано до реклами: <code>{target_id}</code>", parse_mode="HTML"
            )
        except:
            await message.answer("❌ Error")

    async def cmd_admod_del(self, message: Message):
        """Видаляє адмода (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("Usage: /admod_del [id]")
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_ad_moderator(target_id):
                await message.answer("✅ Видалено з реклами.")
            else:
                await message.answer("❌ Не знайдено.")
        except:
            await message.answer("❌ Error")

    # === Chat-Wide Features (v2.5.0) ===

    async def cmd_chat_unreg(self, message: Message):
        """Тимчасово анрегає всіх користувачів в чаті (Owner only)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return await message.answer("❌ Тільки для власників бота.")

        args = message.text.split()
        target_chat_id = (
            args[1] if len(args) > 1 else get_clean_chat_id(message.chat.id)
        )

        chat_data = self.chat_repo.get_chat_data(target_chat_id)
        users = chat_data.get("users", {})

        if not users:
            return await message.answer(
                f"ℹ️ В базі немає користувачів чату <code>{target_chat_id}</code>.",
                parse_mode="HTML",
            )

        count = 0
        for user_id in users.keys():
            if self.chat_repo.add_to_temp_unreg(target_chat_id, user_id):
                count += 1

        await message.answer(
            f"✅ <b>Chat Temp Unreg Complete</b>\n\n"
            f"💬 Чат: <code>{target_chat_id}</code>\n"
            f"🔕 Анрегнуто: {count} користувачів\n"
            f"<i>Всі тепер в temp_unreg (автовідновлення при активності).</i>",
            parse_mode="HTML",
        )

    async def cmd_chat_superunreg(self, message: Message):
        """Постійно анрегає всіх користувачів в чаті (Owner only)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return await message.answer("❌ Тільки для власників бота.")

        args = message.text.split()
        target_chat_id = (
            args[1] if len(args) > 1 else get_clean_chat_id(message.chat.id)
        )

        chat_data = self.chat_repo.get_chat_data(target_chat_id)
        users = chat_data.get("users", {})

        if not users:
            return await message.answer(
                f"ℹ️ В базі немає користувачів чату <code>{target_chat_id}</code>.",
                parse_mode="HTML",
            )

        count = 0
        for user_id in users.keys():
            if self.chat_repo.add_to_super_unreg(target_chat_id, user_id):
                count += 1

        await message.answer(
            f"✅ <b>Chat Super Unreg Complete</b>\n\n"
            f"💬 Чат: <code>{target_chat_id}</code>\n"
            f"🚫 Анрегнуто: {count} користувачів\n"
            f"<i>Всі тепер в super_unreg (постійний захист).</i>",
            parse_mode="HTML",
        )

    async def cmd_chat_regall(self, message: Message):
        """Прописує всіх учасників чату назад у базу (Owner only)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return await message.answer("❌ Тільки для власників бота.")

        args = message.text.split()
        target_chat_id = (
            args[1] if len(args) > 1 else get_clean_chat_id(message.chat.id)
        )

        count = self.chat_repo.clear_all_unreg_in_chat(target_chat_id)

        await message.answer(
            f"✅ <b>Chat Absolute Reg Complete</b>\n\n"
            f"💬 Чат: <code>{target_chat_id}</code>\n"
            f"👤 Реєстровано: {count} користувачів\n"
            f"<i>Всі списки анрегу для цього чату очищено.</i>",
            parse_mode="HTML",
        )

    async def cmd_admin_chats(self, message: Message):
        """Показує список усіх чатів у базі (Owner only)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return

        chats = self.chat_repo.get_all_chats()
        if not chats:
            return await message.answer("ℹ️ База чатів порожня.")

        keyboard = []
        for cid in chats[:20]:  # Показати перші 20
            # v2.7.5: Show registration status
            reg_disabled = self.chat_repo.get_setting(
                cid, "registration_disabled", False
            )
            reg_icon = "🔴" if reg_disabled else "🟢"

            # Спробуємо отримати назву чату через Bot API
            try:
                chat_info = await self.bot.get_chat(cid)
                title = chat_info.title or f"Chat {cid}"
            except:
                title = f"Chat {cid}"

            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"{reg_icon} {title}",
                        callback_data=f"admin_chat_view_{cid}",
                    )
                ]
            )

        # Pagination markers if needed (simplified for now)
        if len(chats) > 20:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"... і ще {len(chats) - 20} чатів", callback_data="none"
                    )
                ]
            )

        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            "🏘 <b>Список чатів у базі:</b>", reply_markup=markup, parse_mode="HTML"
        )

    async def callback_admin_chat_settings(self, callback: CallbackQuery):
        """Керування конкретним чатом в адмінці"""
        if not self.chat_repo.is_owner(callback.from_user.id):
            return await callback.answer("❌ Недостатньо прав", show_alert=True)

        # admin_chat_view_-100123
        cid = callback.data.replace("admin_chat_view_", "")

        stats = self.chat_repo.get_stats(cid)
        unreg_limit = self.chat_repo.get_command_limit(cid, "unreg")
        super_limit = self.chat_repo.get_command_limit(cid, "superunreg")
        reg_disabled = self.chat_repo.get_setting(cid, "registration_disabled", False)

        text = (
            f"🏘 <b>Керування чатом:</b> <code>{cid}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Користувачів:</b> {stats['total']}\n"
            f"✅ <b>Активні:</b> {stats['active']}\n"
            f"🚫 <b>Unreg:</b> {stats['temp_unreg']} | <b>Super:</b> {stats['super_unreg']}\n\n"
            f"📝 <b>Обмеження команд:</b>\n"
            f"• <code>unreg</code>: {'🔴 ВИМКНЕНО' if unreg_limit else '🟢 ДОЗВОЛЕНО'}\n"
            f"• <code>superunreg</code>: {'🔴 ВИМКНЕНО' if super_limit else '🟢 ДОЗВОЛЕНО'}\n"
            f"• <b>Авто-реєстрація:</b> {'🔴 ВИМКНЕНО' if reg_disabled else '🟢 УВІМКНЕНО'}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{'🟢 Дозволити' if unreg_limit else '🔴 Блокувати'} unreg",
                        callback_data=f"admin_limit_unreg_{cid}",
                    ),
                    InlineKeyboardButton(
                        text=f"{'🟢 Дозволити' if super_limit else '🔴 Блокувати'} superunreg",
                        callback_data=f"admin_limit_superunreg_{cid}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'🟢 Увімкнути активність' if reg_disabled else '🔴 Вимкнути активність'}",
                        callback_data=f"admin_toggle_reg_{cid}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔕 Анрег усіх (Temp)",
                        callback_data=f"admin_chat_action_unreg_{cid}",
                    ),
                    InlineKeyboardButton(
                        text="👤 Рег усіх (Back)",
                        callback_data=f"admin_chat_action_reg_{cid}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ До списку", callback_data="admin_chats_back"
                    ),
                    InlineKeyboardButton(
                        text="❌ Закрити", callback_data="delete_message"
                    ),
                ],
            ]
        )

        # Перевіряємо чи це дія чи просто перегляд
        if "action" in callback.data:
            action = callback.data.split("_")[3]
            if action == "unreg":
                # Викликаємо існуючу логіку
                users = self.chat_repo.get_chat_data(cid).get("users", {})
                for uid in users:
                    self.chat_repo.add_to_temp_unreg(cid, uid)
                await callback.answer("✅ Всіх анрегнуто (тимчасово)")
            elif action == "reg":
                self.chat_repo.clear_all_unreg_in_chat(cid)
                await callback.answer("✅ Всіх зареєстровано")

            # Оновлюємо статистику після дії
            stats = self.chat_repo.get_stats(cid)
            # Перебудовуємо текст і кнопки (код нижче в edit_text виконає це)

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    async def callback_admin_toggle_reg(self, callback: CallbackQuery):
        """Перемикає авто-реєстрацію (активність) в чаті"""
        if not self.chat_repo.is_owner(callback.from_user.id):
            return

        # admin_toggle_reg_-100123
        cid = callback.data.replace("admin_toggle_reg_", "")

        current = self.chat_repo.get_setting(cid, "registration_disabled", False)
        self.chat_repo.set_setting(cid, "registration_disabled", not current)

        await callback.answer(
            f"✅ {'Авто-реєстрацію увімкнено' if current else 'Авто-реєстрацію вимкнено'}"
        )
        await self.callback_admin_chat_settings(callback)

    async def callback_admin_toggle_limit(self, callback: CallbackQuery):
        """Перемикає блокування команд у чаті"""
        if not self.chat_repo.is_owner(callback.from_user.id):
            return

        # admin_limit_unreg_-100123
        _, _, cmd, cid = callback.data.split("_", 3)

        current = self.chat_repo.get_command_limit(cid, cmd)
        self.chat_repo.set_command_limit(cid, cmd, not current)

        await callback.answer(
            f"✅ {'Блокування знято' if current else 'Команду заблоковано'}"
        )
        await self.callback_admin_chat_settings(callback)

    async def cmd_admin_grant_chat_premium(self, message: Message):
        """Видає Chat Premium безкоштовно (Owner only)"""
        if not self.chat_repo.is_owner(message.from_user.id):
            return await message.answer("❌ Тільки для власників бота.")

        args = message.text.split()
        if len(args) < 3:
            return await message.answer("Usage: /admin_grant_chat_premium chat_id days")

        try:
            target_chat_id = args[1]
            days = int(args[2])

            # Import ChatPremiumRepository if not available
            from core.database import ChatPremiumRepository
            from core.database import JSONDatabase
            from config import DB_FILE

            db = JSONDatabase(DB_FILE)
            chat_premium_repo = ChatPremiumRepository(db)
            chat_premium_repo.grant_chat_premium(target_chat_id, days)

            await message.answer(
                f"✅ <b>Chat Premium видано!</b>\n\n"
                f"💬 Чат: <code>{target_chat_id}</code>\n"
                f"📅 Термін: {days} днів\n\n"
                f"<i>Тепер всі в цьому чаті можуть /superunreg</i>",
                parse_mode="HTML",
            )
        except Exception as e:
            await message.answer(f"❌ Помилка: {e}")

    async def cmd_admin_emoji_packs(self, message: Message):
        """Перегляд статусів емодзі-паків бота"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        packs = self.chat_repo.emoji_packs.get_packs()
        if not packs:
            await message.answer(l10n.format_value("emoji_pack.admin.no_packs"))
            return

        text = l10n.format_value("emoji_pack.admin.packs_title") + "\n\n"
        for i, pack in enumerate(packs, 1):
            text += (
                f"{i}. <b>{pack['title']}</b>\n"
                f"   🏷 Назва: <code>{pack['name']}</code>\n"
                f"   📊 Емодзі: {pack.get('count', 0)}/200\n"
                f"   🔗 Посилання: t.me/addemoji/{pack['name']}\n\n"
            )

        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

    async def cmd_admin_register_pack(self, message: Message):
        """Вручну реєструє емодзі-пак у базі"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return

        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            await message.answer(
                l10n.format_value("emoji_pack.admin.register_usage"),
                parse_mode="HTML",
            )
            return

        name = parts[1]
        title = parts[2]
        count = int(parts[3]) if len(parts) > 3 else 0

        self.chat_repo.emoji_packs.register_pack(name, title, count)
        await message.answer(
            l10n.format_value("emoji_pack.register_success", name=name),
            parse_mode="HTML",
        )
