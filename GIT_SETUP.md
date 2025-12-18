# Git Setup Instructions

## Перше завантаження на GitHub

### 1. Ініціалізація Git
```bash
cd d:\Personal\IT\Telegram\user_ping
git init
```

### 2. Додати файли
```bash
git add .
```

### 3. Перший коміт
```bash
git commit -m "Initial commit: Telegram Ping Bot with SOLID architecture"
```

### 4. Створити приватний репозиторій на GitHub
1. Перейдіть на https://github.com/new
2. Назва: `telegram-ping-bot` (або будь-яка інша)
3. **Обов'язково виберіть "Private"** ✅
4. НЕ додавайте README, .gitignore або ліцензію (вони вже є)
5. Натисніть "Create repository"

### 5. Підключити до GitHub
```bash
# Замініть YOUR_USERNAME на ваш GitHub username
git remote add origin https://github.com/YOUR_USERNAME/telegram-ping-bot.git
git branch -M main
git push -u origin main
```

## Подальша робота

### Додати зміни
```bash
git add .
git commit -m "Опис змін"
git push
```

### Отримати зміни
```bash
git pull
```

## Важливо! 🔒

Файли, які **НЕ** потраплять у Git (захищені .gitignore):
- ✅ `*.session` - сесії Telegram
- ✅ `users_data.json` - база даних
- ✅ `__pycache__/` - кеш Python
- ✅ `main copy.py` - резервні копії
- ✅ `main_legacy.py` - старий код

Файли, які **БУДУТЬ** у Git:
- ✅ Весь код (`main.py`, `handlers/`, `core/`, etc.)
- ✅ `config.example.py` - приклад конфігу
- ✅ `requirements.txt` - залежності
- ✅ `README.md` - документація
- ⚠️ `config.py` - **УВАГА!** Містить токени!

## Захист config.py

Якщо хочете **повністю** виключити `config.py` з Git:

1. Відредагуйте `.gitignore`:
```bash
# Розкоментуйте останній рядок:
config.py
```

2. Видаліть з Git (якщо вже додали):
```bash
git rm --cached config.py
git commit -m "Remove config.py from tracking"
git push
```

3. Тепер `config.py` залишиться локально, але не потрапить у Git

## Клонування на іншому ПК

```bash
git clone https://github.com/YOUR_USERNAME/telegram-ping-bot.git
cd telegram-ping-bot

# Створіть config.py з прикладу
cp config.example.py config.py

# Відредагуйте config.py своїми даними
# nano config.py  # або будь-який редактор

# Встановіть залежності
pip install -r requirements.txt

# Запустіть
python main.py
```

## Корисні команди

```bash
# Подивитися статус
git status

# Подивитися історію
git log --oneline

# Створити нову гілку
git checkout -b feature-name

# Перемкнутися на main
git checkout main

# Об'єднати гілку
git merge feature-name
```

## Troubleshooting

### Якщо випадково закомітили токени:

```bash
# Видаліть з історії (НЕБЕЗПЕЧНО!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config.py" \
  --prune-empty --tag-name-filter cat -- --all

# Примусово запушіть
git push origin --force --all
```

**Краще:** Змініть всі токени на нові через @BotFather та my.telegram.org
