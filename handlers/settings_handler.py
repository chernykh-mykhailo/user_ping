"""
Settings Handler - налаштування чату (SRP)
"""
import logging
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from aiogram.exceptions import TelegramBadRequest
from config import PING_LIMITS

class SettingsHandler(BaseHandler):
    """
    Обробляє налаштування чату
    """
    
    def __init__(self, chat_repo, premium_repo):
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери налаштувань"""
        self.router.message(Command("settings"))(self.cmd_settings)
        self.router.callback_query(F.data == "settings_main")(self.callback_settings_main)
        self.router.callback_query(F.data.startswith("toggle_"))(self.callback_toggle_setting)
        self.router.callback_query(F.data == "change_speed")(self.callback_change_speed)
        self.router.callback_query(F.data.startswith("set_speed_"))(self.callback_set_speed)
    
    async def _is_admin(self, chat_id: int, user_id: int, bot) -> bool:
        """Перевіряє права адміністратора"""
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in ['creator', 'administrator']
        except:
            return True
            
    async def cmd_settings(self, message: Message):
        """Відкриває меню налаштувань"""
        if not await self._is_admin(message.chat.id, message.from_user.id, message.bot):
            return
            
        await self._show_settings_menu(message)

    async def callback_settings_main(self, callback: CallbackQuery):
        """Повертається в головне меню налаштувань"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
            return
        
        await self._show_settings_menu(callback.message, is_edit=True)
        try:
            await callback.answer()
        except TelegramBadRequest:
            pass

    async def _show_settings_menu(self, message: Message, is_edit: bool = False):
        """Відображає меню налаштувань"""
        chat_id = get_clean_chat_id(message.chat.id)
        
        # Отримуємо поточні налаштування (default: True)
        pin_enabled = self.chat_repo.get_setting(chat_id, "pin_enabled", True)
        first_msg_stop = self.chat_repo.get_setting(chat_id, "first_msg_stop", True)
        admin_stop_report = self.chat_repo.get_setting(chat_id, "admin_stop_report", True)
        
        # Отримуємо поточну швидкість
        current_delay = self.chat_repo.get_setting(chat_id, "ping_delay", PING_LIMITS["default_delay"])
        
        # Визначаємо текст кнопки швидкості
        speed_text = "⚡️ Turbo (0.1s)"
        if current_delay >= 1.0:
            speed_text = "🐢 Slow (1.0s)"
        elif current_delay >= 0.5:
            speed_text = "🚶 Normal (0.5s)"
        
        # Формуємо клавіатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if pin_enabled else '❌'} Закріплювати повідомлення", 
                    callback_data="toggle_pin_enabled"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if first_msg_stop else '❌'} Кнопка Стоп (тільки 1-ше)", 
                    callback_data="toggle_first_msg_stop"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if admin_stop_report else '❌'} Показувати хто зупинив", 
                    callback_data="toggle_admin_stop_report"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Швидкість: {speed_text}", 
                    callback_data="change_speed"
                )
            ],
            [
                InlineKeyboardButton(text="◀️ Закрити", callback_data="delete_message") # Need delete handler or generic
            ]
        ])
        
        text = (
            "<b>⚙️ Налаштування чату</b>\n\n"
            "Натисніть на кнопку, щоб змінити налаштування:"
        )
        
        if is_edit:
            try:
                await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                pass
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    async def callback_toggle_setting(self, callback: CallbackQuery):
        """Перемикає налаштування"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
            try:
                await callback.answer("❌ Тільки адміни!", show_alert=True)
            except TelegramBadRequest:
                pass
            return
            
        setting_key = callback.data.replace("toggle_", "")
        chat_id = get_clean_chat_id(callback.message.chat.id)
        
        # Отримуємо поточне значення (default: True для всіх наших налаштувань)
        current_value = self.chat_repo.get_setting(chat_id, setting_key, True)
        new_value = not current_value
        
        self.chat_repo.set_setting(chat_id, setting_key, new_value)
        
        try:
            await callback.answer(f"✅ Змінено на {'Увімкнено' if new_value else 'Вимкнено'}")
        except TelegramBadRequest:
            pass
            
        # Оновлюємо меню
        await self._show_settings_menu(callback.message, is_edit=True)

    async def callback_change_speed(self, callback: CallbackQuery):
        """Показує меню вибору швидкості"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
            return
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡️ Turbo (0.1s)", callback_data="set_speed_0.1"),
                InlineKeyboardButton(text="🚀 Fast (0.3s)", callback_data="set_speed_0.3")
            ],
            [
                InlineKeyboardButton(text="🚶 Normal (0.5s)", callback_data="set_speed_0.5"),
                InlineKeyboardButton(text="🐢 Slow (1.0s)", callback_data="set_speed_1.0")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")
            ]
        ])
        
        try:
            await callback.message.edit_text(
                "<b>🚀 Оберіть швидкість пінгування:</b>\n\n"
                "⚠️ <i>Turbo режим (0.1s) найшвидший, але є ризик блокування якщо часто використовувати.</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except:
            pass

    async def callback_set_speed(self, callback: CallbackQuery):
        """Встановлює швидкість"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
            return
            
        speed = float(callback.data.replace("set_speed_", ""))
        chat_id = get_clean_chat_id(callback.message.chat.id)
        
        # Валідація через ліміти
        if speed < PING_LIMITS["min_delay"]:
            speed = PING_LIMITS["min_delay"]
        if speed > PING_LIMITS["max_delay"]:
            speed = PING_LIMITS["max_delay"]
            
        self.chat_repo.set_setting(chat_id, "ping_delay", speed)
        
        try:
            await callback.answer(f"✅ Швидкість встановлено: {speed}s")
        except TelegramBadRequest:
            pass
            
        await self._show_settings_menu(callback.message, is_edit=True)
