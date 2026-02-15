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
- `fonts-dejavu` + `fonts-dejavu-core` + `fonts-dejavu-extra` - DejaVu Sans (основний)
- `fonts-liberation` + `fonts-liberation2` - Liberation Sans (запасний)
- `fonts-noto-core` - Noto Sans (додатковий)
- `fonts-freefont-ttf` - FreeSans (додатковий)
- `fonts-ubuntu` - Ubuntu (додатковий)

**Примітка:** Color emoji fonts не використовуються, бо PIL погано їх підтримує на Linux.

## Пріоритет шрифтів
**Для тексту та емодзі (однаковий список):**
1. **Linux** (для Docker): DejaVu Sans → Liberation Sans → Noto Sans → FreeSans → Ubuntu
2. **Windows** (для локальної розробки): Arial → Segoe UI → Calibri

**Розмір:**
- Текст: базовий (height/15) - збільшено для кращої читабельності
- Емодзі: збільшений (базовий × 1.4)

## Troubleshooting

### Перевірка шрифтів у контейнері
```bash
# Запустіть тестовий скрипт
docker exec -it ping_bot python test_fonts.py

# Або перевірте вручну
docker exec -it ping_bot ls -la /usr/share/fonts/truetype/dejavu/
docker exec -it ping_bot ls -la /usr/share/fonts/truetype/liberation/
```

### Шрифти не встановлюються
```bash
# Увійдіть в контейнер
docker exec -it ping_bot bash

# Перевірте наявність шрифтів
ls -la /usr/share/fonts/truetype/dejavu/

# Якщо порожньо - встановіть вручну
apt-get update
apt-get install -y fonts-dejavu fonts-dejavu-core fonts-liberation fonts-liberation2
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
- Розмір образу збільшиться на ~20MB через шрифти
- Шрифти встановлюються один раз при збірці
- Кеш APT очищається для економії місця
- Емодзі відображаються базовим шрифтом (не color emoji)
