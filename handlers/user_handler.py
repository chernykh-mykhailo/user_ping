"""
User handlers - команди користувача (SRP)
"""
import logging
import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatMemberUpdated
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id, get_user_name
from config import (
    PREMIUM_PLANS, CHAT_PREMIUM_PLANS, FEEDBACK_BOT, 
    PROJECTS_CHANNEL, REFERRAL_BONUS_SIGNUP, REFERRAL_BONUS_PREMIUM,
    ADMIN_USER_ID
)
from __version__ import __version__
from aiogram.exceptions import TelegramBadRequest


class UserHandler(BaseHandler):
    """
    Обробляє команди користувачів
    Single Responsibility: тільки користувацькі команди
    """
    
    def __init__(self, chat_repo, premium_repo):
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери користувачів"""
        # Help
        self.router.message(Command("help"))(self.cmd_help)
        self.router.message(Command("start"))(self.cmd_start)  # Окремо для реферальних посилань
        self.router.message(F.text.regexp(r'^!?(хелп|допомога)', flags=0))(self.cmd_help)
        self.router.callback_query(F.data.startswith("help_"))(self.callback_help_section)
        
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
        self.router.message(F.text.regexp(r'^\s*!?анрег(\s|$)', flags=re.IGNORECASE))(self.cmd_unreg)
        
        self.router.message(Command("superunreg"))(self.cmd_superunreg)
        self.router.message(F.text.regexp(r'^\s*!?суперанрег(\s|$)', flags=re.IGNORECASE))(self.cmd_superunreg)
        
        self.router.message(Command("reg"))(self.cmd_reg)
        self.router.message(F.text.regexp(r'^\s*!?рег(\s|$)', flags=re.IGNORECASE))(self.cmd_reg)
        
        # Global Unreg (v1.5.0+)
        self.router.message(Command("gunreg"))(self.cmd_global_unreg)
        self.router.message(F.text.regexp(r'^\s*!?ганрег(\s|$)', flags=re.IGNORECASE))(self.cmd_global_unreg)
        
        self.router.message(Command("gsuperunreg"))(self.cmd_global_superunreg)
        self.router.message(F.text.regexp(r'^\s*!?гсуперанрег(\s|$)', flags=re.IGNORECASE))(self.cmd_global_superunreg)
        
        self.router.message(Command("greg"))(self.cmd_global_reg)
        self.router.message(F.text.regexp(r'^\s*!?грег(\s|$)', flags=re.IGNORECASE))(self.cmd_global_reg)
        
        # Premium
        # Premium
        self.router.message(Command("balance"))(self.cmd_balance)
        self.router.message(Command("spanreg"))(self.cmd_superunreg)
    
    async def cmd_start(self, message: Message):
        """Обробляє /start з реферальними посиланнями"""
        from config import REFERRAL_BONUS_SIGNUP
        
        # Перевіряємо чи є реферальний код
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("ref_"):
            referrer_id = args[1].replace("ref_", "")
            referred_id = str(message.from_user.id)
            
            # Не можна реферити самого себе
            if referrer_id == referred_id:
                await self.cmd_help(message)
                return
            
            # Відстежуємо реферала
            from core import ReferralRepository
            from core.database import JSONDatabase
            from config import DB_FILE
            
            db = JSONDatabase(DB_FILE)
            referral_repo = ReferralRepository(db)
            
            if referral_repo.track_referral(referrer_id, referred_id):
                # Нараховуємо бонус рефереру
                from core import PremiumRepository
                premium_repo = PremiumRepository(db)
                premium_repo.grant_premium(referrer_id, REFERRAL_BONUS_SIGNUP)
                referral_repo.add_bonus_days(referrer_id, REFERRAL_BONUS_SIGNUP)
                
                # Повідомляємо нового користувача
                await message.answer(
                    f"🎉 <b>Вітаємо!</b>\n\n"
                    f"Ви приєдналися за реферальним посиланням!\n"
                    f"Ваш друг отримав +{REFERRAL_BONUS_SIGNUP} днів Premium 🎁\n\n"
                    f"Купіть Premium і він отримає ще більше бонусів!\n"
                    f"/premium",
                    parse_mode="HTML"
                )
                
                # Повідомляємо реферера
                try:
                    await message.bot.send_message(
                        int(referrer_id),
                        f"🎁 <b>Новий реферал!</b>\n\n"
                        f"👤 {message.from_user.first_name} приєднався за вашим посиланням!\n"
                        f"💎 Ви отримали +{REFERRAL_BONUS_SIGNUP} днів Premium\n\n"
                        f"<i>Продовжуйте ділитися посиланням!</i>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to notify referrer: {e}")
                
                return
        
        # Якщо немає реферального коду - показуємо help
        await self.cmd_help(message)
    
    async def cmd_help(self, message: Message):
        """Показує головне меню довідки"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 Пінги", callback_data="help_pings"),
                InlineKeyboardButton(text="🎯 Тригери", callback_data="help_triggers")
            ],
            [
                InlineKeyboardButton(text="🎮 Панель ролей", callback_data="help_roles"),
                InlineKeyboardButton(text="📝 Шаблони", callback_data="help_templates")
            ],
            [
                InlineKeyboardButton(text="⚙️ Керування", callback_data="help_management"),
                InlineKeyboardButton(text="👑 Premium", callback_data="help_premium")
            ]
        ])
        
        help_text = (
            f"<b>📋 Довідка бота v{__version__}</b>\n\n"
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
        
        sent = await message.answer(help_text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
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
        if text.startswith(('/', '!')):
            return
        
        # v2.6.3: Перевіряємо слова-команди без префіксів (анрег, рег, всі і т.д.)
        word_commands = [
            'анрег', 'рег', 'суперанрег', 'ганрег', 'гсуперанрег', 'грег',
            'всі', 'хтось', 'стата', 'фулстата', 'стоп', 
            'unreg', 'reg', 'superunreg', 'gunreg', 'gsuperunreg', 'greg',
            'all', 'stats', 'fullstats', 'stop', 'help',
            'адміни', 'admins', 'збір', 'sync', 'преміум', 'premium'
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
            user_id=message.from_user.id
        )
        
        # Оновлюємо ім'я та знімаємо тимчасовий анрег
        self.chat_repo.save_user(chat_id, user_id, name, update_unreg=True)
    
    async def callback_help_section(self, callback: CallbackQuery):
        """Обробляє вибір розділу довідки"""
        section = callback.data.replace("help_", "")
        self.logger.info(f"Help section requested: {section} by {callback.from_user.id}")
        
        try:
            await callback.answer()
        except:
            pass
        
        # Кнопка "Назад"
        back_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_main")]
        ])
        
        try:
            if section == "main":
                help_text = (
                    f"<b>📋 Довідка бота v{__version__}</b>\n\n"
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
                await callback.message.edit_text(
                    help_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="📢 Пінги", callback_data="help_pings"),
                            InlineKeyboardButton(text="🎯 Тригери", callback_data="help_triggers")
                        ],
                        [
                            InlineKeyboardButton(text="🎮 Панель ролей", callback_data="help_roles"),
                            InlineKeyboardButton(text="📝 Шаблони", callback_data="help_templates")
                        ],
                        [
                            InlineKeyboardButton(text="⚙️ Керування", callback_data="help_management"),
                            InlineKeyboardButton(text="👑 Premium", callback_data="help_premium")
                        ]
                    ]),
                    parse_mode="HTML",
                    disable_web_page_preview=True
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
                await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
            
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
                await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
            
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
                await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
            
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
                    "1. Напишіть: \"Збори о 18:00\"\n"
                    "2. Відповідайте: <code>!addcpattern meeting</code>\n"
                    "3. Використайте: <code>/all meeting</code>"
                )
                await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
            
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
                    [InlineKeyboardButton(text="⚙️ Налаштування чату", callback_data="settings_location_chat_0_0")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="help_main")]
                ]
                # Ховаємо кнопку налаштувань в ЛС, бо вона там не працює
                if callback.message.chat.type == "private":
                    mgmt_kb.pop(0)

                await callback.message.edit_text(
                    text, 
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=mgmt_kb), 
                    parse_mode="HTML"
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
                await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
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
        sent = await message.answer(feedback_text, parse_mode="HTML", disable_web_page_preview=True)
        await self.auto_cleanup(message, sent)
    
    async def cmd_unreg(self, message: Message):
        """Тимчасово вимикає пінги з можливістю авто-видалення"""
        if message.chat.type not in ["group", "supergroup"]:
            return
            
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        self.logger.info(f"Команда анрег від {user_id} у чаті {chat_id}")
        
        added = self.chat_repo.add_to_temp_unreg(chat_id, user_id)
        
        # Debug: verify it was actually saved
        chat_data = self.chat_repo.get_chat_data(chat_id)
        current_temp = chat_data.get("temp_unreg", [])
        self.logger.info(f"[UNREG DEBUG] added={added}, temp_unreg now: {current_temp}")
        
        if added:
            sent = await self._safe_answer(
                message, 
                "🔕 Пінги вимкнено. Напишіть будь-що в чат, щоб увімкнути назад."
            )
            await self.auto_cleanup(message, sent)
        else:
            sent = await self._safe_answer(message, "ℹ️ Ви вже в режимі тимчасового анрегу.")
            await self.auto_cleanup(message, sent)
    
    async def cmd_superunreg(self, message: Message):
        """Постійно вимикає пінги (Premium або Chat Premium)"""
        user_id = str(message.from_user.id)
        chat_id = get_clean_chat_id(message.chat.id)
        self.logger.info(f"Команда SUPERUNREG від {user_id} у чаті {chat_id}")
        
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
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return
        
        added = self.chat_repo.add_to_super_unreg(chat_id, user_id)
        
        if added:
            sent = await message.answer(
                "🛡 <b>SUPER UNREG: АКТИВОВАНО</b>\n\n"
                "💎 Ви успішно використали свій <b>Premium</b> статус. Тепер учасники не зможуть пінгнути вас у цьому чаті, навіть якщо ви будете активні.\n\n"
                "<i>Повернутися: /reg</i>",
                parse_mode="HTML"
            )
        else:
            sent = await message.answer("ℹ️ <b>Ви вже захищені SuperUnreg у цьому чаті.</b>", parse_mode="HTML")
        
        # SuperUnreg повідомлення висять довше (60с), щоб всі бачили статус
        await self.auto_cleanup(message, sent, custom_delay=60)
    
    async def cmd_reg(self, message: Message):
        """Увімкнює пінги назад"""
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        
        removed = self.chat_repo.remove_from_unreg(chat_id, user_id)
        
        if removed:
            sent = await message.answer(
                "✅ Пінги увімкнено! Тепер ви знову отримуватимете сповіщення."
            )
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
            balance_text = (
                "❌ <b>У вас немає Premium</b>\n\n"
                "Купити Premium: /premium"
            )
        
        sent = await message.answer(balance_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent)

    async def cmd_start(self, message: Message):
        """Обробляє команду /start"""
        # Перевіряємо чи це реферальне посилання
        args = message.text.split()
        if len(args) > 1:
            referrer_id = args[1]
            # Якщо це не ми самі (захист від накрутки)
            if referrer_id != str(message.from_user.id):
                await self._handle_referral(message, referrer_id, str(message.from_user.id))
                return

        start_text = (
            "👋 <b>Вітаю! Ping Bot готовий до роботи!</b>\n\n"
            "📋 <b>Швидкий старт:</b>\n"
            "1️⃣ Зробіть мене <b>адміністратором</b> (для доступу до повідомлень)\n"
            "2️⃣ Виконайте /sync для синхронізації учасників\n"
            "3️⃣ Готово! Тепер можна використовувати /all, /anybody та інші команди\n\n"
            "💡 <i>Синхронізація відбувається автоматично щоночі о 03:00.</i>\n\n"
            "❓ <b>Важливо про синхронізацію:</b>\n"
            "Щоб бот міг бачити <b>всіх</b> учасників (а не тільки тих, хто пише), "
            "потрібно додати нашого технічного адміністратора:\n"
            "👉 @you_can_try_this\n\n"
            "<i>Він допоможе зібрати повну базу користувачів для коректної роботи команд. "
            "Бот ніколи не турбуватиме вас без команди.</i>\n\n"
            "Всі команди: /help"
        )
        sent = await message.answer(start_text, parse_mode="HTML")
        await self.auto_cleanup(message, sent, custom_delay=60)

    # === Global Unreg Logic ===

    async def cmd_global_unreg(self, message: Message):
        """Вимкнення пінгів у всіх чатах відразу"""
        user_id = str(message.from_user.id)
        
        self.chat_repo.add_to_global_unreg(user_id, is_super=False)
        
        sent = await message.answer(
            "🌍 <b>Глобальний анрег активовано</b>\n\n"
            "Пінги вимкнені у <b>всіх чатах</b> з ботом.\n"
            "<i>Автоувімкнення при наступному повідомленні</i>",
            parse_mode="HTML"
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
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return

        self.chat_repo.add_to_global_unreg(user_id, is_super=True)
        
        sent = await message.answer(
            "🌌 <b>GLOBAL SUPER UNREG</b>\n\n"
            "✨ <b>Статус: УЛЬТИМАТИВНИЙ ЗАХИСТ</b>\n"
            "Ви повністю приховані від усіх типів пінгування (all, active, writers тощо) в усіх чатах, де присутній бот.\n\n"
            "<i>Зняти захист: /greg</i>",
            parse_mode="HTML"
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

    async def on_bot_join(self, event: ChatMemberUpdated):
        """
        Відстежує додавання бота в нові чати (v2.4.2)
        Повідомляє власника про нову групу для перевірки юзербота.
        """
        # Перевіряємо чи це саме додавання (був left/kicked -> став member/admin)
        if event.old_chat_member.status in ["left", "kicked", "restricted"] and \
           event.new_chat_member.status in ["member", "administrator"]:
            
            chat_title = event.chat.title or "Chat"
            chat_id = event.chat.id
            username = event.chat.username or "private"
            
            added_by = event.from_user.first_name
            added_by_username = f"@{event.from_user.username}" if event.from_user.username else str(event.from_user.id)
            
            # Логуємо
            self.logger.info(f"🆕 Бот доданий в чат: {chat_title} ({chat_id}) користувачем {added_by}")
            
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
