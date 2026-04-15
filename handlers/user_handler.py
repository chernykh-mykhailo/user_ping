"""
User handlers - команди користувача (SRP)
"""

import logging
import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatMemberUpdated,
)
from .base_handler import BaseHandler
from utils.helpers import (
    get_clean_chat_id,
    get_user_name,
    render_emoji,
)
from utils.l10n import l10n
from config import (
    PREMIUM_PLANS,
    CHAT_PREMIUM_PLANS,
    FEEDBACK_BOT,
    PROJECTS_CHANNEL,
    REFERRAL_BONUS_SIGNUP,
    REFERRAL_BONUS_PREMIUM,
    ADMIN_USER_ID,
)
from __version__ import __version__
from aiogram.exceptions import TelegramBadRequest, TelegramServerError


class UserHandler(BaseHandler):
    """
    Обробляє команди користувачів
    Single Responsibility: тільки користувацькі команди
    """

    def __init__(self, chat_repo, premium_repo, emoji_service=None, bot=None):
        self.emoji_service = emoji_service
        self.bot = bot
        self.me = None  # Встановиться при першому виклику або вручну
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)

    def register_handlers(self):
        """Реєструє хендлери користувачів"""
        # Help
        self.router.message(Command("help"))(self.cmd_help)
        self.router.message(Command("start"))(
            self.cmd_start
        )  # Окремо для реферальних посилань
        self.router.message(F.text.regexp(r"^[!/](хелп|допомога)", flags=0))(
            self.cmd_help
        )
        self.router.callback_query(F.data.startswith("help_"))(
            self.callback_help_section
        )

        # Contact
        self.router.message(Command("feedback", "contact"))(self.cmd_feedback)

        # New Chat Notification (v2.4.2)
        from aiogram.filters import ChatMemberUpdatedFilter, MEMBER, ADMINISTRATOR

        self.router.my_chat_member(
            ChatMemberUpdatedFilter(member_status_changed=(MEMBER | ADMINISTRATOR))
        )(self.on_bot_join)

        # Unreg/Reg - case-insensitive for Ukrainian commands (Анрег = анрег)
        import re

        self.router.message(Command("unreg"))(self.cmd_unreg)
        self.router.message(F.text.regexp(r"^\s*[!/]анрег(\s|$)", flags=re.IGNORECASE))(
            self.cmd_unreg
        )

        self.router.message(Command("superunreg"))(self.cmd_superunreg)
        self.router.message(
            F.text.regexp(r"^\s*[!/]суперанрег(\s|$)", flags=re.IGNORECASE)
        )(self.cmd_superunreg)

        self.router.message(Command("superpuperunreg", "spa"))(self.cmd_superpuperunreg)
        self.router.message(
            F.text.regexp(r"^\s*[!/]суперпуперанрег(\s|$)", flags=re.IGNORECASE)
        )(self.cmd_superpuperunreg)

        self.router.message(Command("reg"))(self.cmd_reg)
        self.router.message(F.text.regexp(r"^\s*[!/]рег(\s|$)", flags=re.IGNORECASE))(
            self.cmd_reg
        )

        # Global Unreg (v1.5.0+)
        self.router.message(Command("gunreg"))(self.cmd_global_unreg)
        self.router.message(F.text.regexp(r"^\s*[!/]ганрег(\s|$)", flags=re.IGNORECASE))(
            self.cmd_global_unreg
        )

        # Set Emoji Callbacks
        self.router.callback_query(F.data.startswith("set_emoji:"))(
            self.callback_select_emoji
        )

        self.router.message(Command("gsuperunreg"))(self.cmd_global_superunreg)
        self.router.message(
            F.text.regexp(r"^\s*[!/]гсуперанрег(\s|$)", flags=re.IGNORECASE)
        )(self.cmd_global_superunreg)

        self.router.message(Command("greg"))(self.cmd_global_reg)
        self.router.message(F.text.regexp(r"^\s*[!/]грег(\s|$)", flags=re.IGNORECASE))(
            self.cmd_global_reg
        )

        # Premium
        # Premium
        self.router.message(Command("balance"))(self.cmd_balance)
        self.router.message(Command("spanreg"))(self.cmd_superunreg)

        # v2.6.5: Слідкуємо за виходом учасників (Real-time cleanup)
        from aiogram.filters import (
            ChatMemberUpdatedFilter,
            LEFT,
            KICKED,
            MEMBER,
            ADMINISTRATOR,
            RESTRICTED,
        )

        self.router.chat_member(
            ChatMemberUpdatedFilter(member_status_changed=(LEFT | KICKED))
        )(self.on_user_left)

        self.router.chat_member(
            ChatMemberUpdatedFilter(
                member_status_changed=(MEMBER | ADMINISTRATOR | RESTRICTED)
            )
        )(self.on_user_join)

        # v2.7.5: Personal Emoji
        self.router.message(Command("setemoji"))(self.cmd_set_emoji)
        self.router.message(F.text.startswith("!setemoji"))(self.cmd_set_emoji)

        # v2.10.19: Admin forced actions
        self.router.message(Command("chat_reg"))(self.cmd_chat_reg)
        self.router.message(Command("force_unreg"))(self.cmd_force_unreg)
        self.router.message(Command("force_reg"))(self.cmd_force_reg)

    async def on_user_join(self, event: ChatMemberUpdated):
        """Додає користувача в базу, коли він входить в чат"""
        if event.new_chat_member.user.is_bot:
            return

        chat_id = get_clean_chat_id(event.chat.id)
        user = event.new_chat_member.user
        user_id = str(user.id)

        name = get_user_name(
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            user_id=user.id,
        )

        # Додаємо в базу як "пасивного" учасника (не знімаємо анрег, якщо він був)
        self.chat_repo.save_user(
            chat_id, user_id, name, update_unreg=False, username=user.username
        )
        self.logger.info(
            f"Real-time Join: Користувач {user_id} приєднався до {chat_id}"
        )

    async def on_user_left(self, event: ChatMemberUpdated):
        """Видаляє користувача з бази, коли він виходить з чату"""
        chat_id = get_clean_chat_id(event.chat.id)
        user_id = str(event.old_chat_member.user.id)

        self.chat_repo.remove_user(chat_id, user_id)
        self.logger.info(f"Real-time Cleanup: Користувач {user_id} вийшов з {chat_id}")

    async def cmd_start(self, message: Message):
        """Обробляє команду /start та реферальні посилання"""
        from config import REFERRAL_BONUS_SIGNUP, PROJECTS_CHANNEL

        # 1. Перевірка реферального коду
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("ref_"):
            referrer_id = args[1].replace("ref_", "")
            referred_id = str(message.from_user.id)

            if referrer_id != referred_id:
                from core import ReferralRepository
                from core.database import JSONDatabase
                from config import DB_FILE

                db = JSONDatabase(DB_FILE)
                referral_repo = ReferralRepository(db)

                if referral_repo.track_referral(referrer_id, referred_id):
                    from core import PremiumRepository

                    premium_repo = PremiumRepository(db)
                    premium_repo.grant_premium(referrer_id, REFERRAL_BONUS_SIGNUP)
                    referral_repo.add_bonus_days(referrer_id, REFERRAL_BONUS_SIGNUP)

                    # Повідомляємо реферера
                    try:
                        await message.bot.send_message(
                            int(referrer_id),
                            f"🎁 <b>Новий реферал!</b>\n\n"
                            f"👤 {message.from_user.first_name} приєднався за вашим посиланням!\n"
                            f"💎 Ви отримали +{REFERRAL_BONUS_SIGNUP} днів Premium\n\n"
                            f"<i>Продовжуйте ділитися посиланням!</i>",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to notify referrer: {e}")

                    await message.answer(
                        f"🎉 <b>Вітаємо!</b>\n\n"
                        f"Ви приєдналися за реферальним посиланням!\n"
                        f"Ваш друг отримав +{REFERRAL_BONUS_SIGNUP} днів Premium 🎁\n\n"
                        f"Купіть Premium і він отримає ще більше бонусів!\n"
                        f"/premium",
                        parse_mode="HTML",
                    )
                    return

        # 2. Стандартне привітання (якщо не був реферал або вже оброблено)
        start_text = (
            "👋 <b>Вітаю! Ping Bot готовий до роботи!</b>\n\n"
            "📋 <b>Швидкий старт:</b>\n"
            "1️⃣ Зробіть мене <b>адміністратором</b> (для доступу до повідомлень)\n"
            "2️⃣ Виконайте /sync для синхронізації учасників (якщо потрібно)\n"
            "3️⃣ Готово! Тепер можна використовувати /all, /anybody та інші команди\n\n"
            "✨ <b>Real-time Tracking:</b> Бот автоматично бачить кожного, хто пише або заходить у чат. "
            "Юзербот потрібен тільки для швидкого збору тих, хто ще не проявив активність.\n\n"
            "Всі команди: /help"
        )
        sent = await message.answer(start_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent, custom_delay=60)

    async def cmd_help(self, message: Message):
        """Показує головне меню довідки"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📢 Пінги", callback_data="help_pings"),
                    InlineKeyboardButton(
                        text="🎯 Тригери", callback_data="help_triggers"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎮 Панель ролей", callback_data="help_roles"
                    ),
                    InlineKeyboardButton(
                        text="📝 Шаблони", callback_data="help_templates"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="⚙️ Керування", callback_data="help_management"
                    ),
                    InlineKeyboardButton(
                        text="👑 Premium", callback_data="help_premium"
                    ),
                ],
            ]
        )

        # v2.7.5: Personal Emoji in Profile
        personal_emoji = self.chat_repo.get_user_setting(
            message.from_user.id, "personal_emoji", ""
        )
        profile_header = f"{render_emoji(personal_emoji)} " if personal_emoji else ""

        help_text = (
            f"<b>{profile_header}📋 Довідка бота v{__version__}</b>\n\n"
            "Оберіть розділ для детальної інформації.\n\n"
            "⚠️ <b>Порада:</b> Для стабільної роботи (авточистка, пін) надайте боту права <b>Адміністратора</b> (видалення та закріплення).\n\n"
            "📢 <b>Пінги</b> — Виклики користувачів\n"
            "🎯 <b>Тригери</b> — Вибіркові виклики груп\n"
            "🎮 <b>Панель ролей</b> — Самореєстрація\n"
            "📝 <b>Шаблони</b> — Збережені тексти\n"
            "⚙️ <b>Керування</b> — Адмін-команди\n"
            "👑 <b>Premium</b> — Преміум функції (вкл. Захист від тегів)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💬 Зв'язок: /feedback\n"
            "🛡 Alias: /spanreg = /superunreg\n"
            f"📢 Проекти: <a href='{PROJECTS_CHANNEL}'>Канал</a>"
        )

        sent = await message.answer(
            help_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await self.auto_cleanup(message, sent)

    async def handle_user_activity(self, message: Message):
        """Відстежує активність користувача для зняття анрегу (v1.6.0)"""
        # Тільки для груп
        if not message.chat or message.chat.type not in ["group", "supergroup"]:
            return

        # Ігноруємо ботів
        if message.from_user and message.from_user.is_bot:
            return

        text = message.text or message.caption or ""
        # Якщо це команда або тригер - ігноруємо (вони обробляються окремо і не знімають анрег)
        if text.startswith(("/", "!")):
            return

        # v2.6.3: Перевіряємо слова-команди без префіксів (анрег, рег, всі і т.д.)
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
        first_word = text.strip().lower().split()[0] if text.strip() else ""
        if first_word in word_commands:
            return

        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        name = get_user_name(
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            user_id=message.from_user.id,
        )

        # Оновлюємо ім'я та знімаємо тимчасовий анрег
        self.chat_repo.save_user(
            chat_id,
            user_id,
            name,
            update_unreg=True,
            username=message.from_user.username,
        )

    async def callback_help_section(self, callback: CallbackQuery):
        """Обробляє вибір розділу довідки"""
        section = callback.data.replace("help_", "")
        self.logger.info(
            f"Help section requested: {section} by {callback.from_user.id}"
        )

        async def safe_edit_text(text, reply_markup=None, **kwargs):
            for i in range(3):
                try:
                    await callback.message.edit_text(
                        text, reply_markup=reply_markup, parse_mode="HTML", **kwargs
                    )
                    return
                except TelegramServerError:
                    await asyncio.sleep(0.5)
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e):
                        return
                    raise e

        try:
            await callback.answer()
        except:
            pass

        # Кнопка "Назад"
        back_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="help_main")]
            ]
        )

        try:
            if section == "main":
                personal_emoji = self.chat_repo.get_user_setting(
                    callback.from_user.id, "personal_emoji", ""
                )
                profile_header = (
                    f"{render_emoji(personal_emoji)} " if personal_emoji else ""
                )

                help_text = (
                    f"<b>{profile_header}📋 Довідка бота v{__version__}</b>\n\n"
                    "Оберіть розділ для детальної інформації.\n\n"
                    "⚠️ <b>Порада:</b> Для стабільної роботи (авточистка, пін) надайте боту права <b>Адміністратора</b> (видалення та закріплення).\n\n"
                    "📢 <b>Пінги</b> — Виклики користувачів\n"
                    "🎯 <b>Тригери</b> — Вибіркові виклики груп\n"
                    "🎮 <b>Панель ролей</b> — Самореєстрація\n"
                    "📝 <b>Шаблони</b> — Збережені тексти\n"
                    "⚙️ <b>Керування</b> — Адмін-команди\n"
                    "👑 <b>Premium</b> — Преміум функції\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "💬 Зв'язок: /feedback\n"
                    f"📢 Проекти: <a href='{PROJECTS_CHANNEL}'>Канал</a>"
                )
                await safe_edit_text(
                    help_text,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="📢 Пінги", callback_data="help_pings"
                                ),
                                InlineKeyboardButton(
                                    text="🎯 Тригери", callback_data="help_triggers"
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="🎮 Панель ролей", callback_data="help_roles"
                                ),
                                InlineKeyboardButton(
                                    text="📝 Шаблони", callback_data="help_templates"
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="⚙️ Керування", callback_data="help_management"
                                ),
                                InlineKeyboardButton(
                                    text="👑 Premium", callback_data="help_premium"
                                ),
                            ],
                        ]
                    ),
                    disable_web_page_preview=True,
                )

            elif section == "pings":
                text = (
                    "<b>📢 Пінги</b>\n\n"
                    "<b>Гібридні виклики (рекомендовано):</b>\n"
                    "• <code>!активні</code> або /active — В мережі + хто писав (24г)\n"
                    "• <code>!актив_тиждень</code> або /active_week — Гібрид за тиждень\n\n"
                    "<b>Точні виклики:</b>\n"
                    "• <code>!писали</code> або /writers — Тільки ті, хто відправив повідомлення\n"
                    "• <code>!онлайн</code> або /online — Тільки ті, хто зараз в мережі\n\n"
                    "<b>Базові виклики:</b>\n"
                    "• <code>!всі</code> або /all — Заклик усіх (включаючи офлайн)\n"
                    "• <code>!емодзі</code> або /emoji — Заклик усіх (емодзі)\n"
                    "• <code>!адміни</code> або /admins — Заклик тільки адміністраторів\n"
                    "• <code>!хтось</code> або /anybody — Випадковий учасник\n\n"
                    "<b>Налаштування:</b>\n"
                    "• <code>!анрег</code> або /unreg — Тимчасово не пінгувати мене\n"
                    "• <code>!рег</code> або /reg — Повернутися в списки\n"
                    "• <code>!стоп</code> — Зупинити поточний виклик"
                )
                await safe_edit_text(text, reply_markup=back_button)

            elif section == "triggers":
                text = (
                    "<b>🎯 Тригери викликів</b>\n\n"
                    "<b>Створення тригерів-викликів:</b>\n"
                    "• <code>!addtrigger слово</code> — Пінг усіх (текстом)\n"
                    "• <code>!addemojitrigger слово</code> — Пінг усіх (емодзі)\n"
                    "• <code>!addactivetrigger слово</code> — Гібридний актив (24г)\n"
                    "• <code>!addactiveweektrigger слово</code> — Гібридний актив (тиждень)\n"
                    "• <code>!addwritertrigger слово</code> — Тільки ті, хто писав\n"
                    "• <code>!addonlinetrigger слово</code> — Тільки ті, хто онлайн\n\n"
                    "<b>Управління групами користувачів:</b>\n"
                    "• <code>!calls</code> — Список тригерів груп\n"
                    "• <code>!addcall назва емодзі</code> — Створити групу\n"
                    "• <code>!delcall назва</code> — Видалити групу\n\n"
                    "<b>Загальне управління:</b>\n"
                    "• <code>!triggers</code> — Список усіх кастомних слів\n"
                    "• <code>!deltrigger слово</code> — Видалити слово-виклик"
                )
                await safe_edit_text(text, reply_markup=back_button)

            elif section == "roles":
                text = (
                    "<b>🎮 Панель самореєстрації</b>\n\n"
                    "<i>Користувачі самі обирають тригери!</i>\n\n"
                    "<b>Налаштування (адмін):</b>\n"
                    "1. Створіть тригери:\n"
                    "   <code>!addcall croco 🐊</code>\n"
                    "   <code>!addcall mafia 🔫</code>\n\n"
                    "2. Створіть панель:\n"
                    "   <code>!roles_panel</code>\n\n"
                    "<b>Використання:</b>\n"
                    "Користувачі натискають кнопки для реєстрації:\n"
                    "• ✅ — Зареєстрований\n"
                    "• Без ✅ — Не зареєстрований\n\n"
                    "<i>Як в Discord! 🎯</i>"
                )
                await safe_edit_text(text, reply_markup=back_button)

            elif section == "templates":
                text = (
                    "<b>📝 Шаблони викликів</b>\n\n"
                    "<i>Збережені тексти для швидких викликів</i>\n\n"
                    "<b>Управління:</b>\n"
                    "• <code>!cpatterns</code> — Список шаблонів\n"
                    "• <code>!addcpattern назва</code> — Додати (у відповідь на повідомлення)\n"
                    "• <code>!delcpattern назва</code> — Видалити\n\n"
                    "<b>Використання:</b>\n"
                    "• <code>/all назва_шаблону</code> — Викликати з текстом\n\n"
                    "<b>Приклад:</b>\n"
                    '1. Напишіть: "Збори о 18:00"\n'
                    "2. Відповідайте: <code>!addcpattern meeting</code>\n"
                    "3. Використайте: <code>/all meeting</code>"
                )
                await safe_edit_text(text, reply_markup=back_button)

            elif section == "management":
                is_super = callback.from_user.id == ADMIN_USER_ID
                is_owner = self.chat_repo.is_owner(callback.from_user.id)
                is_admin = self.chat_repo.is_bot_admin(callback.from_user.id)

                text = (
                    "<b>⚙️ Керування</b>\n\n"
                    "<b>Адмін-панель:</b>\n"
                    "• /settings — Головне меню налаштувань\n\n"
                    "<b>Базові команди:</b>\n"
                    "• <code>!збір</code> або /sync — Оновити базу користувачів\n"
                    "• <code>!стата</code> або /stats — Статистика чату\n"
                    "• <code>!адміни</code> — Пінганути всіх адмінів\n"
                )

                if is_admin or is_owner or is_super:
                    text += (
                        "\n<b>👑 Адмін-команди (Owner Only):</b>\n"
                        "• /apanel — Глобальні налаштування\n"
                        "• /ub_login — Авторизація юзербота\n"
                        "• /admin_toggle_userbot — ВКЛ/ВИКЛ юзербот\n"
                        "• /admin_list — Весь склад персоналу\n"
                    )

                if is_owner or is_super:
                    text += (
                        "\n<b>💎 Premium команди:</b>\n"
                        "• /admin_grant_premium user_id days\n"
                        "• /admin_revoke_premium user_id\n"
                        "• /admin_grant_chat_premium chat_id days\n"
                        "• /chat_unreg — Анрег всього чату\n"
                    )

                if is_super:
                    text += (
                        "\n<b>⭐️ SuperOwner Only:</b>\n"
                        "• /owner_add [ID] — Додати співвласника\n"
                        "• /owner_del [ID] — Видалити власника\n"
                        "• /mod_add [ID] — Додати модератора\n"
                    )

                # Додаємо кнопку налаштувань прямо сюди для зручності
                mgmt_kb = [
                    [
                        InlineKeyboardButton(
                            text="⚙️ Налаштування чату",
                            callback_data="settings_location_chat_0_0",
                        )
                    ],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="help_main")],
                ]
                # Ховаємо кнопку налаштувань в ЛС, бо вона там не працює
                if callback.message.chat.type == "private":
                    mgmt_kb.pop(0)

                await safe_edit_text(
                    text, reply_markup=InlineKeyboardMarkup(inline_keyboard=mgmt_kb)
                )

            elif section == "premium":
                text = (
                    f"<b>👑 Premium</b>\n\n"
                    f"<b>Personal Premium:</b>\n"
                    f"• 🚫 /superunreg — Постійне вимкнення пінгів\n"
                    f"• 🎯 Доступ до всіх функцій\n"
                    f"⭐ Місяць: {PREMIUM_PLANS['month'].price} Stars\n"
                    f"⭐ Рік: {PREMIUM_PLANS['year'].price} Stars\n\n"
                    f"<b>💎 Chat Premium:</b>\n"
                    f"• 🎯 Безліміт тригерів\n"
                    f"• 📊 Розширена статистика\n"
                    f"• 👥 Доступ для всіх адмінів\n"
                    f"⭐ Місяць: {CHAT_PREMIUM_PLANS['month'].price} Stars\n"
                    f"⭐ Рік: {CHAT_PREMIUM_PLANS['year'].price} Stars\n\n"
                    f"<b>🎁 Подарунок Premium:</b>\n"
                    f"• Подаруйте Premium друзям!\n"
                    f"• /gift_premium — інструкція\n\n"
                    f"<b>🔗 Реферальна програма:</b>\n"
                    f"• +{REFERRAL_BONUS_SIGNUP} днів за кожного друга\n"
                    f"• +{REFERRAL_BONUS_PREMIUM} днів якщо друг купить Premium\n"
                    f"• /referral — ваше посилання\n\n"
                    f"<b>Команди:</b>\n"
                    f"• /premium — Personal Premium\n"
                    f"• /chat_premium — Chat Premium\n"
                    f"• /gift_premium — Подарунок\n"
                    f"• /referral — Реферали\n"
                    f"• /balance — Статус\n"
                    f"• /refund — Повернення"
                )
                await safe_edit_text(text, reply_markup=back_button)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                try:
                    await callback.answer()
                except:
                    pass
            else:
                raise e

    async def cmd_feedback(self, message: Message):
        """Показує контакти для зворотного зв'язку"""
        feedback_text = (
            "💬 <b>Зворотний зв'язок</b>\n\n"
            f"Є питання, пропозиції або знайшли баг?\n"
            f"Напишіть нам: {FEEDBACK_BOT}\n\n"
            f"📢 Слідкуйте за нашими проектами:\n"
            f"<a href='{PROJECTS_CHANNEL}'>Telegram канал</a>\n\n"
            "<i>Ми завжди раді вашому фідбеку! 🙏</i>"
        )
        sent = await message.answer(
            feedback_text, parse_mode="HTML", disable_web_page_preview=True
        )
        await self.auto_cleanup(message, sent)

    async def cmd_unreg(self, message: Message):
        """Тимчасово вимикає пінги з можливістю авто-видалення та цитатою"""
        if message.chat.type not in ["group", "supergroup"]:
            return

        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)

        # Check if unreg is allowed in this chat
        allow_unreg = self.chat_repo.get_setting(chat_id, "allow_unreg", True)
        is_whitelisted = self.chat_repo.is_user_unreg_whitelisted(chat_id, user_id)

        if not allow_unreg and not is_whitelisted:
            denied_msg = self.chat_repo.get_setting(chat_id, "unreg_denied_message")
            if not denied_msg:
                denied_msg = (
                    "🚫 <b>Анрег вимкнено адміністратором чату.</b>\n"
                    "У цьому чаті не можна відключати сповіщення."
                )
            sent = await self._safe_answer(message, denied_msg, parse_mode="HTML")
            await self.auto_cleanup(message, sent)
            try:
                await message.delete()
            except:
                pass
            return

        # Check for quote
        quote = None
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            quote = args[1].strip()

        # Logic for quote permissions
        if quote:
            quote_mode = self.chat_repo.get_global_setting(
                "unreg_quote_mode", "premium"
            )  # 'all' or 'premium'
            has_premium = self.premium_repo.has_premium(user_id)

            # Якщо режим "premium" і у юзера немає преміум
            if quote_mode == "premium" and not has_premium:
                sent = await self._safe_answer(
                    message,
                    "💎 <b>Premium Feature</b>\n\n"
                    "Залишати повідомлення при анрегу можуть тільки Premium користувачів.\n"
                    "Власник бота може змінити це в налаштуваннях.",
                    parse_mode="HTML",
                )
                await self.auto_cleanup(message, sent)
                return

        self.logger.info(
            f"Команда анрег від {user_id} у чаті {chat_id} (quote={bool(quote)})"
        )

        added = self.chat_repo.add_to_temp_unreg(chat_id, user_id)

        # Debug: verify it was actually saved
        chat_data = self.chat_repo.get_chat_data(chat_id)
        current_temp = chat_data.get("temp_unreg", [])
        self.logger.info(f"[UNREG DEBUG] added={added}, temp_unreg now: {current_temp}")

        if added:
            if quote:
                name = get_user_name(
                    message.from_user.first_name,
                    message.from_user.last_name,
                    message.from_user.username,
                    message.from_user.id,
                )
                # Escaping quote to prevent HTML injection
                from html import escape

                safe_quote = escape(quote)

                # v2.10.17: Додаємо емодзі юзера, якщо є
                user_emoji = self.chat_repo.get_user_setting(
                    user_id, "personal_emoji", ""
                )
                emoji_html = render_emoji(user_emoji) if user_emoji else ""
                emoji_prefix = f"{emoji_html} " if emoji_html else ""

                text = f"🔕 {emoji_prefix}<b>{name}</b> анрегнувся зі словами:\n<i>{safe_quote}</i>"
                sent = await message.answer(text, parse_mode="HTML")

                # Check chat setting for cleanup (default: False - keep quote)
                cleanup_quote = self.chat_repo.get_setting(
                    chat_id, "cleanup_unreg_quote", False
                )

                if cleanup_quote:
                    await self.auto_cleanup(message, sent)
                else:
                    # Якщо ми НЕ видаляємо відповідь бота, то видаляємо команду юзера для чистоти
                    try:
                        await message.delete()
                    except:
                        pass
            else:
                user_emoji = self.chat_repo.get_user_setting(
                    user_id, "personal_emoji", ""
                )
                emoji_html = render_emoji(user_emoji) if user_emoji else ""
                emoji_prefix = f"{emoji_html} " if emoji_html else ""

                name = get_user_name(
                    message.from_user.first_name,
                    message.from_user.last_name,
                    message.from_user.username,
                    message.from_user.id,
                )

                text = f"🔕 {emoji_prefix}<b>{name}</b>: пінги вимкнено.\n<i>Напишіть будь-що в чат, щоб увімкнути назад.</i>"
                sent = await self._safe_answer(message, text, parse_mode="HTML")
                await self.auto_cleanup(message, sent)
        else:
            sent = await self._safe_answer(
                message, "ℹ️ Ви вже в режимі тимчасового анрегу."
            )
            await self.auto_cleanup(message, sent)

    async def cmd_superunreg(self, message: Message):
        """Постійно вимикає пінги (Premium або Chat Premium)"""
        user_id = str(message.from_user.id)
        chat_id = get_clean_chat_id(message.chat.id)
        self.logger.info(f"Команда SUPERUNREG від {user_id} у чаті {chat_id}")

        # Check if unreg is allowed in this chat
        allow_unreg = self.chat_repo.get_setting(chat_id, "allow_unreg", True)
        is_whitelisted = self.chat_repo.is_user_unreg_whitelisted(chat_id, user_id)

        if not allow_unreg and not is_whitelisted:
            denied_msg = self.chat_repo.get_setting(chat_id, "unreg_denied_message")
            if not denied_msg:
                denied_msg = (
                    "🚫 <b>Анрег вимкнено адміністратором чату.</b>\n"
                    "У цьому чаті не можна використовувати SuperUnreg."
                )
            sent = await self._safe_answer(message, denied_msg, parse_mode="HTML")
            await self.auto_cleanup(message, sent)
            try:
                await message.delete()
            except:
                pass
            return

        # Перевірка: Personal Premium АБО Chat Premium
        has_personal = self.premium_repo.has_premium(user_id)

        # Check Chat Premium
        from core import ChatPremiumRepository
        from core.database import JSONDatabase
        from config import DB_FILE

        db = JSONDatabase(DB_FILE)
        chat_premium_repo = ChatPremiumRepository(db)
        has_chat_premium = chat_premium_repo.has_chat_premium(chat_id)

        if not has_personal and not has_chat_premium:
            sent = await message.answer(
                "👑 <b>PREMIUM REQUIRED</b>\n\n"
                "Функція <b>SuperUnreg</b> дозволяє назавжди зникнути з радарів пінгу.\n\n"
                "✨ <b>Як отримати:</b>\n"
                "• Personal Premium: /premium\n"
                "• Chat Premium: попросіть адміна чату\n\n"
                "<i>Chat Premium дозволяє SuperUnreg для всіх в чаті!</i>",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return

        added = self.chat_repo.add_to_super_unreg(chat_id, user_id)

        if added:
            user_emoji = self.chat_repo.get_user_setting(user_id, "personal_emoji", "")
            from utils.helpers import render_emoji, get_user_name

            emoji_html = render_emoji(user_emoji) if user_emoji else ""
            emoji_prefix = f"{emoji_html} " if emoji_html else ""

            name = get_user_name(
                message.from_user.first_name,
                message.from_user.last_name,
                message.from_user.username,
                message.from_user.id,
            )

            sent = await message.answer(
                f"🛡 {emoji_prefix}<b>{name}</b>: SUPER UNREG АКТИВОВАНО\n\n"
                "💎 Ви успішно використали свій <b>Premium</b> статус. Тепер учасники не зможуть пінгнути вас у цьому чаті, навіть якщо ви будете активні.\n\n"
                "<i>Повернутися: /reg</i>",
                parse_mode="HTML",
            )
        else:
            sent = await message.answer(
                "ℹ️ <b>Ви вже захищені SuperUnreg у цьому чаті.</b>", parse_mode="HTML"
            )

        # SuperUnreg повідомлення висять довше (60с), щоб всі бачили статус
        await self.auto_cleanup(message, sent, custom_delay=60)

    async def cmd_superpuperunreg(self, message: Message):
        """Супер-Пупер Анрег: Те саме, що SuperUnreg, але з перевіркою прав"""
        if message.chat.type not in ["group", "supergroup"]:
            return

        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)

        # Перевірка налаштування allow_unreg
        allow_unreg = self.chat_repo.get_setting(chat_id, "allow_unreg", True)
        if not allow_unreg:
            denied_msg = self.chat_repo.get_setting(chat_id, "unreg_denied_message")
            if not denied_msg:
                denied_msg = "🚫 <b>Анрег вимкнено адміністратором чату.</b>\nУ цьому чаті не можна відключати сповіщення."

            sent = await self._safe_answer(message, denied_msg, parse_mode="HTML")
            await self.auto_cleanup(message, sent)
            return

        # Перевірка Premium
        has_personal = self.premium_repo.has_premium(user_id)
        from core import ChatPremiumRepository
        from core.database import JSONDatabase
        from config import DB_FILE

        db = JSONDatabase(DB_FILE)
        chat_premium_repo = ChatPremiumRepository(db)
        has_chat_premium = chat_premium_repo.has_chat_premium(chat_id)

        if not has_personal and not has_chat_premium:
            sent = await message.answer(
                "👑 <b>PREMIUM REQUIRED</b>\n\n"
                "Функція <b>SuperPuperUnreg</b> дозволяє назавжди зникнути з радарів пінгу.\n\n"
                "✨ <b>Як отримати:</b>\n"
                "• Personal Premium: /premium\n"
                "• Chat Premium: попросіть адміна чату",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return

        added = self.chat_repo.add_to_super_puper_unreg(chat_id, user_id)

        if added:
            # Перевірка прав бота на видалення (для Mention Protection)
            try:
                bot_member = await message.bot.get_chat_member(
                    message.chat.id, message.bot.id
                )
                can_delete = getattr(bot_member, "can_delete_messages", True)
            except:
                can_delete = True

            warning_text = ""
            if not can_delete:
                warning_text = (
                    "\n\n⚠️ <b>Увага:</b> У бота немає прав на видалення повідомлень!\n"
                    "Вас не будуть пінгувати через команди, але бот <b>не зможе видаляти</b> ручні теги від інших користувачів."
                )

            sent = await message.answer(
                f"🛡 <b>SUPER PUPER UNREG: АКТИВОВАНО</b>\n\n"
                f"💎 Ви успішно використали свій <b>Premium</b> статус. Тепер учасники не зможуть пінгнути вас у цьому чаті, навіть якщо ви будете активні.\n"
                f"<i>Повернутися: /reg</i>{warning_text}",
                parse_mode="HTML",
            )
        else:
            sent = await message.answer(
                "ℹ️ <b>Ви вже захищені SuperPuperUnreg у цьому чаті.</b>",
                parse_mode="HTML",
            )

        await self.auto_cleanup(message, sent, custom_delay=60)

    async def cmd_reg(self, message: Message):
        """Увімкнює пінги назад"""
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)

        # Перевіряємо глобальний статус перед змінами (v2.10.18: для кращого фідбеку)
        glob_status = self.chat_repo.is_globally_unreg(user_id)
        is_glob_unreg = glob_status["temp"] or glob_status["super"]

        removed = self.chat_repo.remove_from_unreg(chat_id, user_id)

        if removed:
            if is_glob_unreg:
                msg = (
                    "🔔 <b>Пінги увімкнено!</b>\n"
                    "(Ви використали локальне перекриття для цього чату, глобальний анрег залишається активним)"
                )
            else:
                msg = "✅ Пінги увімкнено! Тепер ви знову отримуватимете сповіщення."
            sent = await message.answer(msg, parse_mode="HTML")
        else:
            sent = await message.answer("ℹ️ Ви і так отримуєте пінги.")

        await self.auto_cleanup(message, sent)

    async def cmd_balance(self, message: Message):
        """Показує статус преміуму"""
        user_id = str(message.from_user.id)

        if self.premium_repo.has_premium(user_id):
            expiry = self.premium_repo.get_expiry(user_id)
            from datetime import datetime

            days_left = (expiry - datetime.now()).days

            balance_text = (
                "👑 <b>Ваш Premium статус</b>\n\n"
                f"✅ Активний до: {expiry.strftime('%d.%m.%Y')}\n"
                f"⏳ Залишилось днів: {days_left}\n\n"
                "Продовжити: /premium"
            )
        else:
            balance_text = "❌ <b>У вас немає Premium</b>\n\nКупити Premium: /premium"

        sent = await message.answer(balance_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent)

    # === Global Unreg Logic ===

    async def cmd_global_unreg(self, message: Message):
        """Вимкнення пінгів у всіх чатах відразу"""
        user_id = str(message.from_user.id)

        self.chat_repo.add_to_global_unreg(user_id, is_super=False)

        sent = await message.answer(
            "🌍 <b>Глобальний анрег активовано</b>\n\n"
            "Пінги вимкнені у <b>всіх чатах</b> з ботом.\n"
            "<i>Автоувімкнення при наступному повідомленні</i>",
            parse_mode="HTML",
        )
        await self.auto_cleanup(message, sent)

    async def cmd_global_superunreg(self, message: Message):
        """Постійне вимкнення пінгів у всіх чатах (Premium)"""
        user_id = str(message.from_user.id)

        if not self.premium_repo.has_premium(user_id):
            sent = await message.answer(
                "👑 <b>GLOBAL PREMIUM FEATURE</b>\n\n"
                "<b>Глобальний SuperUnreg</b> — це ультимативне рішення. Ви зникаєте з усіх пінгувань у всіх чатах одночасно.\n\n"
                "💎 Придбати доступ: /premium",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return

        self.chat_repo.add_to_global_unreg(user_id, is_super=True)

        sent = await message.answer(
            "🌌 <b>GLOBAL SUPER UNREG</b>\n\n"
            "✨ <b>Статус: УЛЬТИМАТИВНИЙ ЗАХИСТ</b>\n"
            "Ви повністю приховані від усіх типів пінгування (all, active, writers тощо) в усіх чатах, де присутній бот.\n\n"
            "<i>Зняти захист: /greg</i>",
            parse_mode="HTML",
        )
        await self.auto_cleanup(message, sent, custom_delay=60)

    async def cmd_global_reg(self, message: Message):
        """Увімкнення пінгів у всіх чатах відразу"""
        user_id = str(message.from_user.id)

        removed = self.chat_repo.remove_from_global_unreg(user_id)

        if removed:
            sent = await message.answer(
                "🔔 <b>Глобальні пінги увімкнено!</b>\n\n"
                "Ви знову отримуватимете сповіщення в усіх чатах."
            )
        else:
            sent = await message.answer("ℹ️ Ви і так отримували глобальні пінги.")

        await self.auto_cleanup(message, sent)

    async def cmd_chat_reg(self, message: Message):
        """Регає весь чат (тільки для власника чату або адмінів бота)"""
        user_id = message.from_user.id
        from utils.helpers import get_clean_chat_id

        chat_id = get_clean_chat_id(message.chat.id)

        # Check permission: Bot Admin/Owner OR Chat Owner
        is_bot_staff = self.chat_repo.is_bot_admin(user_id)

        # Check if user is chat owner
        chat_member = await message.chat.get_member(user_id)
        is_chat_owner = chat_member.status == "creator"

        if not (is_bot_staff or is_chat_owner):
            sent = await message.answer(
                "❌ Ця команда тільки для <b>Власника чату</b> або <b>Адміністрації бота</b>.",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        count = self.chat_repo.clear_chat_unreg(chat_id)

        if count > 0:
            sent = await message.answer(
                f"✅ <b>Учасників зареєстровано!</b>\n\n"
                f"Успішно повернуто в стрій: <b>{count}</b> користувачів.\n",
                parse_mode="HTML",
            )
        else:
            sent = await message.answer(
                "ℹ️ У цьому чаті немає активних тимчасових анрегів."
            )

        await self.auto_cleanup(message, sent)

    async def cmd_force_unreg(self, message: Message):
        """Примусово анрегає юзера (тільки для власника чату або адмінів бота)"""
        user_id = message.from_user.id
        from utils.helpers import get_clean_chat_id

        chat_id = get_clean_chat_id(message.chat.id)

        # Check permission: Bot Admin/Owner OR Chat Owner
        is_bot_staff = self.chat_repo.is_bot_admin(user_id)
        chat_member = await message.chat.get_member(user_id)
        is_chat_owner = chat_member.status == "creator"

        if not (is_bot_staff or is_chat_owner):
            sent = await message.answer(
                "❌ Ця команда тільки для <b>Власника чату</b> або <b>Адміністрації бота</b>.",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        if not message.reply_to_message:
            sent = await message.answer(
                "ℹ️ Використовуйте команду як <b>відповідь</b> на повідомлення юзера, якого треба анрегнути."
            )
            await self.auto_cleanup(message, sent)
            return

        target_id = str(message.reply_to_message.from_user.id)
        target_name = message.reply_to_message.from_user.full_name

        self.chat_repo.add_to_temp_unreg(chat_id, target_id)
        sent = await message.answer(
            f"🔇 Користувача <b>{target_name}</b> примусово анрегнуто в цьому чаті.",
            parse_mode="HTML",
        )
        await self.auto_cleanup(message, sent)

    async def cmd_force_reg(self, message: Message):
        """Примусово регає юзера (тільки для власника чату або адмінів бота)"""
        user_id = message.from_user.id
        from utils.helpers import get_clean_chat_id

        chat_id = get_clean_chat_id(message.chat.id)

        # Check permission: Bot Admin/Owner OR Chat Owner
        is_bot_staff = self.chat_repo.is_bot_admin(user_id)
        chat_member = await message.chat.get_member(user_id)
        is_chat_owner = chat_member.status == "creator"

        if not (is_bot_staff or is_chat_owner):
            sent = await message.answer(
                "❌ Ця команда тільки для <b>Власника чату</b> або <b>Адміністрації бота</b>.",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        if not message.reply_to_message:
            sent = await message.answer(
                "ℹ️ Використовуйте команду як <b>відповідь</b> на повідомлення юзера, якого треба зареєструвати.",
                parse_mode="HTML",
            )
            await self.auto_cleanup(message, sent)
            return

        target_id = str(message.reply_to_message.from_user.id)
        target_name = message.reply_to_message.from_user.full_name

        removed = self.chat_repo.remove_from_unreg(chat_id, target_id)

        if removed:
            sent = await message.answer(
                f"🔔 Користувача <b>{target_name}</b> примусово зареєстровано в цьому чаті.",
                parse_mode="HTML",
            )
        else:
            sent = await message.answer(
                f"ℹ️ Користувач <b>{target_name}</b> і так має активні пінги (або має глобальний анрег).",
                parse_mode="HTML",
            )

        await self.auto_cleanup(message, sent)

    async def on_bot_join(self, event: ChatMemberUpdated):
        """
        Відстежує додавання бота в нові чати (v2.4.2)
        Повідомляє власника про нову групу для перевірки юзербота.
        """
        # Перевіряємо чи це саме додавання (був left/kicked -> став member/admin)
        if event.old_chat_member.status in [
            "left",
            "kicked",
            "restricted",
        ] and event.new_chat_member.status in ["member", "administrator"]:
            chat_title = event.chat.title or "Chat"
            chat_id = event.chat.id
            username = event.chat.username or "private"

            added_by = event.from_user.first_name
            added_by_username = (
                f"@{event.from_user.username}"
                if event.from_user.username
                else str(event.from_user.id)
            )

            # Логуємо
            self.logger.info(
                f"🆕 Бот доданий в чат: {chat_title} ({chat_id}) користувачем {added_by}"
            )

            # Повідомляємо власника
            try:
                msg_text = (
                    f"🆕 <b>Бот додано в новий чат!</b>\n\n"
                    f"📝 Назва: {chat_title}\n"
                    f"🆔 ID: <code>{chat_id}</code>\n"
                    f"🔗 Link: @{username}\n"
                    f"👤 Ким: {added_by} ({added_by_username})\n\n"
                    f"⚠️ <b>Action Required:</b>\n"
                    f"Перевірте чи є там Support Admin (@you_can_try_this)\n"
                    f"Якщо ні - напишіть власнику чату."
                )
                await self.bot.send_message(ADMIN_USER_ID, msg_text, parse_mode="HTML")
            except Exception as e:
                self.logger.error(f"Failed to notify owner about new chat: {e}")

    async def cmd_set_emoji(self, message: Message):
        """Встановлює персональний емодзі для профілю"""
        if message.chat.type != "private":
            sent = await message.answer(
                "⚠️ Цю команду можна використовувати тільки в <b>особистих повідомленнях</b> боту."
            )
            await self.auto_cleanup(message, sent)
            return

        # v2.10.16: Перевірка преміуму на самому початку
        is_premium = self.premium_repo.has_premium(message.from_user.id)
        if not is_premium:
            sent = await message.answer(
                l10n.format_value("emoji_pack.no_premium"), parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent)
            return

        from utils.helpers import extract_emoji_info, render_emoji

        # 1. Спроба витягти преміум-емодзі або звичайний
        info = extract_emoji_info(message)
        custom_id = info.get("custom_id")
        emoji_val = info.get("emoji")

        if custom_id:
            msg_status = await message.answer(
                l10n.format_value("emoji_pack.cloning"), parse_mode="HTML"
            )

            # ВАЖЛИВО: Бот може використовувати будь-які преміум-емодзі в повідомленнях,
            # навіть якщо вони не з його паку. Тому просто зберігаємо оригінальний ID.
            try:
                print("[SETEMOJI] Saving original emoji ID:", custom_id)

                # Перевіряємо, чи ВЛАСНИК бота має Premium (не сам бот!)
                from config import ADMIN_USER_ID

                owner_has_premium = self.premium_repo.has_premium(ADMIN_USER_ID)
                print(
                    f"[SETEMOJI] Bot owner (ID={ADMIN_USER_ID}) premium status: {owner_has_premium}"
                )

                if not owner_has_premium:
                    print("[SETEMOJI] ⚠️ WARNING: Bot owner doesn't have Premium!")
                    await msg_status.edit_text(
                        "⚠️ <b>Увага!</b>\n\n"
                        "Власник бота <b>не має Telegram Premium</b>, тому кастомні емодзі "
                        "<b>не будуть відображатися</b> в пінгах.\n\n"
                        "Емодзі збережено, але буде показуватися як звичайне ✨.\n\n"
                        "Щоб кастомні емодзі працювали, потрібно:\n"
                        "1. Купити Premium для власника бота\n"
                        "2. Або використовувати звичайні емодзі",
                        parse_mode="HTML",
                    )
                    return

                if self.emoji_service:
                    try:
                        # v2.10.8: Тепер реально клонуємо в наш пак
                        new_id = await self.emoji_service.clone_emoji(
                            custom_id, message.from_user.id
                        )
                        if new_id:
                            custom_id = new_id
                            print(
                                f"[SETEMOJI] Successfully cloned! New ID: {custom_id}"
                            )
                        else:
                            print(
                                f"[SETEMOJI] Cloning returned None, using original ID: {custom_id}"
                            )

                    except Exception as e:
                        print(f"[SETEMOJI] Warning: Could not clone: {e}")

                # v2.10.12: Зберігаємо КЛОНОВАНИЙ ID в налаштування користувача
                self.chat_repo.set_user_setting(
                    message.from_user.id,
                    "personal_emoji",
                    f"tg-emoji:{custom_id}",
                )

                print(f"[SETEMOJI] ✅ Saved successfully!")

                # Рендеримо через HTML (так надійніше і працює у користувача)
                emoji_html = render_emoji(f"tg-emoji:{custom_id}")
                success_text = l10n.format_value("emoji_pack.success")

                await msg_status.edit_text(
                    f"{success_text} {emoji_html}\nВін буде відображатися біля вашого імені.",
                    parse_mode="HTML",
                )
            except Exception as e:
                import html

                self.logger.error(f"Error cloning emoji: {e}", exc_info=True)
                await msg_status.edit_text(
                    f"❌ Критична помилка при клонуванні:\n<code>{html.escape(str(e))}</code>\n\n"
                    "Спробуйте пізніше або інший емодзі.",
                    parse_mode="HTML",
                )
            return

        # 2. Якщо просто !setemoji (без аргументів)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            # Перевіряємо преміум бота (тільки власники преміуму можуть обирати з колекції)
            is_premium = self.premium_repo.has_premium(message.from_user.id)
            if is_premium:
                # v2.10.16: Завантажуємо інформацію про бота, якщо її ще немає (Більш надійна перевірка)
                if not getattr(self, "me", None) and message.bot:
                    self.me = await message.bot.get_me()

                pack = self.chat_repo.emoji_packs.get_active_pack()
                bot_info = getattr(self, "me", None)
                if pack and bot_info:
                    # v2.10.9: Перевіряємо, чи пак належить поточному боту
                    if (
                        not pack["name"]
                        .lower()
                        .endswith(f"_by_{bot_info.username}".lower())
                    ):
                        self.logger.warning(
                            f"Active pack {pack['name']} doesn't match bot {self.me.username}. Ignoring."
                        )
                        # If the pack doesn't belong to this bot, treat it as if no pack is active
                        pack = None

                if not pack:
                    await message.answer(
                        l10n.format_value("emoji_pack.no_emojis"), parse_mode="HTML"
                    )
                    return

                emojis = self.chat_repo.emoji_packs.get_all_cloned_emojis()
                if not emojis:
                    await message.answer(
                        l10n.format_value("emoji_pack.no_emojis"), parse_mode="HTML"
                    )
                    return

                # Показуємо останніх 40
                emojis = emojis[-40:]

                text = l10n.format_value("emoji_pack.choose") + "\n\n"
                kb = []
                row = []
                for i, item in enumerate(emojis, 1):
                    eid = item["id"]
                    alt = item["alt"]
                    text += f'<b>{i}.</b> <tg-emoji emoji-id="{eid}">{alt}</tg-emoji>  '
                    if i % 4 == 0:
                        text += "\n"

                    row.append(
                        InlineKeyboardButton(
                            text=str(i), callback_data=f"set_emoji:{eid}"
                        )
                    )
                    if len(row) == 5:
                        kb.append(row)
                        row = []
                if row:
                    kb.append(row)

                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                    parse_mode="HTML",
                )
                return

        emoji = emoji_val.strip()

        if emoji.lower() == "none":
            self.chat_repo.set_user_setting(message.from_user.id, "personal_emoji", "")
            await message.answer("✅ Персональний емодзі видалено.")
            return

        # Валідація: не більше 10 символів
        if len(emoji) > 10:
            await message.answer(
                "❌ Занадто довгий текст. Будь ласка, використовуйте один емодзі."
            )
            return

        self.chat_repo.set_user_setting(message.from_user.id, "personal_emoji", emoji)
        await message.answer(
            f"✅ Персональний емодзі встановлено: {emoji}\nВін буде відображатися біля вашого імені.",
            parse_mode="HTML",
        )

    async def callback_select_emoji(self, callback: CallbackQuery):
        """Обробляє вибір емодзі з колекції"""
        emoji_id = callback.data.split(":")[1]

        # Перевіряємо преміум ще раз (про всяк випадок)
        if not self.premium_repo.has_premium(callback.from_user.id):
            await callback.answer(
                "❌ Ця функція тільки для Premium користувачів.", show_alert=True
            )
            return

        # Зберігаємо
        self.chat_repo.set_user_setting(
            callback.from_user.id, "personal_emoji", f"tg-emoji:{emoji_id}"
        )

        # Рендеримо для підтвердження
        emoji_html = render_emoji(f"tg-emoji:{emoji_id}")
        await callback.message.edit_text(
            f"✅ Персональний емодзі встановлено: {emoji_html}\nВін буде відображатися біля вашого імені.",
            parse_mode="HTML",
        )
        await callback.answer("Встановлено! ✨")
