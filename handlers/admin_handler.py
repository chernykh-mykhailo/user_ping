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
    
    def __init__(self, chat_repo, premium_repo, bot: Bot, userbot: UserbotCollector):
        self.bot = bot
        self.userbot = userbot
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери адміністраторів"""
        self.router.message(Command("sync"))(self.cmd_sync)
        self.router.message(F.text.regexp(r'^!?збір', flags=0))(self.cmd_sync)
        
        self.router.message(Command("stats"))(self.cmd_stats)
        self.router.message(F.text.regexp(r'^!?стата', flags=0))(self.cmd_stats)
        
        
        self.router.message(Command("admin_settings", "apanel"))(self.cmd_admin_settings)
        self.router.message(Command("ahelp"))(self.cmd_ahelp)
        self.router.message(Command("admin_add_trigger"))(self.cmd_admin_add_trigger)
        self.router.message(Command("admin_del_trigger"))(self.cmd_admin_del_trigger)
        self.router.message(Command("admin_toggle_userbot"))(self.cmd_admin_toggle_userbot)
        
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
        self.router.callback_query(F.data.startswith("ub_acc_"))(self.process_account_selection)
        self.router.message(Command("ub_cancel"))(self.cmd_ub_cancel)
        self.router.message(LoginStates.waiting_for_phone)(self.process_auth_phone)
        self.router.message(LoginStates.waiting_for_code)(self.process_auth_code)
        self.router.message(LoginStates.waiting_for_password)(self.process_auth_password)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            is_admin = member.status in ['creator', 'administrator']
            
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
        
        status = await message.answer("🔄 <b>Починаю синхронізацію...</b>", parse_mode="HTML")
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
                await status.edit_text(f"✅ Адміни ({admin_count}) оновлені.\n🛰 <b>Запускаю юзербота для повного збору...</b>", parse_mode="HTML")
                
                try:
                    total_count = await self.userbot.sync_participants(message.chat.id)
                    await status.edit_text(
                        f"✅ <b>Синхронізація завершена!</b>\n\n"
                        f"👥 Всього в базі чату: <b>{total_count}</b>\n"
                        f"👑 З них адмінів: {admin_count}\n"
                        f"🛰 Метод: Hybrid (Bot API + Userbot)",
                        parse_mode="HTML"
                    )
                except Exception as ub_err:
                    self.logger.error(f"Userbot sync error: {ub_err}")
                    await status.edit_text(
                        f"⚠️ <b>Часткова синхронізація</b>\n\n"
                        f"👑 Адміни оновлені: {admin_count}\n"
                        f"❌ Юзербот не зміг зібрати всіх: <code>{str(ub_err)[:50]}...</code>\n\n"
                        "<i>Спробуйте !APANEL щоб перевірити статус юзербота.</i>",
                        parse_mode="HTML"
                    )
            else:
                await status.edit_text(
                    f"✅ <b>Синхронізація завершена!</b>\n\n"
                    f"👑 Оновлено адмінів: {admin_count}\n"
                    f"ℹ️ Повний збір пропущено (Юзербот вимкнено).\n\n"
                    f"<i>Щоб зібрати всіх учасників, увімкніть юзербота в /apanel</i>",
                    parse_mode="HTML"
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

    async def cmd_admin_settings(self, message: Message):
        """Встановлює глобальні налаштування (адміни бота)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
            
        args = message.text.split()
        if len(args) < 3:
            current_delay = self.chat_repo.get_global_setting("ping_delay", PING_LIMITS["default_delay"])
            use_ub = self.chat_repo.get_global_setting("use_userbot", True)
            
            text = (
                "🖥 <b>ГЛОБАЛЬНА ПАНЕЛЬ КЕРУВАННЯ</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛰 <b>Статус Юзербота:</b> {'✅ ПРАЦЮЄ' if use_ub else '❌ ВИМКНЕНО'}\n"
                f"⚡️ <b>Затримка (Global):</b> <code>{current_delay}s</code>\n\n"
                "📝 <b>Швидкі команди:</b>\n"
                "• <code>/apanel set_delay 0.5</code>\n"
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
                if delay < PING_LIMITS["min_delay"]: delay = PING_LIMITS["min_delay"]
                if delay > PING_LIMITS["max_delay"]: delay = PING_LIMITS["max_delay"]
                
                self.chat_repo.set_global_setting("ping_delay", delay)
                await self._safe_answer(message, f"✅ <b>Global Delay встановлено:</b> {delay}s", parse_mode="HTML")
            except ValueError:
                await self._safe_answer(message, "❌ Введіть коректне число (наприклад: 0.5)")

    async def cmd_ahelp(self, message: Message):
        """Швидка допомога для власника та адмінів"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
            
        help_text = (
            "👑 <b>Admin Help Panel</b>\n\n"
            "<b>Системні:</b>\n"
            "• /apanel — Глобальні налаштування\n"
            "• /sync — Синхронізація (Userbot)\n"
            "• /admin_toggle_userbot — Вкл/Викл юзербота\n"
            "• /ub_login — Авторизація юзербота через чат\n\n"
            "<b>Тригери (Global):</b>\n"
            "• /admin_add_trigger [word] [text/emoji]\n"
            "• /admin_del_trigger [word]\n\n"
            "<b>Premium:</b>\n"
            "• /admin_grant_premium [user_id] [days]\n"
            "• /admin_revoke_premium [user_id]\n"
            "• /admin_add_payment [user_id] [amount]"
        )
        help_text += (
            "\n👑 <b>Адмін-команди (Owner Only):</b>\n"
            "• /apanel — Глобальні налаштування\n"
            "• /ub_login — Авторизація юзербота\n"
            "• /admin_grant_premium user_id days\n"
            "• /admin_revoke_premium user_id\n"
            "• /admin_toggle_userbot — ВКЛ/ВИКЛ юзербот"
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
        await message.answer(f"✅ Global Trigger '{trigger}' added as {type_}\nAllowed types: {', '.join(allowed_types)}")

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
            parse_mode="HTML"
        )
    # === Userbot Login Flow Handlers ===

    async def cmd_ub_login(self, message: Message, state: FSMContext):
        """Починає процес авторизації юзербота (Bot Admins)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id):
            return
            
        await state.set_state(LoginStates.waiting_for_account)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Акаунт 2 (Старий)", callback_data="ub_acc_account2")],
            [InlineKeyboardButton(text="👤 Акаунт 3 (Новий)", callback_data="ub_acc_account3")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="ub_acc_cancel")]
        ])
        
        await self._safe_answer(
            message,
            "🛰 <b>ВИБІР АКАУНТА ЮЗЕРБОТА</b>\n\n"
            "Оберіть акаунт, який хочете авторизувати. Кожен акаунт має свій API ID та файл сесії.\n\n"
            "<i>Акаунт 2 — той, що мав проблеми з Email (можна спробувати пізніше).</i>\n"
            "<i>Акаунт 3 — новий чистий акаунт.</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def process_account_selection(self, callback: CallbackQuery, state: FSMContext):
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
            
        if not acc_config.get('api_id') or not acc_config.get('api_hash'):
            self.logger.error(f"Конфігурація для {account_id} неповна: {acc_config}")
            await callback.message.edit_text(
                f"❌ <b>Помилка конфігурації {account_id}!</b>\n\n"
                "Перевірте файл <code>.env</code> на сервері. Поля API_ID або API_HASH порожні.",
                parse_mode="HTML"
            )
            return

        # Зберігаємо обраний акаунт у стані
        await state.update_data(acc_id=account_id, acc_config=acc_config)
        
        # Перемикаємо клієнт на льоту!
        await callback.message.edit_text(f"⏳ Перемикаюся на <b>{account_id}</b>...\n(API: {acc_config['api_id']})", parse_mode="HTML")
        try:
            await self.userbot.switch_account(
                api_id=acc_config['api_id'],
                api_hash=acc_config['api_hash'],
                session_name=acc_config['session']
            )
        except Exception as e:
            self.logger.error(f"Failed to switch account: {e}")
            await callback.message.edit_text(f"❌ <b>Помилка ініціалізації:</b>\n<code>{e}</code>", parse_mode="HTML")
            return
        
        await state.set_state(LoginStates.waiting_for_phone)
        await callback.message.edit_text(
            f"🛰 <b>АВТОРИЗАЦІЯ: {account_id.upper()}</b>\n\n"
            "Будь ласка, введіть номер телефону в міжнародному форматі:\n"
            "Приклад: <code>+380501112233</code>\n\n"
            "<i>Щоб скасувати, напишіть /ub_cancel</i>",
            parse_mode="HTML"
        )

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
        
        status_msg = await self._safe_answer(message, "⏳ <b>Зв'язуюсь з Telegram...</b>", parse_mode="HTML")
        
        try:
            sent_code = await self.userbot.request_phone_code(phone)
            await state.update_data(
                phone=phone, 
                phone_code_hash=sent_code.phone_code_hash
            )
            await state.set_state(LoginStates.waiting_for_code)
            
            await status_msg.edit_text(
                f"✅ <b>Код відправлено на {phone}!</b>\n\n"
                "Перевірте ваші <b>повідомлення в Telegram</b> (код прийде від сервісного акаунту).\n\n"
                "Введіть отриманий код нижче:",
                parse_mode="HTML"
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
        
        status_msg = await self._safe_answer(message, "⏳ <b>Перевіряю код...</b>", parse_mode="HTML")
        
        try:
            result = await self.userbot.sign_in_with_code(
                data['phone'], 
                code, 
                data['phone_code_hash']
            )
            
            if result['status'] == 'password_needed':
                await state.set_state(LoginStates.waiting_for_password)
                await status_msg.edit_text(
                    "🔐 <b>2FA активовано!</b>\n\n"
                    "Будь ласка, введіть ваш хмарний пароль (Cloud Password):",
                    parse_mode="HTML"
                )
            else:
                await state.clear()
                await status_msg.edit_text("🎉 <b>Успіх! Юзербот авторизований.</b>", parse_mode="HTML")
                await self.userbot.start() # Перезавантажуємо клієнт
                
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
            await state.clear()
            await self._safe_answer(message, "🎉 <b>Успіх! Юзербот авторизований через 2FA.</b>", parse_mode="HTML")
            await self.userbot.start()
            
        except Exception as e:
            self.logger.error(f"Error signing in with password: {e}")
            await self._safe_answer(message, f"❌ Невірний пароль або інша помилка: {e}\nСпробуйте знову: /ub_login")
            await state.clear()


    # === Admin Management Commands (Owner Only) ===

    async def cmd_admin_add(self, message: Message):
        """Додає нового адміна бота (тільки власник)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_add [user_id]")
            return
            
        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_admin(target_id)
            await message.answer(f"✅ Користувача <code>{target_id}</code> додано до адмінів бота.", parse_mode="HTML")
        except ValueError:
            await message.answer("❌ Введіть коректний User ID (число).")

    async def cmd_admin_del(self, message: Message):
        """Видаляє адміна бота (тільки власник)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /admin_del [user_id]")
            return
            
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_admin(target_id):
                await message.answer(f"✅ Користувача <code>{target_id}</code> видалено з адмінів бота.", parse_mode="HTML")
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
            for o in owners: text += f"• <code>{o}</code>\n"
            text += "\n"
            
        if admins:
            text += "👨‍💻 <b>Адміни:</b>\n"
            for a in admins: text += f"• <code>{a}</code>\n"
            text += "\n"
            
        if mods:
            text += "🛡 <b>Модератори:</b>\n"
            for m in mods: text += f"• <code>{m}</code>\n"
            text += "\n"
            
        if ad_mods:
            text += "📢 <b>Модератори реклами:</b>\n"
            for am in ad_mods: text += f"• <code>{am}</code>\n"
            text += "\n"
            
        await message.answer(text, parse_mode="HTML")

    async def cmd_owner_add(self, message: Message):
        """Додає додаткового власника (тільки SuperOwner)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /owner_add [user_id]")
        
        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_owner(target_id)
            await message.answer(f"✅ Користувача <code>{target_id}</code> додано як <b>Власника</b>.", parse_mode="HTML")
        except: await message.answer("❌ Помилка")

    async def cmd_owner_del(self, message: Message):
        """Видаляє власника (тільки SuperOwner)"""
        if message.from_user.id != ADMIN_USER_ID:
            return
            
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /owner_del [user_id]")
        
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_owner(target_id):
                await message.answer(f"✅ Користувача <code>{target_id}</code> видалено зі списку власників.", parse_mode="HTML")
            else:
                await message.answer("❌ Власника не знайдено.")
        except: await message.answer("❌ Помилка")

    async def cmd_mod_add(self, message: Message):
        """Додає модератора (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id): return
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /mod_add [id]")
        try:
            target_id = int(args[1])
            self.chat_repo.add_bot_moderator(target_id)
            await message.answer(f"✅ Користувача <code>{target_id}</code> додано до модераторів.", parse_mode="HTML")
        except: await message.answer("❌ Error")

    async def cmd_mod_del(self, message: Message):
        """Видаляє модератора (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id): return
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /mod_del [id]")
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_bot_moderator(target_id):
                await message.answer("✅ Видалено.")
            else: await message.answer("❌ Не знайдено.")
        except: await message.answer("❌ Error")

    async def cmd_admod_add(self, message: Message):
        """Додає адмода (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id): return
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /admod_add [id]")
        try:
            target_id = int(args[1])
            self.chat_repo.add_ad_moderator(target_id)
            await message.answer(f"✅ Додано до реклами: <code>{target_id}</code>", parse_mode="HTML")
        except: await message.answer("❌ Error")

    async def cmd_admod_del(self, message: Message):
        """Видаляє адмода (Admin+)"""
        if not self.chat_repo.is_bot_admin(message.from_user.id): return
        args = message.text.split()
        if len(args) < 2: return await message.answer("Usage: /admod_del [id]")
        try:
            target_id = int(args[1])
            if self.chat_repo.remove_ad_moderator(target_id):
                await message.answer("✅ Видалено з реклами.")
            else: await message.answer("❌ Не знайдено.")
        except: await message.answer("❌ Error")
