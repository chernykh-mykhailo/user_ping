"""
Конфігурація бота - ПРИКЛАД
Скопіюйте цей файл як config.py і заповніть своїми даними
"""
from dataclasses import dataclass

# === API CREDENTIALS ===
# Отримайте на https://my.telegram.org
API_ID = 12345678 # Зміни це
API_HASH = 'your_api_hash_here' # Зміни це
SESSION_NAME = 'account_session'

# Отримайте від @BotFather
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz" # Зміни це

# Отримайте від @BotFather -> Payments -> Telegram Stars
# Для тестування використовуйте тестовий токен
PAYMENT_TOKEN = "1234567890:TEST:your_test_token_here" # Зміни це

# === ADMIN ===
# Ваш Telegram User ID (отримайте від @userinfobot)
ADMIN_USER_ID = 123456789 # Зміни це

# === CONTACTS ===
FEEDBACK_BOT = "@your_feedback_bot" 
PROJECTS_CHANNEL = "https://t.me/your_channel"

# === FILES ===
DB_FILE = "users_data.json"

# === PING SETTINGS ===
CHUNK_SIZE = 5  # Кількість людей в одному повідомленні
PING_DELAY = 1.5  # Пауза між повідомленнями (секунди)

# === EMOJIS ===
EMOJIS = [
    "😀", "😎", "🦾", "🔥", "🚀", "⚡️", "🏆", "🎯", 
    "💎", "🌟", "🎉", "👾", "🤖", "🎃", "🐙", "🦊", 
    "🦁", "🦖", "🛸", "🎮", "⚔️", "🔔", "📢", "🌀", "🧿"
]

# === PREMIUM PRICING ===
@dataclass
class PremiumPlan:
    name: str
    price: int  # Stars
    days: int

# Personal Premium (знижено для залучення)
PREMIUM_PLANS = {
    "month": PremiumPlan("Personal Premium (Місяць)", 20, 30),
    "year": PremiumPlan("Personal Premium (Рік)", 200, 365)
}

# Chat Premium (v2.5.0) - reduced price to encourage adoption
CHAT_PREMIUM_PLANS = {
    "month": PremiumPlan("Chat Premium (Місяць)", 500, 30),
    "year": PremiumPlan("Chat Premium (Рік)", 5000, 365)
}

# Gift Premium (v1.5.0) - зі знижкою 20%!
GIFT_PLANS = {
    "week": PremiumPlan("Подарунок 7 днів", 6, 7),      # -25% від Personal Premium
    "month": PremiumPlan("Подарунок 30 днів", 16, 30)   # -20% від Personal Premium
}

# === REFERRAL SYSTEM (v1.5.0) ===
REFERRAL_BONUS_SIGNUP = 7      # Днів за кожного реферала
REFERRAL_BONUS_PREMIUM = 14    # Бонус якщо реферал купить Premium

# === GIFT SETTINGS (v1.5.0) ===
GIFT_DISCOUNT = 0.20           # 20% знижка на подарунки (стимулює покупки)
