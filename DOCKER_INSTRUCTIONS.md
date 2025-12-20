# Docker запуск бота

## 🧪 Тестовий бот

```bash
docker-compose up -d
```

Або з rebuild:
```bash
docker-compose up -d --build
```

**Що використовується:**
- Конфіг: `config_test.py`
- База: `users_data_test.json`
- Контейнер: `my_ping_bot_test`

---

## 🚀 Продакшн бот

```bash
docker-compose -f docker-compose-prod.yml up -d
```

Або з rebuild:
```bash
docker-compose -f docker-compose-prod.yml up -d --build
```

**Що використовується:**
- Конфіг: `config_prod.py`
- База: `users_data.json`
- Контейнер: `my_ping_bot_prod`

---

## 📋 Корисні команди

### Переглянути логи
```bash
# Тест
docker-compose logs -f

# Prod
docker-compose -f docker-compose-prod.yml logs -f
```

### Зупинити бота
```bash
# Тест
docker-compose down

# Prod
docker-compose -f docker-compose-prod.yml down
```

### Перезапустити
```bash
# Тест
docker-compose restart

# Prod
docker-compose -f docker-compose-prod.yml restart
```

### Видалити контейнер і пересобрати
```bash
# Тест
docker-compose down
docker-compose up -d --build

# Prod
docker-compose -f docker-compose-prod.yml down
docker-compose -f docker-compose-prod.yml up -d --build
```

---

## 🔄 Одночасний запуск

Можна запустити обидва боти одночасно (різні контейнери, різні бази):

```bash
# Запустити тест
docker-compose up -d

# Запустити prod
docker-compose -f docker-compose-prod.yml up -d
```

Вони не будуть конфліктувати, бо:
- Різні імена контейнерів
- Різні бази даних
- Різні токени ботів

---

## ⚠️ Важливо

1. **Перед запуском prod** - замініть токени в `config_prod.py`
2. **Бекап бази** - перед оновленням зробіть копію `users_data.json`
3. **Логи** - перевіряйте логи після запуску: `docker-compose logs -f`
