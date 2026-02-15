# Фікс /set_sticker для Docker/Linux

## Проблема
На Linux у Docker контейнері `/set_sticker` не працює через відсутність шрифтів з підтримкою кирилиці.

## Рішення

### 1. Оновлення коду
Файли вже оновлені:
- ✅ `utils/image_utils.py` - додано Linux шрифти (DejaVu, Liberation, Noto)
- ✅ `Dockerfile` - додано встановлення шрифтів
- ✅ `.dockerignore` - оптимізація образу

### 2. Перезбірка Docker образу

#### Варіант A: Docker Compose (рекомендовано)
```bash
docker-compose down
docker-compose up -d --build
```

#### Варіант B: Docker напряму
```bash
docker stop ping-bot
docker rm ping-bot
docker build -t telegram-ping-bot .
docker run -d \
  --name ping-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  telegram-ping-bot
```

### 3. Перевірка
1. Надішліть стікер у чат
2. Відповідайте на нього командою `/set_sticker`
3. Надішліть `/stats` або `/summary` для перевірки

## Встановлені шрифти
Docker образ тепер включає:
- `fonts-dejavu` - DejaVu Sans (основний для кирилиці)
- `fonts-liberation` - Liberation Sans
- `fonts-noto` - Noto Sans + Noto Emoji
- `fonts-freefont-ttf` - FreeSans

## Пріоритет шрифтів
1. **Linux** (для Docker): DejaVu → Liberation → Noto → FreeSans
2. **Windows** (для локальної розробки): Arial → Segoe UI → Calibri

## Troubleshooting

### Шрифти не встановлюються
```bash
# Увійдіть в контейнер
docker exec -it ping-bot bash

# Перевірте наявність шрифтів
ls -la /usr/share/fonts/truetype/dejavu/

# Якщо порожньо - встановіть вручну
apt-get update
apt-get install -y fonts-dejavu fonts-liberation fonts-noto
```

### Стікер все ще не працює
```bash
# Перегляньте логи
docker logs -f ping-bot

# Шукайте помилки типу:
# "Error creating summary image: ..."
```

### Тест локально (без Docker)
```python
# Запустіть config_test.py
python config_test.py
```

## Додаткова інформація
- Розмір образу збільшиться на ~50MB через шрифти
- Шрифти встановлюються один раз при збірці
- Кеш APT очищається для економії місця
