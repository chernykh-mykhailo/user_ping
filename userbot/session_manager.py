import os
import glob
import logging
from datetime import datetime

class SmartSessionManager:
    """
    Керує файлами сесій Telethon.
    Шукає робочі, позначає биті, генерує нові назви.
    """
    def __init__(self, sessions_dir="sessions", base_name="account"):
        self.sessions_dir = sessions_dir
        self.base_name = base_name
        self.logger = logging.getLogger(__name__)
        
        if not os.path.exists(sessions_dir):
            os.makedirs(sessions_dir)

    def get_best_session(self):
        """Повертає шлях до найновішої сесії ДЛЯ ЦЬОГО АКАУНТА (без розширення .session)"""
        # Шукаємо тільки файли, що починаються з нашого base_name
        pattern = os.path.join(self.sessions_dir, f"{self.base_name}*.session")
        files = glob.glob(pattern)
        
        if not files:
            # Навіть якщо файлів немає, повертаємо дефолтний шлях для спроби входу
            return os.path.join(self.sessions_dir, self.base_name)
        
        # Сортуємо за часом модифікації (спочатку найсвіжіші)
        files.sort(key=os.path.getmtime, reverse=True)
        
        # Повертаємо шлях без .session
        return files[0].replace(".session", "")

    def mark_broken(self, session_path):
        """Перейменовує биту сесію, щоб більше її не брати"""
        full_path = f"{session_path}.session"
        if os.path.exists(full_path):
            broken_path = f"{full_path}.broken_{datetime.now().strftime('%H%M%S')}"
            try:
                os.rename(full_path, broken_path)
                self.logger.warning(f"❌ Сесія {full_path} позначена як БИТА та перейменована")
            except Exception as e:
                self.logger.error(f"Не вдалося перейменувати биту сесію: {e}")

    def generate_new_session_path(self):
        """Генерує нову унікальну назву для спроби входу"""
        new_name = f"{self.base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return os.path.join(self.sessions_dir, new_name)

    def cleanup_old_broken(self, limit=5):
        """Видаляє старі .broken файли, залишаючи лише останні N"""
        broken_files = glob.glob(os.path.join(self.sessions_dir, "*.broken*"))
        if len(broken_files) <= limit:
            return
            
        broken_files.sort(key=os.path.getmtime)
        for f in broken_files[:-limit]:
            try:
                os.remove(f)
                self.logger.info(f"🗑 Видалено стару биту сесію: {f}")
            except: pass
