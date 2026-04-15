"""
StringSession Manager - зберігає сесії як рядки в JSON (без SQLite файлів)
Це повністю усуває проблему 'readonly database' в Docker
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict
from telethon.sessions import StringSession


class StringSessionManager:
    """
    Керує сесіями Telethon у вигляді рядків, зберігаючи їх у JSON файлі.
    Це усуває всі проблеми з правами доступу до SQLite файлів у Docker.
    """
    
    def __init__(self, storage_file: str = "data/sessions.json"):
        self.storage_file = Path(storage_file)
        self.logger = logging.getLogger(__name__)
        
        # Створюємо папку для зберігання
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            # Перевіримо можливість запису відразу
            test_file = self.storage_file.parent / f".write_test_{self.storage_file.name}"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            self.logger.critical(f"❌ КРИТИЧНА ПОМИЛКА: Немає прав на запис у {self.storage_file.parent}: {e}")
        
        # Ініціалізуємо файл, якщо його немає
        if not self.storage_file.exists():
            self._save_sessions({})
    
    def _load_sessions(self) -> Dict[str, str]:
        """Завантажує всі сесії з JSON"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Помилка завантаження сесій: {e}")
            return {}
    
    def _save_sessions(self, sessions: Dict[str, str]):
        """Зберігає всі сесії в JSON"""
        try:
            # Створюємо тимчасовий файл для безпечного запису (atomic write)
            temp_file = self.storage_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
                f.flush()
                import os
                os.fsync(f.fileno())
            
            # Перейменовуємо тимчасовий файл у основний
            temp_file.replace(self.storage_file)
            self.logger.info(f"✅ Файл сесій оновлено: {self.storage_file}")
        except Exception as e:
            self.logger.error(f"❌ ПОМИЛКА ЗБЕРЕЖЕННЯ СЕСІЙ у {self.storage_file}: {e}")
            self.logger.error(f"Дані, які не збереглися: {list(sessions.keys())}")
    
    def get_session(self, account_name: str) -> Optional[StringSession]:
        """
        Отримує StringSession для акаунта
        Повертає None, якщо сесія не знайдена
        """
        sessions = self._load_sessions()
        session_string = sessions.get(account_name)
        
        if session_string:
            self.logger.info(f"📂 Завантажено сесію для {account_name}")
            return StringSession(session_string)
        else:
            self.logger.info(f"🆕 Створюю нову сесію для {account_name}")
            return StringSession()  # Порожня сесія для нового логіну
    
    def save_session(self, account_name: str, session: StringSession):
        """Зберігає StringSession для акаунта"""
        sessions = self._load_sessions()
        session_string = session.save()
        
        if session_string:
            sessions[account_name] = session_string
            self._save_sessions(sessions)
            self.logger.info(f"💾 Сесію {account_name} збережено успішно")
        else:
            self.logger.warning(f"⚠️ Спроба зберегти порожню сесію для {account_name}")
    
    def delete_session(self, account_name: str):
        """Видаляє сесію акаунта"""
        sessions = self._load_sessions()
        if account_name in sessions:
            del sessions[account_name]
            self._save_sessions(sessions)
            self.logger.info(f"🗑 Сесію {account_name} видалено")
            return True
        return False
    
    def list_sessions(self) -> list:
        """Повертає список всіх збережених акаунтів"""
        sessions = self._load_sessions()
        return list(sessions.keys())
    
    def has_session(self, account_name: str) -> bool:
        """Перевіряє, чи існує сесія для акаунта"""
        sessions = self._load_sessions()
        return account_name in sessions and bool(sessions[account_name])
