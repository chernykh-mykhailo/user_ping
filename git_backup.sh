#!/bin/bash

# === CONFIGURATION ===
# Завантажуємо налаштування з .env (шлях до .env відносно скрипта)
if [ -f "/home/ubuntu/user_ping/.env" ]; then
    export $(grep -v '^#' /home/ubuntu/user_ping/.env | xargs)
fi

# Використовуємо URL з .env або дефолтний, якщо він прописаний в скрипті для безпеки
# Але краще за все брати з $BACKUP_REPO_URL
PROJECT_DATA_DIR="/home/ubuntu/user_ping/data"
BACKUP_REPO_DIR="/home/ubuntu/user_ping_backups"
# Якщо в .env немає BACKUP_REPO_URL, скрипт зупиниться
if [ -z "$BACKUP_REPO_URL" ]; then
    echo "❌ Error: BACKUP_REPO_URL is not set in .env file"
    exit 1
fi

# === LOGIC ===
echo "🕒 Starting backup at $(date)"

# Створюємо папку для репозиторія, якщо її немає
if [ ! -d "$BACKUP_REPO_DIR/.git" ]; then
    echo "📦 Initializing backup repository..."
    mkdir -p "$BACKUP_REPO_DIR"
    cd "$BACKUP_REPO_DIR"
    git clone "$BACKUP_REPO_URL" .
fi

cd "$BACKUP_REPO_DIR"

# Копіюємо свіжі дані з бота
cp -r $PROJECT_DATA_DIR/* .

# Гіт команди
git add .
# Перевіряємо, чи є зміни для коміту
if git diff-index --quiet HEAD --; then
    echo "🌕 No changes to backup."
else
    git commit -m "Auto-backup: $(date +'%Y-%m-%d %H:%M:%S')"
    
    # Визначаємо поточну гілку
    CURRENT_BRANCH=$(git branch --show-current)
    if [ -z "$CURRENT_BRANCH" ]; then
        # Якщо гілки ще немає (порожній репо), створюємо main
        git checkout -b main
        CURRENT_BRANCH="main"
    fi
    
    echo "📤 Pushing to GitHub (branch: $CURRENT_BRANCH)..."
    git push -u origin "$CURRENT_BRANCH"
    echo "✅ Backup successfully pushed to GitHub!"
fi
