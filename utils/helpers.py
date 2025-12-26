"""
Utility helpers (DRY principle)
"""

def get_clean_chat_id(chat_id: int) -> str:
    """
    Конвертує ID чату в формат Bot API (-100...)
    
    Args:
        chat_id: ID чату
        
    Returns:
        Стандартизований ID чату
    """
    cid = str(chat_id)
    
    if not cid.startswith('-'):
        cid = f"-100{cid}"
    elif cid.startswith('-') and not cid.startswith('-100') and len(cid) > 10:
        cid = cid.replace('-', '-100')
    
    return cid

def get_user_name(first_name=None, last_name=None, username=None, user_id=None) -> str:
    """
    Повертає найкраще доступне ім'я користувача.
    Пріоритет: First Name -> Last Name -> Username -> ID -> Користувач
    """
    if first_name and first_name.strip():
        return first_name.strip()
    if last_name and last_name.strip():
        return last_name.strip()
    if username and username.strip():
        return username.strip()
    if user_id:
        return f"ID:{user_id}"
    return "Користувач"
