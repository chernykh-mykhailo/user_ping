"""
Ping handlers - команди пінгування (SRP)
"""
import logging
import asyncio
import random
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from .base_handler import BaseHandler
from utils.helpers import get_clean_chat_id
from config import PING_LIMITS, EMOJIS
from aiogram.exceptions import TelegramBadRequest


class PingHandler(BaseHandler):
    """
    Обробляє команди пінгування
    Single Responsibility: тільки пінги
    """
    
    def __init__(self, chat_repo, premium_repo, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери пінгування"""
        # Базові виклики
        self.router.message(Command("all"))(self.cmd_all)
        self.router.message(F.text.regexp(r'^!?кнагє', flags=0))(self.cmd_all)
        
        self.router.message(Command("emoji"))(self.cmd_emoji)
        self.router.message(F.text.regexp(r'^!?емодзі', flags=0))(self.cmd_emoji)
        
        # Нові команди v1.1.0
        self.router.message(Command("admins"))(self.cmd_admins)
        self.router.message(F.text.regexp(r'^!?адміни', flags=0))(self.cmd_admins)
        
        self.router.message(Command("anybody"))(self.cmd_anybody)
        self.router.message(F.text.regexp(r'^!?хтось', flags=0))(self.cmd_anybody)
        
        self.router.message(Command("stop", "stopcall"))(self.cmd_stop)
        self.router.message(F.text.regexp(r'^!?стоп', flags=0))(self.cmd_stop)
        
        # Шаблони викликів
        self.router.message(F.text.regexp(r'^!cpatterns$', flags=0))(self.cmd_list_templates)
        self.router.message(F.text.regexp(r'^!addcpattern\s+(\S+)', flags=0))(self.cmd_add_template)
        self.router.message(F.text.regexp(r'^!delcpattern\s+(\S+)', flags=0))(self.cmd_del_template)
        
        # Тригери викликів v1.2.0
        self.router.message(F.text.regexp(r'^!calls$', flags=0))(self.cmd_list_triggers)
        self.router.message(F.text.regexp(r'^!callinfo\s+(\S+)', flags=0))(self.cmd_trigger_info)
        self.router.message(F.text.regexp(r'^!addcall\s+(\S+)', flags=0))(self.cmd_add_trigger)
        self.router.message(F.text.regexp(r'^!delcall\s+(\S+)', flags=0))(self.cmd_del_trigger)
        self.router.message(F.text.regexp(r'^!adduser\s+(\S+)', flags=0))(self.cmd_add_user_to_trigger)
        self.router.message(F.text.regexp(r'^!deluser\s+(\S+)', flags=0))(self.cmd_del_user_from_trigger)
        
        # Self-Service Roles v1.3.0
        self.router.message(F.text.regexp(r'^!roles_panel$', flags=0))(self.cmd_roles_panel)
        self.router.message(F.text.regexp(r'^!set_role_emoji\s+(\S+)\s+(.+)', flags=0))(self.cmd_set_role_emoji)
        self.router.callback_query(F.data.startswith("role_"))(self.callback_role_toggle)
        self.router.callback_query(F.data == "stop_ping")(self.callback_stop_ping)
        
        # Виклик тригера (має бути останнім!)
        self.router.message(F.text.regexp(r'^!(\w+)$', flags=0))(self.cmd_call_trigger)
    
    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        """Перевіряє права адміністратора"""
        cid = get_clean_chat_id(chat_id)
        try:
            member = await self.bot.get_chat_member(cid, user_id)
            return member.status in ['creator', 'administrator']
        except:
            return True
    
    async def _get_admin_users(self, chat_id: int) -> dict:
        """Повертає тільки адміністраторів з активних користувачів"""
        clean_chat_id = get_clean_chat_id(chat_id)
        all_users = self.chat_repo.get_active_users(clean_chat_id)
        
        admin_users = {}
        for uid, name in all_users.items():
            try:
                member = await self.bot.get_chat_member(chat_id, int(uid))
                if member.status in ['creator', 'administrator']:
                    admin_users[uid] = name
            except:
                continue
        
        return admin_users
    
    async def _send_pings(
        self,
        chat_id: int,
        users: dict,
        call_text: str,
        use_emoji: bool = False
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
        user_ids = list(users.keys())
        
        # Скидаємо прапорець зупинки перед початком
        self.chat_repo.set_stop_flag(clean_chat_id, False)
        
        # Отримуємо налаштування чату
        pin_enabled = self.chat_repo.get_setting(clean_chat_id, "pin_enabled", True)
        first_msg_stop = self.chat_repo.get_setting(clean_chat_id, "first_msg_stop", True)
        
        # Динамічні налаштування з урахуванням лімітів
        ping_delay = self.chat_repo.get_setting(clean_chat_id, "ping_delay", PING_LIMITS["default_delay"])
        chunk_size = self.chat_repo.get_setting(clean_chat_id, "chunk_size", PING_LIMITS["default_chunk"])
        
        # Перевірка глобальних налаштувань (Global Override)
        global_delay = self.chat_repo.get_global_setting("ping_delay")
        if global_delay:
            ping_delay = global_delay
            
        # Hard Limits Safety Check
        if ping_delay < PING_LIMITS["min_delay"]: ping_delay = PING_LIMITS["min_delay"]
        if ping_delay > PING_LIMITS["max_delay"]: ping_delay = PING_LIMITS["max_delay"]
        if chunk_size < PING_LIMITS["min_chunk"]: chunk_size = PING_LIMITS["min_chunk"]
        if chunk_size > PING_LIMITS["max_chunk"]: chunk_size = PING_LIMITS["max_chunk"]
        
        chunk_size = int(chunk_size)
        
        for i in range(0, len(user_ids), chunk_size):
            # Перевіряємо прапорець зупинки
            if self.chat_repo.get_stop_flag(clean_chat_id):
                self.logger.info(f"Виклик зупинено в чаті {clean_chat_id}")
                try:
                    await self.bot.send_message(
                        chat_id,
                        "⏸ <b>Виклик зупинено</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass
                break
            
            chunk = user_ids[i:i + chunk_size]
            mentions = []
            
            for uid in chunk:
                if use_emoji:
                    label = random.choice(EMOJIS)
                else:
                    label = users[uid]
                
                mentions.append(f'<a href="tg://user?id={uid}">{label}</a>')
            
            try:
                # Визначаємо чи потрібна кнопка стоп
                is_first_chunk = (i == 0)
                add_stop_button = True
                
                if first_msg_stop and not is_first_chunk:
                    add_stop_button = False
                
                keyboard = None
                footer_text = ""
                
                if add_stop_button:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🛑 Стоп", callback_data="stop_ping")
                    ]])
                    footer_text = "\n\n(стоп - зупинити)"
                
                sent_message = await self.bot.send_message(
                    chat_id,
                    f"<b>{call_text}</b>\n\n" + " ".join(mentions) + footer_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
                # Закріплюємо перше повідомлення
                if is_first_chunk and pin_enabled:
                    try:
                        await self.bot.pin_chat_message(chat_id, sent_message.message_id)
                    except Exception as e:
                        self.logger.warning(f"Не вдалося закріпити повідомлення: {e}")
                
                await asyncio.sleep(ping_delay)
            except:
                continue
    
    async def cmd_all(self, message: Message):
        """Пінгує всіх користувачів"""
        self.logger.info(f"Отримано команду закликання від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Увага!"
        
        # Перевірка на шаблон
        if len(parts) > 1:
            chat_id = get_clean_chat_id(message.chat.id)
            templates = self.chat_repo.get_call_templates(chat_id)
            template_name = parts[1].strip()
            
            if template_name in templates:
                call_text = templates[template_name]
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        try:
            await message.delete()
        except:
            pass
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=False)
    
    async def cmd_emoji(self, message: Message):
        """Пінгує всіх користувачів емодзі"""
        self.logger.info(f"Отримано команду емодзі від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Увага!"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        try:
            await message.delete()
        except:
            pass
        
        await self._send_pings(message.chat.id, users, call_text, use_emoji=True)
    
    async def cmd_admins(self, message: Message):
        """Пінгує тільки адміністраторів"""
        self.logger.info(f"Отримано команду виклику адмінів від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "📣 Виклик адмінів!"
        
        admin_users = await self._get_admin_users(message.chat.id)
        
        if not admin_users:
            await message.answer("❌ Не знайдено адміністраторів")
            return
        
        try:
            await message.delete()
        except:
            pass
        
        await self._send_pings(message.chat.id, admin_users, call_text, use_emoji=False)
    
    async def cmd_anybody(self, message: Message):
        """Викликає випадкового учасника"""
        self.logger.info(f"Отримано команду випадкового виклику від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        parts = message.text.split(maxsplit=1)
        call_text = parts[1] if len(parts) > 1 else "🎲 Випадковий учасник:"
        
        chat_id = get_clean_chat_id(message.chat.id)
        users = self.chat_repo.get_active_users(chat_id)
        
        if not users:
            return
        
        # Вибираємо випадкового
        random_uid = random.choice(list(users.keys()))
        random_name = users[random_uid]
        
        try:
            await message.delete()
        except:
            pass
        
        await self.bot.send_message(
            message.chat.id,
            f"<b>{call_text}</b>\n\n<a href=\"tg://user?id={random_uid}\">{random_name}</a>",
            parse_mode="HTML"
        )
    
    async def cmd_stop(self, message: Message):
        """Зупиняє активний виклик"""
        self.logger.info(f"Отримано команду зупинки від {message.from_user.id}")
        
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        self.chat_repo.set_stop_flag(chat_id, True)
        
        await message.answer("⏸ Зупинка виклику...")
    
    async def cmd_list_templates(self, message: Message):
        """Показує список шаблонів викликів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        templates = self.chat_repo.get_call_templates(chat_id)
        
        if not templates:
            await message.answer(
                "📝 <b>Шаблони викликів</b>\n\n"
                "Немає збережених шаблонів.\n\n"
                "Додати: <code>!addcpattern назва</code> (у відповідь на повідомлення з текстом)",
                parse_mode="HTML"
            )
            return
        
        text = "📝 <b>Шаблони викликів:</b>\n\n"
        for name, template_text in templates.items():
            preview = template_text[:50] + "..." if len(template_text) > 50 else template_text
            text += f"• <code>{name}</code>: {preview}\n"
        
        text += "\n<i>Використання: /all {назва}</i>"
        
        await message.answer(text, parse_mode="HTML")
    
    async def cmd_add_template(self, message: Message):
        """Додає шаблон виклику"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        if not message.reply_to_message or not message.reply_to_message.text:
            await message.answer(
                "❌ Використовуйте цю команду у відповідь на повідомлення з текстом шаблону"
            )
            return
        
        # Отримуємо назву шаблону з команди
        import re
        match = re.search(r'^!addcpattern\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву шаблону")
            return
        
        template_name = match.group(1)
        template_text = message.reply_to_message.text
        
        chat_id = get_clean_chat_id(message.chat.id)
        self.chat_repo.add_call_template(chat_id, template_name, template_text)
        
        await message.answer(
            f"✅ Шаблон <code>{template_name}</code> додано!\n\n"
            f"Використання: <code>/all {template_name}</code>",
            parse_mode="HTML"
        )
    
    async def cmd_del_template(self, message: Message):
        """Видаляє шаблон виклику"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!delcpattern\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву шаблону")
            return
        
        template_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.remove_call_template(chat_id, template_name):
            await message.answer(f"✅ Шаблон <code>{template_name}</code> видалено", parse_mode="HTML")
        else:
            await message.answer(f"❌ Шаблон <code>{template_name}</code> не знайдено", parse_mode="HTML")
    
    # === Call Triggers v1.2.0 ===
    
    async def cmd_list_triggers(self, message: Message):
        """Показує список тригерів викликів"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_call_triggers(chat_id)
        
        if not triggers:
            await message.answer(
                "🎯 <b>Тригери викликів</b>\n\n"
                "Немає створених тригерів.\n\n"
                "Створити: <code>!addcall назва</code>\n"
                "Додати користувача: <code>!adduser назва</code> (у відповідь)\n"
                "Викликати: <code>!назва</code>",
                parse_mode="HTML"
            )
            return
        
        text = "🎯 <b>Тригери викликів:</b>\n\n"
        for trigger_name, user_ids in triggers.items():
            user_count = len(user_ids)
            text += f"• <code>!{trigger_name}</code> — {user_count} користувачів\n"
        
        text += "\n<i>Інфо про тригер: !callinfo назва</i>"
        
        await message.answer(text, parse_mode="HTML")
    
    async def cmd_trigger_info(self, message: Message):
        """Показує інформацію про тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!callinfo\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву тригера")
            return
        
        trigger_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if not user_ids:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено або порожній",
                parse_mode="HTML"
            )
            return
        
        # Отримуємо імена користувачів
        chat_data = self.chat_repo.get_chat_data(chat_id)
        all_users = chat_data.get("users", {})
        
        text = f"🎯 <b>Тригер: !{trigger_name}</b>\n\n"
        text += f"👥 Користувачів: {len(user_ids)}\n\n"
        text += "<b>Список:</b>\n"
        
        for uid in user_ids:
            name = all_users.get(uid, f"User {uid}")
            text += f"• {name}\n"
        
        text += f"\n<i>Виклик: !{trigger_name}</i>"
        
        await message.answer(text, parse_mode="HTML")
    
    async def cmd_add_trigger(self, message: Message):
        """Створює новий тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        # Підтримуємо два формати: !addcall назва або !addcall назва емодзі
        match = re.search(r'^!addcall\s+(\S+)(?:\s+(.+))?', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву тригера")
            return
        
        trigger_name = match.group(1)
        emoji = match.group(2).strip() if match.group(2) else None
        
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.create_call_trigger(chat_id, trigger_name):
            # Якщо вказано емодзі - встановлюємо одразу
            if emoji:
                self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji)
                await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено з емодзі {emoji}!\n\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>\n"
                    f"Панель реєстрації: <code>!roles_panel</code>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"✅ Тригер <code>!{trigger_name}</code> створено!\n\n"
                    f"Встановити емодзі: <code>!set_role_emoji {trigger_name} 🎯</code>\n"
                    f"Додати користувача: <code>!adduser {trigger_name}</code> (у відповідь на повідомлення)\n"
                    f"Викликати: <code>!{trigger_name}</code>",
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> вже існує",
                parse_mode="HTML"
            )
    
    async def cmd_del_trigger(self, message: Message):
        """Видаляє тригер"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!delcall\s+(\S+)', message.text)
        if not match:
            await message.answer("❌ Вкажіть назву тригера")
            return
        
        trigger_name = match.group(1)
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.delete_call_trigger(chat_id, trigger_name):
            await message.answer(
                f"✅ Тригер <code>!{trigger_name}</code> видалено",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
            )
    
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
        match = re.search(r'^!adduser\s+(\S+)', message.text)
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
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
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
        match = re.search(r'^!deluser\s+(\S+)', message.text)
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
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Користувача не знайдено в тригері <code>!{trigger_name}</code>",
                parse_mode="HTML"
            )
    
    async def cmd_call_trigger(self, message: Message):
        """Викликає користувачів з тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!(\w+)$', message.text)
        if not match:
            return
        
        trigger_name = match.group(1)
        
        # Ігноруємо системні команди
        system_commands = ['кнагє', 'емодзі', 'адміни', 'хтось', 'стоп', 'збір', 'стата', 
                          'анрег', 'суперанрег', 'рег', 'calls', 'cpatterns', 'upatterns']
        if trigger_name.lower() in system_commands:
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        user_ids = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if not user_ids:
            # Тихо ігноруємо, якщо тригер не знайдено
            return
        
        # Отримуємо імена користувачів
        chat_data = self.chat_repo.get_chat_data(chat_id)
        all_users = chat_data.get("users", {})
        
        trigger_users = {}
        for uid in user_ids:
            if uid in all_users:
                trigger_users[uid] = all_users[uid]
        
        if not trigger_users:
            await message.answer(f"❌ Тригер <code>!{trigger_name}</code> порожній", parse_mode="HTML")
            return
        
        try:
            await message.delete()
        except:
            pass
        
        call_text = f"🎯 Тригер: {trigger_name}"
        await self._send_pings(message.chat.id, trigger_users, call_text, use_emoji=False)
    
    # === Self-Service Roles v1.3.0 ===
    
    async def cmd_roles_panel(self, message: Message):
        """Створює панель самореєстрації на тригери"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        chat_id = get_clean_chat_id(message.chat.id)
        triggers = self.chat_repo.get_call_triggers(chat_id)
        
        if not triggers:
            await message.answer(
                "❌ Немає створених тригерів.\n\n"
                "Спочатку створіть тригери:\n"
                "<code>!addcall croco</code>\n"
                "<code>!set_role_emoji croco 🐊</code>",
                parse_mode="HTML"
            )
            return
        
        # Отримуємо емодзі для тригерів
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        
        # Створюємо кнопки
        buttons = []
        row = []
        
        for trigger_name in sorted(triggers.keys()):
            emoji = emojis.get(trigger_name, "🎯")
            button_text = f"{emoji} {trigger_name.capitalize()}"
            callback_data = f"role_{trigger_name}"
            
            row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
            
            # По 2 кнопки в ряд
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        # Додаємо останній ряд якщо є
        if row:
            buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ігри/події, на які хочете отримувати сповіщення:\n\n"
            "<i>Натисніть кнопку щоб зареєструватись або вийти</i>"
        )
        
        try:
            await message.delete()
        except:
            pass
        
        await self.bot.send_message(
            message.chat.id,
            panel_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def cmd_set_role_emoji(self, message: Message):
        """Встановлює емодзі для тригера"""
        if not await self._is_admin(message.chat.id, message.from_user.id):
            return
        
        import re
        match = re.search(r'^!set_role_emoji\s+(\S+)\s+(.+)', message.text)
        if not match:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "Використання: <code>!set_role_emoji назва емодзі</code>\n\n"
                "Приклад:\n"
                "<code>!set_role_emoji croco 🐊</code>",
                parse_mode="HTML"
            )
            return
        
        trigger_name = match.group(1)
        emoji = match.group(2).strip()
        
        chat_id = get_clean_chat_id(message.chat.id)
        
        if self.chat_repo.set_trigger_emoji(chat_id, trigger_name, emoji):
            await message.answer(
                f"✅ Емодзі для тригера <code>!{trigger_name}</code> встановлено: {emoji}\n\n"
                f"Оновіть панель: <code>!roles_panel</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Тригер <code>!{trigger_name}</code> не знайдено",
                parse_mode="HTML"
            )
    
    async def callback_role_toggle(self, callback: CallbackQuery):
        """Обробляє натискання кнопки реєстрації"""
        trigger_name = callback.data.replace("role_", "")
        user_id = str(callback.from_user.id)
        chat_id = get_clean_chat_id(callback.message.chat.id)
        
        # Перевіряємо чи користувач вже в тригері
        trigger_users = self.chat_repo.get_trigger_users(chat_id, trigger_name)
        
        if user_id in trigger_users:
            # Видаляємо
            self.chat_repo.remove_user_from_trigger(chat_id, trigger_name, user_id)
            emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name)
            try:
                await callback.answer(
                    f"❌ Ви вийшли з {emoji} {trigger_name}",
                    show_alert=False
                )
            except TelegramBadRequest:
                pass
        else:
            # Додаємо
            self.chat_repo.add_user_to_trigger(chat_id, trigger_name, user_id)
            emoji = self.chat_repo.get_trigger_emoji(chat_id, trigger_name)
            try:
                await callback.answer(
                    f"✅ Ви зареєструвались на {emoji} {trigger_name}!",
                    show_alert=False
                )
            except TelegramBadRequest:
                pass
        
        # Оновлюємо панель з поточним статусом
        await self._update_roles_panel(callback.message, chat_id, user_id)
    
    async def _update_roles_panel(self, message: Message, chat_id: str, user_id: str):
        """Оновлює панель ролей з позначками"""
        triggers = self.chat_repo.get_call_triggers(chat_id)
        emojis = self.chat_repo.get_all_trigger_emojis(chat_id)
        
        # Створюємо кнопки з позначками
        buttons = []
        row = []
        
        for trigger_name in sorted(triggers.keys()):
            emoji = emojis.get(trigger_name, "🎯")
            trigger_users = self.chat_repo.get_trigger_users(chat_id, trigger_name)
            
            # Додаємо ✅ якщо користувач зареєстрований
            if user_id in trigger_users:
                button_text = f"✅ {emoji} {trigger_name.capitalize()}"
            else:
                button_text = f"{emoji} {trigger_name.capitalize()}"
            
            callback_data = f"role_{trigger_name}"
            
            row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
            
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        panel_text = (
            "🎮 <b>Панель реєстрації</b>\n\n"
            "Оберіть ігри/події, на які хочете отримувати сповіщення:\n\n"
            "<i>Натисніть кнопку щоб зареєструватись або вийти</i>"
        )
        
        try:
            await message.edit_text(panel_text, reply_markup=keyboard, parse_mode="HTML")
        except:
            pass

    async def callback_stop_ping(self, callback: CallbackQuery):
        """Обробляє натискання кнопки стоп"""
        if not await self._is_admin(callback.message.chat.id, callback.from_user.id):
            try:
                await callback.answer("❌ Тільки адміни можуть зупиняти виклик", show_alert=True)
            except TelegramBadRequest:
                pass
            return

        chat_id = get_clean_chat_id(callback.message.chat.id)
        self.chat_repo.set_stop_flag(chat_id, True)
        
        # Отримуємо налаштування для звіту
        admin_stop_report = self.chat_repo.get_setting(chat_id, "admin_stop_report", True)
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
                callback.message.text + stop_text,
                parse_mode="HTML",
                reply_markup=None
            )
        except:
            pass
