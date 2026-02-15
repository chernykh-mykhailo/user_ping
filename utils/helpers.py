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
        HTML-код для відображення
    """
    if not emoji_data:
        return ""

    if str(emoji_data).startswith("tg-emoji:"):
        emoji_id = emoji_data.split(":")[1]
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

    return html.escape(str(emoji_data))


def extract_custom_emoji_id(message) -> str:
    """
    Витягує custom_emoji_id з повідомлення, якщо воно там є
    """
    if not message.entities:
        return None

    for entity in message.entities:
        if entity.type == "custom_emoji":
            return entity.custom_emoji_id

    return None


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
    Пріоритет: First Name -> Last Name -> Username -> ID -> Користувач
    """
    name_parts = []

    # 1. Спроба об'єднати Ім'я + Прізвище
    if first_name and first_name.strip():
        name_parts.append(first_name.strip())

    if last_name and last_name.strip():
        name_parts.append(last_name.strip())

    if name_parts:
        return " ".join(name_parts)[:20]  # Обмежуємо довжину для бази

    # 2. Якщо немає Імені/Прізвища - беремо Username
    if username and username.strip():
        username = username.strip().lstrip("@")
        return f"@{username}"[:20]

    # 3. Якщо взагалі нічого немає - fallback на ID
    if user_id:
        return f"ID:{user_id}"

    return "Користувач"
