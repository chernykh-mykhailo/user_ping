import logging
import glob
from datetime import datetime
from pathlib import Path

class SmartSessionManager:
    """
    Керує файлами сесій Telethon.
    Шукає робочі, позначає биті, генерує нові назви.
    """
    def __init__(self, sessions_dir="sessions", base_name="account"):
        self.sessions_dir = Path(sessions_dir)
        self.base_name = base_name
        self.logger = logging.getLogger(__name__)
        
        # Створюємо папку, якщо її немає
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_best_session(self) -> str:
        """Повертає шлях до найновішої сесії ДЛЯ ЦЬОГО АКАУНТА (без розширення .session)"""
        # Шукаємо тільки файли, що починаються з нашого base_name
        pattern = self.sessions_dir / f"{self.base_name}*.session"
        files = glob.glob(str(pattern))
        
        if not files:
            # Навіть якщо файлів немає, повертаємо дефолтний шлях для спроби входу
            return str(self.sessions_dir / self.base_name)
        
        # Сортуємо за часом модифікації (спочатку найсвіжіші)
        files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
        
        # Повертаємо шлях без .session
        return files[0].replace(".session", "")

    def mark_broken(self, session_path: str):
        """Перейменовує биту сесію, щоб більше її не брати"""
        path = Path(f"{session_path}.session")
        if path.exists():
            broken_path = path.with_suffix(f".broken_{datetime.now().strftime('%H%M%S')}")
            try:
                path.rename(broken_path)
                self.logger.warning(f"❌ Сесія {path} позначена як БИТА та перейменована")
            except Exception as e:
                self.logger.error(f"Не вдалося перейменувати биту сесію: {e}")

    def generate_new_session_path(self) -> str:
        """Генерує нову унікальну назву для спроби входу"""
        new_name = f"{self.base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return str(self.sessions_dir / new_name)

    def cleanup_old_broken(self, limit=5):
        """Видаляє старі .broken файли, залишаючи лише останні N"""
        pattern = self.sessions_dir / "*.broken*"
        broken_files = glob.glob(str(pattern))
        
        if len(broken_files) <= limit:
            return
            
        broken_files.sort(key=lambda x: Path(x).stat().st_mtime)
        for f in broken_files[:-limit]:
            try:
                Path(f).unlink()
                self.logger.info(f"🗑 Видалено стару биту сесію: {f}")
            except: pass
