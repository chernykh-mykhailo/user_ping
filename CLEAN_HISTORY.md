# Очищення Git історії від чутливих даних

## ⚠️ ВАЖЛИВО: Ви вже змінили BOT_TOKEN, тому старий токен більше не працює. Це добре!

## Варіант 1: Створити новий репозиторій (РЕКОМЕНДОВАНО)

### 1. Видаліть старий репозиторій на GitHub
1. Перейдіть на https://github.com/chernykh-mykhailo/user_ping
2. Settings → Danger Zone → Delete this repository

### 2. Створіть новий з чистою історією
```bash
cd d:\Personal\IT\Telegram\user_ping

# Видаліть Git папку
Remove-Item -Recurse -Force .git

# Ініціалізуйте заново
git init
git add .
git commit -m "Initial commit: Telegram Ping Bot v1.0.0"

# Створіть НОВИЙ приватний репозиторій на GitHub, потім:
git remote add origin https://github.com/chernykh-mykhailo/user_ping.git
git branch -M main
git push -u origin main --force
```

## Варіант 2: Очистити історію існуючого репозиторію (СКЛАДНІШЕ)

### Використання git filter-branch

```bash
cd d:\Personal\IT\Telegram\user_ping

# Видаліть config.py з усієї історії
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config.py" \
  --prune-empty --tag-name-filter cat -- --all

# Очистіть рефлоги
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Примусово запушіть (ПЕРЕЗАПИШЕ історію на GitHub!)
git push origin --force --all
```

⚠️ **УВАГА:** Це перезапише історію на GitHub!

## Варіант 3: Використати BFG Repo-Cleaner (НАЙШВИДШЕ)

### 1. Завантажте BFG
https://rtyley.github.io/bfg-repo-cleaner/

### 2. Запустіть очищення
```bash
# Створіть резервну копію
git clone --mirror https://github.com/chernykh-mykhailo/user_ping.git user_ping-backup.git

# Видаліть config.py з історії
java -jar bfg.jar --delete-files config.py user_ping-backup.git

# Очистіть
cd user_ping-backup.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Запушіть
git push --force
```

## ✅ Рекомендація

**Варіант 1** — найпростіший і найбезпечніший:
1. Видаліть старий репозиторій
2. Створіть новий
3. Запушіть тільки актуальний код (без config.py)

Старі токени вже не працюють (ви їх змінили), тому немає ризику.

## Після очищення

Переконайтеся, що `config.py` в `.gitignore`:
```bash
git check-ignore -v config.py
# Має показати: .gitignore:62:config.py	config.py
```

Перевірте, що config.py не в Git:
```bash
git ls-files | grep config.py
# Не має нічого показати
```
