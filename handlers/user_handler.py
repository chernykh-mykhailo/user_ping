"""
User handlers - команди користувача (SRP)
"""
import logging
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from config import PREMIUM_PLANS, FEEDBACK_BOT, PROJECTS_CHANNEL
from __version__ import __version__


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
        self.router.message(Command("help", "start"))(self.cmd_help)
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
        
        # Premium
        self.router.message(Command("balance"))(self.cmd_balance)
    
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
            "Оберіть розділ для детальної інформації:\n\n"
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
        
        await message.answer(help_text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    
    async def callback_help_section(self, callback: CallbackQuery):
        """Обробляє вибір розділу довідки"""
        section = callback.data.replace("help_", "")
        
        # Кнопка "Назад"
        back_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="help_main")]
        ])
        
        if section == "main":
            await callback.message.edit_text(
                f"<b>📋 Довідка бота v{__version__}</b>\n\n"
                "Оберіть розділ для детальної інформації:\n\n"
                "📢 <b>Пінги</b> — Виклики користувачів\n"
                "🎯 <b>Тригери</b> — Вибіркові виклики груп\n"
                "🎮 <b>Панель ролей</b> — Самореєстрація\n"
                "📝 <b>Шаблони</b> — Збережені тексти\n"
                "⚙️ <b>Керування</b> — Адмін-команди\n"
                "👑 <b>Premium</b> — Преміум функції\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💬 Зв'язок: /feedback\n"
                f"📢 Проекти: <a href='{PROJECTS_CHANNEL}'>Канал</a>",
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
                "<b>Базові виклики:</b>\n"
                "• <code>!кнагє</code> або /all [текст] — Заклик усіх\n"
                "• <code>!емодзі</code> або /emoji [текст] — Заклик емодзі\n"
                "• <code>!адміни</code> або /admins [текст] — Заклик адмінів\n"
                "• <code>!хтось</code> або /anybody [текст] — Випадковий учасник\n"
                "• <code>!стоп</code> або /stop — Зупинити виклик\n\n"
                "<b>Налаштування:</b>\n"
                "• <code>!анрег</code> або /unreg — Вимкнути пінги (тимчасово)\n"
                "• <code>!суперанрег</code> або /superunreg — Вимкнути назавжди (Premium)\n"
                "• <code>!рег</code> або /reg — Увімкнути пінги назад"
            )
            await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
        
        elif section == "triggers":
            text = (
                "<b>🎯 Тригери викликів</b>\n\n"
                "<i>Вибіркові виклики груп користувачів</i>\n\n"
                "<b>Управління:</b>\n"
                "• <code>!calls</code> — Список тригерів\n"
                "• <code>!addcall назва емодзі</code> — Створити тригер\n"
                "  Приклад: <code>!addcall croco 🐊</code>\n"
                "• <code>!delcall назва</code> — Видалити тригер\n"
                "  Приклад: <code>!delcall croco</code>\n"
                "• <code>!callinfo назва</code> — Інфо про тригер\n\n"
                "<b>Користувачі:</b>\n"
                "• <code>!adduser назва</code> — Додати (у відповідь)\n"
                "• <code>!deluser назва</code> — Видалити (у відповідь)\n\n"
                "<b>Виклик:</b>\n"
                "• <code>!назва</code> — Викликати тригер\n"
                "  Приклад: <code>!croco</code>"
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
            text = (
                "<b>⚙️ Керування</b>\n\n"
                "<b>Базові команди:</b>\n"
                "• <code>!збір</code> або /sync — Оновити базу користувачів\n"
                "• <code>!стата</code> або /stats — Статистика чату\n\n"
                "<b>Адмін-команди Premium:</b>\n"
                "• /admin_grant_premium <user_id> <days>\n"
                "• /admin_revoke_premium <user_id>\n"
                "• /admin_add_payment <user_id> <amount>\n"
                "• /admin_payments <user_id>"
            )
            await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
        
        elif section == "premium":
            text = (
                f"<b>👑 Premium</b>\n\n"
                f"<b>Переваги:</b>\n"
                f"• 🚫 /superunreg — Постійне вимкнення пінгів\n"
                f"• 🎯 Доступ до всіх функцій\n\n"
                f"<b>Ціни:</b>\n"
                f"⭐ Місяць: {PREMIUM_PLANS['month'].price} Stars ({PREMIUM_PLANS['month'].days} днів)\n"
                f"⭐ Рік: {PREMIUM_PLANS['year'].price} Stars ({PREMIUM_PLANS['year'].days} днів)\n\n"
                f"<b>Команди:</b>\n"
                f"• /premium — Купити Premium\n"
                f"• /balance — Перевірити статус\n"
                f"• /refund — Повернення коштів"
            )
            await callback.message.edit_text(text, reply_markup=back_button, parse_mode="HTML")
        
        await callback.answer()

    
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
        await message.answer(feedback_text, parse_mode="HTML", disable_web_page_preview=True)
    
    async def cmd_unreg(self, message: Message):
        """Тимчасово вимикає пінги"""
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        
        added = self.chat_repo.add_to_temp_unreg(chat_id, user_id)
        
        if added:
            await message.answer(
                "🔕 Пінги вимкнено. Напишіть будь-що в чат, щоб увімкнути назад."
            )
        else:
            await message.answer("ℹ️ Ви вже в режимі тимчасового анрегу.")
    
    async def cmd_superunreg(self, message: Message):
        """Постійно вимикає пінги (тільки з Premium)"""
        user_id = str(message.from_user.id)
        
        # Перевірка преміуму
        if not self.premium_repo.has_premium(user_id):
            await message.answer(
                "🚫 <b>Доступ заборонено</b>\n\n"
                "Команда /superunreg доступна тільки з 👑 Premium статусом.\n\n"
                "Купити Premium: /premium",
                parse_mode="HTML"
            )
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        added = self.chat_repo.add_to_super_unreg(chat_id, user_id)
        
        if added:
            await message.answer(
                "🚫 Пінги вимкнено назавжди. Використайте /reg або !рег для повернення."
            )
        else:
            await message.answer("ℹ️ Ви вже в режимі постійного анрегу.")
    
    async def cmd_reg(self, message: Message):
        """Увімкнює пінги назад"""
        chat_id = get_clean_chat_id(message.chat.id)
        user_id = str(message.from_user.id)
        
        removed = self.chat_repo.remove_from_unreg(chat_id, user_id)
        
        if removed:
            await message.answer(
                "✅ Пінги увімкнено! Тепер ви знову отримуватимете сповіщення."
            )
        else:
            await message.answer("ℹ️ Ви і так отримуєте пінги.")
    
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
        
        await message.answer(balance_text, parse_mode="HTML")
