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
