"""
Конфігурація бота - автоматичний вибір між TEST і PROD
"""
import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища з .env файлу
load_dotenv()

# Визначаємо режим: TEST або PROD
# Встановіть змінну середовища BOT_MODE=prod для продакшн
BOT_MODE = os.getenv('BOT_MODE', 'test').lower()

if BOT_MODE == 'prod':
    print("🚀 Запуск у ПРОДАКШН режимі")
    from config_prod import (
        API_ID, API_HASH, SESSION_NAME, BOT_TOKEN,
        PAYMENT_TOKEN, ADMIN_USER_ID, DB_FILE, PING_LIMITS,
        EMOJIS, PREMIUM_PLANS, CHAT_PREMIUM_PLANS,
        GIFT_PLANS, REFERRAL_BONUS_SIGNUP, REFERRAL_BONUS_PREMIUM,
        GIFT_DISCOUNT, PROJECTS_CHANNEL, UB_ACCOUNTS
    )
else:
    print("🧪 Запуск у ТЕСТОВОМУ режимі")
    from config_test import (
        API_ID, API_HASH, SESSION_NAME, BOT_TOKEN,
        PAYMENT_TOKEN, ADMIN_USER_ID, DB_FILE, PING_LIMITS,
        EMOJIS, PREMIUM_PLANS, CHAT_PREMIUM_PLANS,
        GIFT_PLANS, REFERRAL_BONUS_SIGNUP, REFERRAL_BONUS_PREMIUM,
        GIFT_DISCOUNT, PROJECTS_CHANNEL, UB_ACCOUNTS
    )

print(f"📱 Bot Token: {BOT_TOKEN[:20]}...")
print(f"💾 Database: {DB_FILE}")
