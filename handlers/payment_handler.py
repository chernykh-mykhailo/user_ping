"""
Payment handlers - обробка платежів (SRP)
"""
import logging
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from .base_handler import BaseHandler
from config import PAYMENT_TOKEN, PREMIUM_PLANS, ADMIN_USER_ID


class PaymentHandler(BaseHandler):
    """
    Обробляє платежі через Telegram Stars
    Single Responsibility: тільки платежі
    """
    
    def __init__(self, chat_repo, premium_repo, bot: Bot, userbot=None):
        self.bot = bot
        self.userbot = userbot
        self.logger = logging.getLogger(__name__)
        super().__init__(chat_repo, premium_repo)
    
    def register_handlers(self):
        """Реєструє хендлери платежів"""
        self.router.message(Command("premium"))(self.cmd_premium)
        self.router.message(Command("buy_month"))(self.cmd_buy_month)
        self.router.message(Command("buy_year"))(self.cmd_buy_year)
        self.router.message(Command("refund"))(self.cmd_refund)
        self.router.message(Command("refund_confirm"))(self.cmd_refund_confirm)
        
        # Адмін-команди
        self.router.message(Command("admin_add_payment"))(self.cmd_admin_add_payment)
        self.router.message(Command("admin_payments"))(self.cmd_admin_payments)
        self.router.message(Command("admin_grant_premium"))(self.cmd_admin_grant_premium)
        self.router.message(Command("admin_revoke_premium"))(self.cmd_admin_revoke_premium)
        
        self.router.pre_checkout_query()(self.process_pre_checkout)
        self.router.message(F.successful_payment)(self.process_successful_payment)
    
    async def cmd_premium(self, message: Message):
        """Показує меню покупки преміуму"""
        month_plan = PREMIUM_PLANS["month"]
        year_plan = PREMIUM_PLANS["year"]
        
        premium_text = (
            "👑 <b>Premium статус</b>\n\n"
            "Отримайте доступ до ексклюзивних функцій:\n"
            "• 🚫 /superunreg — Постійне вимкнення пінгів\n"
            "• 🎯 Пріоритетна підтримка\n\n"
            "<b>Тарифи:</b>\n"
            f"📅 {month_plan.name} — {month_plan.price} ⭐ Stars\n"
            f"📆 {year_plan.name} — {year_plan.price} ⭐ Stars (знижка 17%)\n\n"
            "Виберіть тариф:\n"
            "/buy_month — Купити на місяць\n"
            "/buy_year — Купити на рік"
        )
        await message.answer(premium_text, parse_mode="HTML")
    
    async def cmd_buy_month(self, message: Message):
        """Створює рахунок на місяць преміуму"""
        plan = PREMIUM_PLANS["month"]
        
        await self.bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Premium на {plan.name.lower()}",
            description=f"Доступ до /superunreg та інших Premium функцій на {plan.duration_days} днів",
            payload="premium_month",
            provider_token=PAYMENT_TOKEN,
            currency="XTR",
            prices=[LabeledPrice(label=f"Premium ({plan.name})", amount=plan.price)]
        )
    
    async def cmd_buy_year(self, message: Message):
        """Створює рахунок на рік преміуму"""
        plan = PREMIUM_PLANS["year"]
        
        await self.bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Premium на {plan.name.lower()}",
            description=f"Доступ до /superunreg та інших Premium функцій на {plan.duration_days} днів (знижка 17%)",
            payload="premium_year",
            provider_token=PAYMENT_TOKEN,
            currency="XTR",
            prices=[LabeledPrice(label=f"Premium ({plan.name})", amount=plan.price)]
        )
    
    async def process_pre_checkout(self, pre_checkout_query: PreCheckoutQuery):
        """Підтверджує платіж"""
        await self.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    
    async def process_successful_payment(self, message: Message):
        """Обробляє успішний платіж"""
        payload = message.successful_payment.invoice_payload
        user_id = str(message.from_user.id)
        charge_id = message.successful_payment.telegram_payment_charge_id
        
        if payload == "premium_month":
            plan = PREMIUM_PLANS["month"]
        elif payload == "premium_year":
            plan = PREMIUM_PLANS["year"]
        else:
            return
        
        # Зберігаємо інформацію про платіж для можливості рефанду
        self.premium_repo.save_payment(user_id, charge_id, plan.price)
        
        # Надаємо преміум
        expiry = self.premium_repo.grant_premium(user_id, plan.duration_days)
        
        success_text = (
            "✅ <b>Оплата успішна!</b>\n\n"
            f"👑 Premium активовано на {plan.name.lower()}\n"
            f"📅 Діє до: {expiry.strftime('%d.%m.%Y')}\n\n"
            f"🔖 ID платежу: <code>{charge_id}</code>\n"
            "Тепер ви можете використовувати /superunreg\n\n"
            "<i>💡 Якщо виникли проблеми, ви можете запросити повернення коштів через /refund</i>"
        )
        
        await message.answer(success_text, parse_mode="HTML")
        self.logger.info(f"Premium надано користувачу {user_id} на {plan.name}")
    
    async def cmd_refund(self, message: Message):
        """Показує інформацію про рефанд"""
        user_id = str(message.from_user.id)
        payments = self.premium_repo.get_user_payments(user_id)
        
        if not payments:
            await message.answer(
                "❌ У вас немає платежів.\n\n"
                "Купити Premium: /premium"
            )
            return
        
        # Фільтруємо тільки не повернені платежі
        active_payments = [p for p in payments if not p.get("refunded", False)]
        
        if not active_payments:
            await message.answer(
                "ℹ️ Всі ваші платежі вже повернені або немає активних платежів."
            )
            return
        
        # Показуємо останній платіж
        last_payment = active_payments[-1]
        from datetime import datetime
        payment_date = datetime.fromisoformat(last_payment["date"])
        
        refund_text = (
            "💰 <b>Повернення коштів</b>\n\n"
            f"📅 Дата платежу: {payment_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"⭐ Сума: {last_payment['amount']} Stars\n"
            f"🔖 ID: <code>{last_payment['charge_id']}</code>\n\n"
            "Щоб повернути кошти, використайте:\n"
            f"/refund_confirm {last_payment['charge_id']}\n\n"
            "<i>⚠️ Увага: після повернення коштів ваш Premium буде скасовано</i>"
        )
        
        await message.answer(refund_text, parse_mode="HTML")
    
    async def cmd_refund_confirm(self, message: Message):
        """Підтверджує та виконує рефанд"""
        user_id = str(message.from_user.id)
        
        # Отримуємо charge_id з команди
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer(
                "❌ Неправильний формат команди.\n\n"
                "Використайте: /refund щоб отримати інструкції"
            )
            return
        
        charge_id = parts[1]
        
        # Перевіряємо чи існує такий платіж
        payments = self.premium_repo.get_user_payments(user_id)
        payment = next((p for p in payments if p["charge_id"] == charge_id and not p.get("refunded", False)), None)
        
        if not payment:
            await message.answer(
                "❌ Платіж не знайдено або вже повернено.\n\n"
                "Перевірте ID платежу через /refund"
            )
            return
        
        try:
            # Виконуємо рефанд через Telegram API
            result = await self.bot.refund_star_payment(
                user_id=int(user_id),
                telegram_payment_charge_id=charge_id
            )
            
            if result:
                # Позначаємо платіж як повернений
                self.premium_repo.mark_payment_refunded(user_id, charge_id)
                
                # Відбираємо преміум
                self.premium_repo.revoke_premium(user_id)
                
                await message.answer(
                    "✅ <b>Кошти повернено!</b>\n\n"
                    f"⭐ Повернено: {payment['amount']} Stars\n"
                    "👑 Premium скасовано\n\n"
                    "<i>Дякуємо за використання нашого сервісу!</i>",
                    parse_mode="HTML"
                )
                
                self.logger.info(f"Refund processed for user {user_id}, charge {charge_id}")
            else:
                await message.answer(
                    "❌ Не вдалося повернути кошти.\n\n"
                    "Спробуйте пізніше або зверніться до підтримки."
                )
                
        except Exception as e:
            self.logger.error(f"Refund error: {e}")
            await message.answer(
                "❌ Помилка при поверненні коштів.\n\n"
                f"Деталі: {str(e)}\n\n"
                "Зверніться до підтримки."
            )
    
    async def cmd_admin_add_payment(self, message: Message):
        """
        Адмін-команда: Додає платіж вручну
        Формат: /admin_add_payment <user_id> <amount> [charge_id]
        """
        if message.from_user.id != ADMIN_USER_ID:
            return
        
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "Використання:\n"
                "/admin_add_payment <user_id> <amount> [charge_id]\n\n"
                "Приклад:\n"
                "/admin_add_payment 831190060 500 manual_charge_123"
            )
            return
        
        try:
            user_id = parts[1]
            amount = int(parts[2])
            charge_id = parts[3] if len(parts) > 3 else f"manual_{user_id}_{amount}"
            
            # Додаємо платіж
            self.premium_repo.save_payment(user_id, charge_id, amount)
            
            await message.answer(
                f"✅ Платіж додано!\n\n"
                f"👤 User ID: {user_id}\n"
                f"⭐ Сума: {amount} Stars\n"
                f"🔖 Charge ID: <code>{charge_id}</code>\n\n"
                f"Тепер користувач може використати /refund",
                parse_mode="HTML"
            )
            
            self.logger.info(f"Admin added payment: user={user_id}, amount={amount}, charge={charge_id}")
            
        except ValueError:
            await message.answer("❌ Сума має бути числом")
        except Exception as e:
            await message.answer(f"❌ Помилка: {e}")
    
    async def cmd_admin_payments(self, message: Message):
        """
        Адмін-команда: Показує всі платежі користувача
        Формат: /admin_payments <user_id>
        """
        if message.from_user.id != ADMIN_USER_ID:
            return
        
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "Використання:\n"
                "/admin_payments <user_id>\n\n"
                "Приклад:\n"
                "/admin_payments 831190060"
            )
            return
        
        user_id = parts[1]
        payments = self.premium_repo.get_user_payments(user_id)
        
        if not payments:
            await message.answer(f"❌ У користувача {user_id} немає платежів")
            return
        
        from datetime import datetime
        
        payments_text = f"💰 <b>Платежі користувача {user_id}</b>\n\n"
        
        for i, payment in enumerate(payments, 1):
            date = datetime.fromisoformat(payment["date"])
            status = "❌ Повернено" if payment.get("refunded", False) else "✅ Активний"
            
            payments_text += (
                f"<b>#{i}</b>\n"
                f"📅 Дата: {date.strftime('%d.%m.%Y %H:%M')}\n"
                f"⭐ Сума: {payment['amount']} Stars\n"
                f"🔖 ID: <code>{payment['charge_id']}</code>\n"
                f"📊 Статус: {status}\n\n"
            )
        
        await message.answer(payments_text, parse_mode="HTML")
    
    async def cmd_admin_grant_premium(self, message: Message):
        """
        Адмін-команда: Видати Premium користувачу
        Формат: 
        - /admin_grant_premium <user_id> <days>
        - /admin_grant_premium @username <days>
        - /admin_grant_premium <days> (у відповідь на повідомлення)
        """
        if message.from_user.id != ADMIN_USER_ID:
            return
        
        parts = message.text.split()
        
        # Варіант 1: У відповідь на повідомлення
        if message.reply_to_message:
            if len(parts) < 2:
                await message.answer("❌ Вкажіть кількість днів")
                return
            
            user_id = str(message.reply_to_message.from_user.id)
            username = message.reply_to_message.from_user.username or "користувач"
            try:
                days = int(parts[1])
            except ValueError:
                await message.answer("❌ Кількість днів має бути числом")
                return
        
        # Варіант 2: З параметрами
        elif len(parts) >= 3:
            user_identifier = parts[1]
            
            # Перевіряємо чи це username
            if user_identifier.startswith('@'):
                username_to_find = user_identifier[1:]  # Без @
                
                # Шукаємо в базі даних чату
                from utils.helpers import get_clean_chat_id
                
                # Якщо команда в групі - шукаємо в цьому чаті
                if message.chat.type in ['group', 'supergroup']:
                    chat_id = get_clean_chat_id(message.chat.id)
                    
                    # Шукаємо user_id по username через userbot
                    user_id = None
                    username = None
                    
                    if self.userbot:
                        try:
                            async for user in self.userbot.client.iter_participants(message.chat.id):
                                if user.username and user.username.lower() == username_to_find.lower():
                                    user_id = str(user.id)
                                    username = user.username
                                    break
                        except Exception as e:
                            self.logger.error(f"Error finding user by username: {e}")
                    
                    if not user_id:
                        await message.answer(
                            f"❌ Користувача @{username_to_find} не знайдено в цьому чаті.\n\n"
                            "<b>Використайте один з варіантів:</b>\n"
                            "1️⃣ У відповідь на повідомлення користувача:\n"
                            "   <code>/admin_grant_premium 30</code>\n\n"
                            "2️⃣ За User ID:\n"
                            "   <code>/admin_grant_premium 831190060 30</code>\n\n"
                            "<i>💡 User ID можна дізнатися через @userinfobot</i>",
                            parse_mode="HTML"
                        )
                        return
                else:
                    await message.answer(
                        "❌ Видача Premium по @username працює тільки в групових чатах.\n\n"
                        "<b>Використайте:</b>\n"
                        "• За User ID: <code>/admin_grant_premium 831190060 30</code>",
                        parse_mode="HTML"
                    )
                    return
            else:
                user_id = user_identifier
                username = None
            
            try:
                days = int(parts[2])
            except ValueError:
                await message.answer("❌ Кількість днів має бути числом")
                return
        
        else:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "<b>Використання:</b>\n\n"
                "1️⃣ <b>У відповідь на повідомлення:</b>\n"
                "<code>/admin_grant_premium 30</code>\n\n"
                "2️⃣ <b>За User ID:</b>\n"
                "<code>/admin_grant_premium 831190060 30</code>\n\n"
                "3️⃣ <b>За @username (в групі):</b>\n"
                "<code>/admin_grant_premium @username 30</code>\n\n"
                "<b>Приклади:</b>\n"
                "• /admin_grant_premium 831190060 30 — місяць\n"
                "• /admin_grant_premium @user 365 — рік\n"
                "• /admin_grant_premium 831190060 7 — тиждень\n\n"
                "<i>💡 Найпростіше: відповісти на повідомлення користувача</i>",
                parse_mode="HTML"
            )
            return
        
        try:
            if days <= 0:
                await message.answer("❌ Кількість днів має бути більше 0")
                return
            
            # Надаємо Premium
            expiry = self.premium_repo.grant_premium(user_id, days)
            
            # Визначаємо період для повідомлення
            if days == 30:
                period_text = "місяць"
            elif days == 365:
                period_text = "рік"
            elif days == 7:
                period_text = "тиждень"
            else:
                period_text = f"{days} днів"
            
            user_display = f"@{username}" if username else f"<code>{user_id}</code>"
            
            await message.answer(
                f"✅ <b>Premium надано!</b>\n\n"
                f"👤 Користувач: {user_display}\n"
                f"🆔 User ID: <code>{user_id}</code>\n"
                f"⏰ Період: {period_text} ({days} днів)\n"
                f"📅 Діє до: {expiry.strftime('%d.%m.%Y')}\n\n"
                f"<i>Користувач тепер може використовувати /superunreg</i>",
                parse_mode="HTML"
            )
            
            # Спробуємо повідомити користувача
            try:
                await self.bot.send_message(
                    int(user_id),
                    f"🎉 <b>Вітаємо!</b>\n\n"
                    f"Вам надано 👑 Premium статус на {period_text}!\n"
                    f"📅 Діє до: {expiry.strftime('%d.%m.%Y')}\n\n"
                    f"Тепер ви можете використовувати /superunreg для постійного вимкнення пінгів.",
                    parse_mode="HTML"
                )
                self.logger.info(f"Користувача {user_id} повідомлено про Premium")
            except Exception as e:
                self.logger.warning(f"Не вдалося повідомити користувача {user_id}: {e}")
            
            self.logger.info(f"Admin granted {days} days premium to user {user_id}")
            
        except ValueError:
            await message.answer("❌ Кількість днів має бути числом")
        except Exception as e:
            await message.answer(f"❌ Помилка: {e}")


    async def cmd_admin_revoke_premium(self, message: Message):
        """
        Адмін-команда: Забрати Premium у користувача
        Формат: 
        - /admin_revoke_premium <user_id>
        - /admin_revoke_premium @username
        - /admin_revoke_premium (у відповідь на повідомлення)
        """
        if message.from_user.id != ADMIN_USER_ID:
            return
        
        parts = message.text.split()
        
        # Варіант 1: У відповідь на повідомлення
        if message.reply_to_message:
            user_id = str(message.reply_to_message.from_user.id)
            username = message.reply_to_message.from_user.username or "користувач"
        
        # Варіант 2: З параметрами
        elif len(parts) >= 2:
            user_identifier = parts[1]
            
            # Перевіряємо чи це username
            if user_identifier.startswith('@'):
                username_to_find = user_identifier[1:]
                
                from utils.helpers import get_clean_chat_id
                
                if message.chat.type in ['group', 'supergroup']:
                    user_id = None
                    username = None
                    
                    if self.userbot:
                        try:
                            async for user in self.userbot.client.iter_participants(message.chat.id):
                                if user.username and user.username.lower() == username_to_find.lower():
                                    user_id = str(user.id)
                                    username = user.username
                                    break
                        except Exception as e:
                            self.logger.error(f"Error finding user by username: {e}")
                    
                    if not user_id:
                        await message.answer(
                            f"❌ Користувача @{username_to_find} не знайдено в цьому чаті.\n\n"
                            "<b>Використайте один з варіантів:</b>\n"
                            "1️⃣ У відповідь на повідомлення користувача:\n"
                            "   <code>/admin_revoke_premium</code>\n\n"
                            "2️⃣ За User ID:\n"
                            "   <code>/admin_revoke_premium 831190060</code>",
                            parse_mode="HTML"
                        )
                        return
                else:
                    await message.answer(
                        "❌ Видалення Premium по @username працює тільки в групових чатах.\n\n"
                        "<b>Використайте:</b>\n"
                        "• За User ID: <code>/admin_revoke_premium 831190060</code>",
                        parse_mode="HTML"
                    )
                    return
            else:
                user_id = user_identifier
                username = None
        
        else:
            await message.answer(
                "❌ Неправильний формат.\n\n"
                "<b>Використання:</b>\n\n"
                "1️⃣ <b>У відповідь на повідомлення:</b>\n"
                "<code>/admin_revoke_premium</code>\n\n"
                "2️⃣ <b>За User ID:</b>\n"
                "<code>/admin_revoke_premium 831190060</code>\n\n"
                "3️⃣ <b>За @username (в групі):</b>\n"
                "<code>/admin_revoke_premium @username</code>\n\n"
                "<i>💡 Найпростіше: відповісти на повідомлення користувача</i>",
                parse_mode="HTML"
            )
            return
        
        try:
            # Перевіряємо чи є Premium
            if not self.premium_repo.has_premium(user_id):
                await message.answer(
                    f"❌ У користувача немає Premium статусу.\n\n"
                    f"🆔 User ID: <code>{user_id}</code>",
                    parse_mode="HTML"
                )
                return
            
            # Забираємо Premium
            revoked = self.premium_repo.revoke_premium(user_id)
            
            if revoked:
                user_display = f"@{username}" if username else f"<code>{user_id}</code>"
                
                await message.answer(
                    f"✅ <b>Premium відібрано!</b>\n\n"
                    f"👤 Користувач: {user_display}\n"
                    f"🆔 User ID: <code>{user_id}</code>\n\n"
                    f"<i>Користувач більше не може використовувати /superunreg</i>",
                    parse_mode="HTML"
                )
                
                # Спробуємо повідомити користувача
                try:
                    await self.bot.send_message(
                        int(user_id),
                        f"⚠️ <b>Повідомлення</b>\n\n"
                        f"Ваш 👑 Premium статус скасовано.\n\n"
                        f"Команда /superunreg більше недоступна.\n"
                        f"Для відновлення Premium: /premium",
                        parse_mode="HTML"
                    )
                    self.logger.info(f"Користувача {user_id} повідомлено про скасування Premium")
                except Exception as e:
                    self.logger.warning(f"Не вдалося повідомити користувача {user_id}: {e}")
                
                self.logger.info(f"Admin revoked premium from user {user_id}")
            else:
                await message.answer("❌ Не вдалося відібрати Premium")
                
        except Exception as e:
            await message.answer(f"❌ Помилка: {e}")

