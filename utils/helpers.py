"""
Utility helpers (DRY principle)
"""

import html


def render_emoji(emoji_data: str) -> str:
    """
    Рендерить емодзі (звичайний або преміум)

    Args:
        emoji_data: Рядок з емодзі або формат 'tg-emoji:ID'

    Returns:
        HTML-код для відображення в повідомленнях
    """
    if not emoji_data:
        return ""

    if str(emoji_data).startswith("tg-emoji:"):
        emoji_id = emoji_data.split(":")[1]
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

    return html.escape(str(emoji_data))


def get_emoji_id_for_button(emoji_data: str) -> tuple[str, str]:
    """
    Підготовлює емодзі для InlineKeyboardButton з підтримкою преміум-емодзі
    
    Args:
        emoji_data: Рядок з емодзі або формат 'tg-emoji:ID'

    Returns:
        Tuple (text, icon_custom_emoji_id):
        - text: текст для відображення на кнопці (порожній рядок для преміум-емодзі)
        - icon_custom_emoji_id: ID преміум-емодзі або None
    """
    if not emoji_data:
        return "", None

    # Для преміум-емодзі повертаємо порожній рядок (Telegram замінить його на кастомний емодзі)
    if str(emoji_data).startswith("tg-emoji:"):
        emoji_id = emoji_data.split(":")[1]
        return "", emoji_id

    return str(emoji_data), None


def extract_emoji_info(message) -> dict:
    """
    Витягує інформацію про емодзі з повідомлення.
    Повертає dict з ключами 'custom_id' та 'emoji'.
    """
    res = {"custom_id": None, "emoji": None}

    # 1. Шукаємо преміум-емодзі в сутностях
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                res["custom_id"] = entity.custom_emoji_id
                # Спробуємо також витягти сам символ, якщо він є
                try:
                    res["emoji"] = message.text[
                        entity.offset : entity.offset + entity.length
                    ]
                except Exception:
                    pass
                return res

    # 2. Якщо не знайшли преміум, шукаємо звичайний емодзі в тексті (після команди)
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            candidate = parts[1].strip()
            # Беремо тільки перший символ/емодзі
            if candidate:
                res["emoji"] = candidate
                # Якщо це просто текст, ми його збережемо як є (до 10 символів)

    return res


def extract_custom_emoji_id(message) -> str:
    """
    Backward compatibility: витягує ТІЛЬКИ custom_emoji_id
    """
    info = extract_emoji_info(message)
    return info.get("custom_id")


def get_clean_chat_id(chat_id: int) -> str:
    """
    Конвертує ID чату в формат Bot API (-100...)

    Args:
        chat_id: ID чату

    Returns:
        Стандартизований ID чату
    """
    cid = str(chat_id)

    if not cid.startswith("-"):
        cid = f"-100{cid}"
    elif cid.startswith("-") and not cid.startswith("-100") and len(cid) > 10:
        cid = cid.replace("-", "-100")

    return cid


def get_user_name(first_name=None, last_name=None, username=None, user_id=None, chat_repo=None) -> str:
    """
    Повертає найкраще доступне ім'я користувача.
    v2.10.16: Очищує від емодзі, бере ТІЛЬКИ перше ім'я, обмежує довжину, дозволяє апостроф.
    v2.11.0: Якщо ім'я - це емодзі, використовує username або генерує випадкове ім'я тваринки/персонажа.
    v2.11.0: Перевіряє кастомне ім'я (setname) для Premium користувачів.
    """
    import re

    # v2.11.0: Перевіряємо кастомне ім'я (Premium функція /setname)
    if chat_repo and user_id:
        custom_name = chat_repo.get_user_setting(user_id, "custom_name")
        if custom_name:
            return custom_name[:20]

    name = ""

    # 1. Пріоритет - First Name (якщо це не просто емодзі)
    if first_name and first_name.strip():
        # Перевіряємо, чи є в імені хоча б одна буква/цифра
        if re.search(r'[a-zA-Zа-яА-ЯіІїЇєЄ0-9]', first_name):
            name = first_name.strip()
        else:
            # Якщо це тільки емодзі - ігноруємо
            name = ""
    
    # 2. Якщо немає - Last Name
    if not name and last_name and last_name.strip():
        if re.search(r'[a-zA-Zа-яА-ЯіІїЇєЄ0-9]', last_name):
            name = last_name.strip()
        else:
            name = ""
    
    # 3. Якщо немає - Username
    if not name and username and username.strip():
        name = username.strip().lstrip("@")
    
    # 4. Fallback - Генеруємо випадкове ім'я або беремо з бази
    if not name:
        # Спроба взяти згенероване ім'я з бази даних
        if chat_repo and user_id:
            user_data = chat_repo.get_user_data(user_id)
            if user_data and isinstance(user_data, dict):
                generated_name = user_data.get("generated_name")
                if generated_name:
                    return generated_name
        
        # Генеруємо нове випадкове ім'я
        name = generate_random_name(chat_repo, user_id)
    
    # ОЧИЩЕННЯ:
    # шукаємо першу послідовність букв, цифр або дозволених знаків
    match = re.search(r"[\w\.\-\'’ʼ]+", name)
    if match:
        name = match.group(0)
    else:
        name = re.sub(r"[^\w\s\.\-\'’ʼ]", "", name)
        name = name.split()[0] if name.split() else "Користувач"

    # Очищення крапок/дефізів на початку/кінці
    name = name.strip(". -")

    # Обмеження довжини
    if len(name) > 12:
        name = name[:11] + "…"

    return name.strip() or "Користувач"


def generate_random_name(chat_repo=None, user_id=None) -> str:
    """
    Генерує випадкове ім'я тваринки/персонажа для користувача без імені.
    Зберігає його в базу даних для повторного використання.
    
    Returns:
        Випадкове ім'я зі списку
    """
    import random
    
    # Список випадкових імен тваринок/персонажів
    random_names = [
        # Тварини
        "Ведмідь", "Вовк", "Лис", "Заєць", "Білка", "Єнот", "Панда", "Коала",
        "Тигр", "Лев", "Пума", "Леопард", "Рись", "Барс", "Носоріг", "Бегемот",
        "Слон", "Жираф", "Зебра", "Горила", "Орангутан", "Чімпанзі", "Мавпа",
        "Дельфін", "Кит", "Акула", "Черепаха", "Змія", "Ящірка", "Жаба",
        "Пташка", "Орел", "Сокіл", "Сова", "Папуга", "Качка", "Гусь", "Ластівка",
        # Міфічні істоти
        "Дракон", "Єдиноріг", "Фенікс", "Грифон", "Кентавр", "Тролль", "Гном",
        "Ельф", "Гоблін", "Маг", "Чарівник", "Рицар", "Привид", "Вампир",
        # Інші персонажі
        "Пірат", "Ковбой", "Ніндзя", "Самурай", "Робот", "Пришелець",
        "Супергерой", "Злодій", "Детектив", "Шпигун", "Космонавт", "Дідько",
        # М'які імена
        "Пушистик", "Соня", "Зірочка", "Мішка", "Кіт", "Пес", "Риба",
        "Бандит", "Штучка", "Малашка", "Кроха", "Смайлик", "Джек", "Том"
    ]
    
    # Вибираємо випадкове ім'я
    random_name = random.choice(random_names)
    
    # Зберігаємо в базу, якщо є доступ
    if chat_repo and user_id:
        try:
            chat_repo.set_user_setting(user_id, "generated_name", random_name)
        except:
            pass  # Якщо не вдалося зберегти, просто повертаємо ім'я
    
    return random_name
