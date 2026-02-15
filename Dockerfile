# Використовуємо легкий образ Python
FROM python:3.11-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файл залежностей
COPY requirements.txt .

# Встановлюємо системні залежності та шрифти для PIL/Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-liberation \
    fonts-liberation2 \
    fonts-noto-core \
    fonts-freefont-ttf \
    fonts-ubuntu \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо бібліотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо всі файли проекту (включаючи сесію, якщо вона не в volumes)
COPY . .

# Запускаємо бота
CMD ["python", "main.py"]