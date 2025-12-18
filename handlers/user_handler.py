"""
User handlers - команди користувачів (SRP)
"""
import logging
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
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
        """Показує довідку"""
        help_text = (
            "<b>📋 Команди бота:</b>\n\n"
            "<b>Пінги:</b>\n"
            "📢 <code>!кнагє</code> або /all [текст] — Заклик усіх\n"
            "🎭 <code>!емодзі</code> або /emoji [текст] — Заклик емодзі\n\n"
            "<b>Керування:</b>\n"
            "🔄 <code>!збір</code> або /sync — Оновити базу\n"
            "📊 <code>!стата</code> або /stats — Статистика\n\n"
            "<b>Налаштування пінгів:</b>\n"
            "🔕 <code>!анрег</code> або /unreg — Вимкнути пінги (до наступного повідомлення)\n"
            "🚫 <code>!суперанрег</code> або /superunreg — Вимкнути назавжди (тільки з 👑 Premium)\n"
            "✅ <code>!рег</code> або /reg — Увімкнути пінги назад\n\n"
            "<b>👑 Premium:</b>\n"
            "💳 /premium — Купити Premium статус\n"
            "💰 /balance — Перевірити статус Premium\n\n"
            f"<i>💡 Premium дає доступ до /superunreg\n"
            f"⭐ Місяць: {PREMIUM_PLANS['month'].price} Stars | "
            f"Рік: {PREMIUM_PLANS['year'].price} Stars</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💬 Зв'язок: /feedback\n"
            f"📢 Наші проекти: <a href='{PROJECTS_CHANNEL}'>Telegram канал</a>\n\n"
            f"<i>🤖 Версія: {__version__}</i>"
        )
        await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)
    
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
