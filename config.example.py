"""
Конфігурація бота - ПРИКЛАД
Скопіюйте цей файл як config.py і заповніть своїми даними
"""
from dataclasses import dataclass

# === API CREDENTIALS ===
# Отримайте на https://my.telegram.org
API_ID = 12345678
API_HASH = 'your_api_hash_here'
SESSION_NAME = 'account_session'

# Отримайте від @BotFather
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# Отримайте від @BotFather -> Payments -> Telegram Stars
# Для тестування використовуйте тестовий токен
PAYMENT_TOKEN = "1234567890:TEST:your_test_token_here"

# === ADMIN ===
# Ваш Telegram User ID (отримайте від @userinfobot)
ADMIN_USER_ID = 123456789

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
    duration_days: int

PREMIUM_PLANS = {
    "month": PremiumPlan("Місяць", 50, 30),
    "year": PremiumPlan("Рік", 500, 365)
}
