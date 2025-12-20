# Скрипти для зручного запуску

## Тестовий бот (за замовчуванням)
```bash
python main.py
```

## Продакшн бот
```bash
# Windows PowerShell
$env:BOT_MODE="prod"; python main.py

# Windows CMD
set BOT_MODE=prod && python main.py

# Linux/Mac
BOT_MODE=prod python main.py
```

## Структура конфігів

- `config.py` - автоматично вибирає test або prod
- `config_test.py` - тестовий бот (8465790358...)
- `config_prod.py` - продакшн бот (замініть токен!)

## Бази даних

- Тест: `users_data_test.json`
- Prod: `users_data.json`

Бази окремі, тому тестування не вплине на продакшн!
