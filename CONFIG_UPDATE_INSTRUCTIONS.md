# ВАЖЛИВО: Оновіть ваш config.py!

Додайте ці рядки в кінець вашого `config.py`:

```python
# === PREMIUM PRICING (v1.5.0) ===
from dataclasses import dataclass

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
```

ВАЖЛИВО: Замініть старі PREMIUM_PLANS на нові (ціни знижено з 50/500 на 20/200 Stars)!
