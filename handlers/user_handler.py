"""
User handlers - команди користувача (SRP)
"""
import logging
import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
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
        
        # Unreg/Reg
        self.router.message(Command("unreg"))(self.cmd_unreg)
        self.router.message(F.text.regexp(r'^!?анрег', flags=0))(self.cmd_unreg)
        
        self.router.message(Command("superunreg"))(self.cmd_superunreg)
        self.router.message(F.text.regexp(r'^!?суперанрег', flags=0))(self.cmd_superunreg)
        
        self.router.message(Command("reg"))(self.cmd_reg)
        self.router.message(F.text.regexp(r'^!?рег', flags=0))(self.cmd_reg)
        
        # Global Unreg (v1.5.0+)
        self.router.message(Command("gunreg"))(self.cmd_global_unreg)
        self.router.message(F.text.regexp(r'^!?ганрег', flags=0))(self.cmd_global_unreg)
        
        self.router.message(Command("gsuperunreg"))(self.cmd_global_superunreg)
        self.router.message(F.text.regexp(r'^!?гсуперанрег', flags=0))(self.cmd_global_superunreg)
        
        self.router.message(Command("greg"))(self.cmd_global_reg)
        self.router.message(F.text.regexp(r'^!?грег', flags=0))(self.cmd_global_reg)
        
        # Premium
        self.router.message(Command("balance"))(self.cmd_balance)
    
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
            "👑 <b>Premium</b> — Преміум функції\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💬 Зв'язок: /feedback\n"
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
            
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        name = message.from_user.first_name or "Учасник"
        
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
                    "<b>⚙️ Керування чатом</b>\n\n"
                    "• <code>/settings</code> — Головні налаштування чату\n"
                    "• <code>!стата</code> або /stats — Детальна статистика\n"
                    "• <code>!збір</code> або /sync — Оновити базу учасників\n"
                    "• <code>!адміни</code> — Пінганути всіх адмінів чату\n"
                )
                
                if is_admin or is_owner or is_super:
                    text += (
                        "\n👨‍💻 <b>Bot Staff Panel:</b>\n"
                        "• /admin_list — Весь склад персоналу\n"
                        "• /admin_help — Керування Premium (для Адмінів)\n"
                    )
                    
                if is_owner or is_super:
                    text += (
                        "\n👑 <b>Owner Features:</b>\n"
                        "• /apanel — Глобальна панель бота\n"
                        "• /ub_login — Керування Юзерботом\n"
                        "• /mod_add [ID] — Додати модератора\n"
                    )
                    
                if is_super:
                    text += (
                        "\n⭐️ <b>SuperOwner Only:</b>\n"
                        "• /owner_add [ID] — Додати співвласника\n"
                        "• /owner_del [ID] — Видалити власника\n"
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
        """Постійно вимикає пінги (тільки з Premium)"""
        user_id = str(message.from_user.id)
        
        # Перевірка преміуму
        if not self.premium_repo.has_premium(user_id):
            sent = await message.answer(
                "👑 <b>PREMIUM REQUIRED</b>\n\n"
                "Функція <b>SuperUnreg</b> дозволяє назавжди зникнути з радарів пінгу в цьому чаті.\n\n"
                "✨ <b>Переваги Premium:</b>\n"
                "• Повний ігнор будь-яких викликів\n"
                "• Пріоритет в обробці команд\n"
                "• Підтримка розвитку проекту\n\n"
                "💎 Придбати: /premium",
                parse_mode="HTML"
            )
            await self.auto_cleanup(message, sent, custom_delay=30)
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
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

    # === Global Unreg Logic ===

    async def cmd_global_unreg(self, message: Message):
        """Вимкнення пінгів у всіх чатах відразу"""
        user_id = str(message.from_user.id)
        
        self.chat_repo.add_to_global_unreg(user_id, is_super=False)
        
        sent = await message.answer(
            "🔇 <b>Глобальний анрег активовано!</b>\n\n"
            "Ви більше не отримуватимете пінги в <b>жодному</b> чаті, де є цей бот.\n"
            "<i>(Пінг увімкнеться автоматично, якщо ви напишете в будь-якому чаті)</i>",
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
