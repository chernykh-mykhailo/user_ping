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
        self.router.callback_query(F.data.startswith("settings_location_"))(self.callback_settings_location)
        self.router.callback_query(F.data.startswith("settings_main_"))(self.callback_settings_main)
        self.router.callback_query(F.data.startswith("toggle_"))(self.callback_toggle_setting)
        self.router.callback_query(F.data.startswith("change_speed_"))(self.callback_change_speed)
        self.router.callback_query(F.data.startswith("set_speed_"))(self.callback_set_speed)
    
    async def _is_admin(self, chat_id: int, user_id: int, bot) -> bool:
        """Перевіряє права адміністратора"""
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in ['creator', 'administrator']
        except:
            return True
            
    async def cmd_settings(self, message: Message):
        """Відкриває меню налаштувань - спочатку вибір куди відправити"""
        if not await self._is_admin(message.chat.id, message.from_user.id, message.bot):
            return
        
        user_id = message.from_user.id
        chat_id = get_clean_chat_id(message.chat.id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 В особисті", 
                    callback_data=f"settings_location_dm_{user_id}_{chat_id}"
                ),
                InlineKeyboardButton(
                    text="💬 В чаті", 
                    callback_data=f"settings_location_chat_{user_id}_{chat_id}"
                )
            ]
        ])
        
        await message.answer(
            "⚙️ <b>Де показати налаштування?</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def callback_settings_location(self, callback: CallbackQuery):
        """Обробляє вибір місця для налаштувань"""
        parts = callback.data.split("_")
        # settings_location_dm_123456_789
        location = parts[2]  # dm або chat
        owner_id = int(parts[3])
        original_chat_id = parts[4]
        
        # Перевірка чи це власник кнопки
        if callback.from_user.id != owner_id:
            try:
                await callback.answer("❌ Ці налаштування не для вас!", show_alert=True)
            except TelegramBadRequest:
                pass
            return
        
        if location == "dm":
            # Відправляємо в ЛС
            try:
                await self._show_settings_menu_dm(callback.bot, callback.from_user.id, original_chat_id, owner_id)
                await callback.message.edit_text("✅ Налаштування відправлено в особисті повідомлення!")
            except Exception as e:
                await callback.message.edit_text(
                    "❌ Не вдалось відправити в ЛС. Спочатку напишіть боту /start в приватних повідомленнях."
                )
        else:
            # Показуємо в чаті
            await self._show_settings_menu(callback.message, is_edit=True, owner_id=owner_id, original_chat_id=original_chat_id)
        
        try:
            await callback.answer()
        except TelegramBadRequest:
            pass

    async def callback_settings_main(self, callback: CallbackQuery):
        """Повертається в головне меню налаштувань"""
        # settings_main_owner_chat
        parts = callback.data.split("_")
        owner_id = int(parts[2])
        original_chat_id = parts[3]
        
        # Перевірка власника
        if callback.from_user.id != owner_id:
            try:
                await callback.answer("❌ Ці налаштування не для вас!", show_alert=True)
            except TelegramBadRequest:
                pass
            return
        
        await self._show_settings_menu(callback.message, is_edit=True, owner_id=owner_id, original_chat_id=original_chat_id)
        try:
            await callback.answer()
        except TelegramBadRequest:
            pass

    async def _show_settings_menu(self, message: Message, is_edit: bool = False, owner_id: int = None, original_chat_id: str = None):
        """Відображає меню налаштувань"""
        # Якщо немає original_chat_id - використовуємо chat_id повідомлення
        chat_id = original_chat_id or get_clean_chat_id(message.chat.id)
        
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
        
        # Суфікс для callback_data з owner та chat
        suffix = f"_{owner_id}_{chat_id}" if owner_id else ""
        
        # Формуємо клавіатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if pin_enabled else '❌'} Закріплювати повідомлення", 
                    callback_data=f"toggle_pin_enabled{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if first_msg_stop else '❌'} Кнопка Стоп (тільки 1-ше)", 
                    callback_data=f"toggle_first_msg_stop{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if admin_stop_report else '❌'} Показувати хто зупинив", 
                    callback_data=f"toggle_admin_stop_report{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Швидкість: {speed_text}", 
                    callback_data=f"change_speed{suffix}"
                )
            ],
            [
                InlineKeyboardButton(text="◀️ Закрити", callback_data="delete_message")
            ]
        ])
        
        text = (
            "<b>⚙️ Налаштування чату</b>\n\n"
            "Натисніть на кнопку, щоб змінити налаштування:\n\n"
            "<b>📢 Кастомні виклики:</b>\n"
            "• <code>!addtrigger слово</code> — Додати виклик (текст)\n"
            "• <code>!addemojitrigger слово</code> — Додати виклик (емодзі)\n"
            "• <code>!deltrigger слово</code> — Видалити виклик\n"
            "• <code>!triggers</code> — Список викликів"
        )
        
        if is_edit:
            try:
                await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                pass
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    async def _show_settings_menu_dm(self, bot, user_id: int, chat_id: str, owner_id: int):
        """Відправляє меню налаштувань в ЛС"""
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
        
        suffix = f"_{owner_id}_{chat_id}"
        
        # Формуємо клавіатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if pin_enabled else '❌'} Закріплювати повідомлення", 
                    callback_data=f"toggle_pin_enabled{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if first_msg_stop else '❌'} Кнопка Стоп (тільки 1-ше)", 
                    callback_data=f"toggle_first_msg_stop{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'✅' if admin_stop_report else '❌'} Показувати хто зупинив", 
                    callback_data=f"toggle_admin_stop_report{suffix}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Швидкість: {speed_text}", 
                    callback_data=f"change_speed{suffix}"
                )
            ]
        ])
        
        text = (
            f"<b>⚙️ Налаштування чату {chat_id}</b>\n\n"
            "Натисніть на кнопку, щоб змінити налаштування:\n\n"
            "<b>📢 Кастомні виклики:</b>\n"
            "• <code>!addtrigger слово</code> — Додати виклик (текст)\n"
            "• <code>!addemojitrigger слово</code> — Додати виклик (емодзі)\n"
            "• <code>!deltrigger слово</code> — Видалити виклик\n"
            "• <code>!triggers</code> — Список викликів"
        )
        
        await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")

    async def callback_toggle_setting(self, callback: CallbackQuery):
        """Перемикає налаштування"""
        # toggle_pin_enabled_ownerid_chatid
        parts = callback.data.split("_")
        
        # Перевіряємо чи є owner_id в callback_data
        if len(parts) >= 4:
            # Є owner_id та chat_id
            setting_key = parts[1]  # pin_enabled, first_msg_stop, etc.
            owner_id = int(parts[2])
            chat_id = parts[3]
            
            # Перевірка власника
            if callback.from_user.id != owner_id:
                try:
                    await callback.answer("❌ Ці налаштування не для вас!", show_alert=True)
                except TelegramBadRequest:
                    pass
                return
        else:
            # Старий формат без owner_id
            if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
                try:
                    await callback.answer("❌ Тільки адміни!", show_alert=True)
                except TelegramBadRequest:
                    pass
                return
            setting_key = callback.data.replace("toggle_", "")
            chat_id = get_clean_chat_id(callback.message.chat.id)
            owner_id = None
        
        # Отримуємо поточне значення (default: True для всіх наших налаштувань)
        current_value = self.chat_repo.get_setting(chat_id, setting_key, True)
        new_value = not current_value
        
        self.chat_repo.set_setting(chat_id, setting_key, new_value)
        
        try:
            await callback.answer(f"✅ Змінено на {'Увімкнено' if new_value else 'Вимкнено'}")
        except TelegramBadRequest:
            pass
            
        # Оновлюємо меню
        await self._show_settings_menu(callback.message, is_edit=True, owner_id=owner_id, original_chat_id=chat_id)

    async def callback_change_speed(self, callback: CallbackQuery):
        """Показує меню вибору швидкості"""
        # change_speed_ownerid_chatid
        parts = callback.data.split("_")
        
        if len(parts) >= 4:
            owner_id = int(parts[2])
            chat_id = parts[3]
            
            if callback.from_user.id != owner_id:
                try:
                    await callback.answer("❌ Ці налаштування не для вас!", show_alert=True)
                except TelegramBadRequest:
                    pass
                return
            suffix = f"_{owner_id}_{chat_id}"
        else:
            if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
                return
            suffix = ""
            owner_id = None
            chat_id = get_clean_chat_id(callback.message.chat.id)
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡️ Turbo (0.1s)", callback_data=f"set_speed_0.1{suffix}"),
                InlineKeyboardButton(text="🚀 Fast (0.3s)", callback_data=f"set_speed_0.3{suffix}")
            ],
            [
                InlineKeyboardButton(text="🚶 Normal (0.5s)", callback_data=f"set_speed_0.5{suffix}"),
                InlineKeyboardButton(text="🐢 Slow (1.0s)", callback_data=f"set_speed_1.0{suffix}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"settings_main_{owner_id}_{chat_id}" if owner_id else "settings_main")
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
        # set_speed_0.5_ownerid_chatid
        parts = callback.data.split("_")
        
        # Витягуємо speed (parts[2] = "0.5" або "0.1" etc.)
        speed_str = parts[2]
        
        if len(parts) >= 5:
            # Є owner_id та chat_id
            owner_id = int(parts[3])
            chat_id = parts[4]
            
            if callback.from_user.id != owner_id:
                try:
                    await callback.answer("❌ Ці налаштування не для вас!", show_alert=True)
                except TelegramBadRequest:
                    pass
                return
        else:
            if not await self._is_admin(callback.message.chat.id, callback.from_user.id, callback.bot):
                return
            owner_id = None
            chat_id = get_clean_chat_id(callback.message.chat.id)
        
        speed = float(speed_str)
        
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
            
        await self._show_settings_menu(callback.message, is_edit=True, owner_id=owner_id, original_chat_id=chat_id)
