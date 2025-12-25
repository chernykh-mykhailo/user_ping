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
    from config_prod import *
else:
    print("🧪 Запуск у ТЕСТОВОМУ режимі")
    from config_test import *

print(f"📱 Bot Token: {BOT_TOKEN[:20]}...")
print(f"💾 Database: {DB_FILE}")
try:
    print(f"📂 Session Storage: {SESSION_STORAGE}")
except NameError:
    print("⚠️  SESSION_STORAGE NOT DEFINED IN CONFIG!")
