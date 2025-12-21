"""
Конфігурація ПРОДАКШН бота
"""
import os
from dataclasses import dataclass

# === API CREDENTIALS ===
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = os.getenv('SESSION_NAME', 'account2_session')

# ПРОДАКШН БОТ
# Спочатку шукаємо специфічний для проду токен, якщо немає - беремо загальний BOT_TOKEN
BOT_TOKEN = os.getenv('PROD_BOT_TOKEN') or os.getenv('BOT_TOKEN', '')
PAYMENT_TOKEN = os.getenv('PROD_PAYMENT_TOKEN') or os.getenv('PAYMENT_TOKEN', '')

# === ADMIN ===
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))

# === CONTACTS ===
FEEDBACK_BOT = "@feedback_myshko_bot"
PROJECTS_CHANNEL = "https://t.me/+BZEIOiPj3so1NzU6"

# === FILES ===
DB_FILE = "users_data.json"  # Продакшн база

# === PING SETTINGS ===
PING_LIMITS = {
    "min_delay": 0.1,
    "max_delay": 10.0,
    "default_delay": 0.3,
    "min_chunk": 1,
    "max_chunk": 10,
    "default_chunk": 5
}

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
