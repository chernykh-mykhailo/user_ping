# Telegram Ping Bot

Професійний бот для масових сповіщень у Telegram з системою преміуму.

## 🏗️ Архітектура

Проект побудований з використанням **SOLID принципів** та **ООП**:

### Структура проекту

```
user_ping/
├── main.py                     # Точка входу (Dependency Injection)
├── config.py                   # Конфігурація
├── core/                       # Бізнес-логіка
│   ├── database.py            # Repository Pattern (SRP, DIP)
│   └── __init__.py
├── handlers/                   # Обробники команд
│   ├── base_handler.py        # Базовий клас (OCP, LSP)
│   ├── admin_handler.py       # Адмін-команди (SRP)
│   ├── ping_handler.py        # Пінги (SRP)
│   ├── user_handler.py        # Користувацькі команди (SRP)
│   ├── payment_handler.py     # Платежі (SRP)
│   └── __init__.py
├── userbot/                    # Збір даних
│   ├── collector.py           # Telethon userbot (SRP)
│   └── __init__.py
└── utils/                      # Допоміжні функції
    ├── helpers.py             # Утиліти (DRY)
    └── __init__.py
```

### SOLID Принципи

- **S**ingle Responsibility: Кожен клас має одну відповідальність
- **O**pen/Closed: Відкритий для розширення, закритий для модифікації
- **L**iskov Substitution: Нащадки можуть замінити базовий клас
- **I**nterface Segregation: Інтерфейси для абстракції
- **D**ependency Inversion: Залежність від абстракцій, не реалізацій

## 🚀 Функції

### Для користувачів:
- `!кнагє` / `/all` — Заклик усіх
- `!емодзі` / `/emoji` — Заклик емодзі
- `!анрег` / `/unreg` — Тимчасово вимкнути пінги
- `!суперанрег` / `/superunreg` — Постійно вимкнути (Premium)
- `!рег` / `/reg` — Увімкнути пінги
- `/balance` — Статус Premium

### Для адміністраторів:
- `!збір` / `/sync` — Синхронізація учасників
- `!стата` / `/stats` — Статистика

### Premium:
- `/premium` — Купити Premium
- `/buy_month` — Місяць (50 Stars)
- `/buy_year` — Рік (500 Stars)

## 📦 Встановлення

### Перший запуск

1. **Клонуйте репозиторій:**
```bash
git clone https://github.com/YOUR_USERNAME/telegram-ping-bot.git
cd telegram-ping-bot
```

2. **Створіть конфігурацію:**
```bash
cp config.example.py config.py
```

3. **Відредагуйте `config.py`:**
- `API_ID` та `API_HASH` - отримайте на https://my.telegram.org
- `BOT_TOKEN` - отримайте від @BotFather
- `PAYMENT_TOKEN` - налаштуйте через @BotFather → Payments
- `ADMIN_USER_ID` - ваш Telegram ID (від @userinfobot)

4. **Встановіть залежності:**
```bash
pip install -r requirements.txt
```

5. **Запустіть:**
```bash
python main.py
```

### Docker (рекомендовано для продакшену)

1. **Створіть `.env` файл** з вашими налаштуваннями:
```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
PAYMENT_TOKEN=your_payment_token
ADMIN_USER_ID=your_telegram_id
```

2. **Зберіть Docker образ:**
```bash
docker build -t telegram-ping-bot .
```

3. **Запустіть контейнер:**
```bash
docker run -d \
  --name ping-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  telegram-ping-bot
```

4. **Перегляд логів:**
```bash
docker logs -f ping-bot
```

5. **Зупинка/перезапуск:**
```bash
docker stop ping-bot
docker start ping-bot
docker restart ping-bot
```

**Примітка:** Docker образ включає всі необхідні шрифти (DejaVu, Liberation, Noto) для коректної роботи `/set_sticker` на Linux.

### Docker Compose (найпростіший спосіб)

1. **Створіть `.env` файл** (як вище)

2. **Запустіть:**
```bash
docker-compose up -d
```

3. **Перегляд логів:**
```bash
docker-compose logs -f
```

4. **Зупинка:**
```bash
docker-compose down
```

5. **Перезбірка після змін:**
```bash
docker-compose up -d --build
```


### Завантаження на GitHub

Детальні інструкції в [GIT_SETUP.md](GIT_SETUP.md)

**Швидкий старт:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/telegram-ping-bot.git
git push -u origin main
```

⚠️ **Важливо:** Створюйте **приватний** репозиторій!

## 🔧 Конфігурація

Відредагуйте `config.py`:

```python
API_ID = your_api_id
API_HASH = 'your_api_hash'
BOT_TOKEN = "your_bot_token"
PAYMENT_TOKEN = "your_payment_token"
```

## 🎯 Переваги рефакторингу

### Було (main_legacy.py):
- ❌ 530+ рядків в одному файлі
- ❌ Важко тестувати
- ❌ Складно розширювати
- ❌ Дублювання коду

### Стало:
- ✅ Модульна структура
- ✅ Легко тестувати кожен компонент
- ✅ Просто додавати нові функції
- ✅ DRY (Don't Repeat Yourself)
- ✅ SOLID принципи
- ✅ Type hints
- ✅ Dependency Injection

## 📝 Приклад розширення

Додати новий хендлер:

```python
from handlers.base_handler import BaseHandler

class MyHandler(BaseHandler):
    def register_handlers(self):
        @self.router.message(Command("mycommand"))
        async def my_command(message: Message):
            await message.answer("Hello!")
```

Зареєструвати в `main.py`:

```python
self.my_handler = MyHandler(self.chat_repo, self.premium_repo)
self.dp.include_router(self.my_handler.get_router())
```

## 🧪 Тестування

Кожен компонент можна тестувати окремо:

```python
# Тест Repository
db = JSONDatabase("test.json")
repo = ChatRepository(db)
repo.save_user("123", "456", "Test")
```

## 📄 Ліцензія

MIT License
