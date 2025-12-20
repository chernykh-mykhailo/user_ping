"""
Конфігурація ТЕСТОВОГО бота
"""
from dataclasses import dataclass

# === API CREDENTIALS ===
API_ID = 38862642
API_HASH = 'f0d13bbdc1c2b5c07521c24570f0f7cb'
SESSION_NAME = 'account2_session'

# ТЕСТОВИЙ БОТ
BOT_TOKEN = "8592617001:AAFLLw59qBmRrvAwOe5JZaWWRwBbGf3Q5cs"
PAYMENT_TOKEN = "2051251535:TEST:OTk5MDA4ODgxLTAwNQ"  # RedSysTest

# === ADMIN ===
ADMIN_USER_ID = 831190060

# === CONTACTS ===
FEEDBACK_BOT = "@feedback_myshko_bot"
PROJECTS_CHANNEL = "https://t.me/+BZEIOiPj3so1NzU6"

# === FILES ===
DB_FILE = "users_data_test.json"  # Окрема база для тесту!

# === PING SETTINGS ===
CHUNK_SIZE = 5
PING_DELAY = 1.5

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

# Chat Premium (v1.5.0)
CHAT_PREMIUM_PLANS = {
    "month": PremiumPlan("Chat Premium (Місяць)", 1500, 30),
    "year": PremiumPlan("Chat Premium (Рік)", 15000, 365)
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
