"""
Скрипт для автоматичного оновлення config.py до v1.5.0
"""

# Читаємо поточний config.py
with open('config.py', 'r', encoding='utf-8') as f:
    config_content = f.read()

# Перевіряємо чи вже є нові константи
if 'CHAT_PREMIUM_PLANS' in config_content:
    print("✅ config.py вже оновлено!")
    exit(0)

# Додаємо нові константи
new_config = """
# === v1.5.0 UPDATES ===

# Chat Premium (v1.5.0)
CHAT_PREMIUM_PLANS = {
    "month": PremiumPlan("Chat Premium (Місяць)", 1500, 30),
    "year": PremiumPlan("Chat Premium (Рік)", 15000, 365)
}

# Gift Premium (v1.5.0)
GIFT_PLANS = {
    "week": PremiumPlan("Подарунок 7 днів", 10, 7),
    "month": PremiumPlan("Подарунок 30 днів", 30, 30)
}

# === REFERRAL SYSTEM (v1.5.0) ===
REFERRAL_BONUS_SIGNUP = 7      # Днів за кожного реферала
REFERRAL_BONUS_PREMIUM = 14    # Бонус якщо реферал купить Premium

# === GIFT SETTINGS (v1.5.0) ===
GIFT_PLATFORM_FEE = 0.10       # 10% комісія платформи
"""

# Оновлюємо PREMIUM_PLANS якщо потрібно
if 'PremiumPlan("Місяць", 50, 30)' in config_content:
    print("⚠️  Оновлюємо ціни Personal Premium (50→20, 500→200 Stars)")
    config_content = config_content.replace(
        'PremiumPlan("Місяць", 50, 30)',
        'PremiumPlan("Personal Premium (Місяць)", 20, 30)'
    )
    config_content = config_content.replace(
        'PremiumPlan("Рік", 500, 365)',
        'PremiumPlan("Personal Premium (Рік)", 200, 365)'
    )

# Додаємо нові константи в кінець
config_content += new_config

# Зберігаємо
with open('config.py', 'w', encoding='utf-8') as f:
    f.write(config_content)

print("✅ config.py успішно оновлено до v1.5.0!")
print("\nДодано:")
print("  - CHAT_PREMIUM_PLANS")
print("  - GIFT_PLANS")
print("  - REFERRAL_BONUS_SIGNUP")
print("  - REFERRAL_BONUS_PREMIUM")
print("  - GIFT_PLATFORM_FEE")
print("\nТепер можна запускати бота!")
