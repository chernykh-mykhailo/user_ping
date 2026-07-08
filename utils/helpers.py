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


def render_emoji_for_button(emoji_data: str) -> str:
    """
    Рендерить емодзі для кнопок (InlineKeyboardButton)
    Кнопки не підтримують HTML, тому повертаємо тільки символ емодзі
    
    Args:
        emoji_data: Рядок з емодзі або формат 'tg-emoji:ID'

    Returns:
        Текст емодзі для відображення на кнопці
    """
    if not emoji_data:
        return ""

    # Для преміум-емодзі повертаємо заміну (✨), оскільки кнопки не підтримують tg-emoji
    if str(emoji_data).startswith("tg-emoji:"):
        return "✨"

    return str(emoji_data)


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


def get_user_name(first_name=None, last_name=None, username=None, user_id=None) -> str:
    """
    Повертає найкраще доступне ім'я користувача.
    v2.10.16: Очищує від емодзі, бере ТІЛЬКИ перше ім'я, обмежує довжину, дозволяє апостроф.
    """
    import re

    name = ""

    # 1. Пріоритет - First Name
    if first_name and first_name.strip():
        name = first_name.strip()
    # 2. Якщо немає - Last Name
    elif last_name and last_name.strip():
        name = last_name.strip()
    # 3. Якщо немає - Username
    elif username and username.strip():
        name = username.strip().lstrip("@")
    # 4. Fallback - ID
    elif user_id:
        name = str(user_id)
    else:
        name = "Користувач"

    # ОЧИЩЕННЯ (v2.10.21):
    # шукаємо першу послідовність букв, цифр або дозволених знаків (., -, апостроф)
    # це дозволяє ігнорувати емодзі на початку та коректно витягувати перше слово

    # Дозволені символи крім \w: крапка, дефіс, апострофи
    match = re.search(r"[\w\.\-\'’ʼ]+", name)
    if match:
        name = match.group(0)
    else:
        # Fallback: видаляємо все заборонене і беремо перше слово
        name = re.sub(r"[^\w\s\.\-\'’ʼ]", "", name)
        name = name.split()[0] if name.split() else "Користувач"

    # Dodatkove ochyschennya: vydalyayemo krapyky/defisy na pochatku/kinci
    name = name.strip(". -")

    # в) Обмежуємо довжину (наприклад, 12 символів)
    if len(name) > 12:
        name = name[:11] + "…"

    return name.strip() or "Користувач"
