from typing import Dict, List, Optional, Any
from core.storage import JSONStorage


class EmojiPackDomain:
    """
    Управління наборами кастомних емодзі бота (Bot-Owned Packs)
    v2.10.0: Система автоматичного створення та наповнення паків
    """

    def __init__(self, storage: JSONStorage):
        self.storage = storage

    def get_packs(self) -> List[Dict[str, Any]]:
        """Повертає список всіх зареєстрованих паків бота"""
        data = self.storage.load()
        return data.get("emoji_packs", [])

    def get_active_pack(self) -> Optional[Dict[str, Any]]:
        """Повертає поточний активний пак (який ще не заповнений)"""
        packs = self.get_packs()
        for pack in packs:
            if pack.get("count", 0) < 200:
                return pack
        return None

    def register_pack(self, name: str, title: str, count: int = 0) -> None:
        """Реєструє новий пак у базі"""
        data = self.storage.load()
        if "emoji_packs" not in data:
            data["emoji_packs"] = []

        # Уникаємо дублікатів
        for pack in data["emoji_packs"]:
            if pack["name"] == name:
                pack["title"] = title
                pack["count"] = count
                self.storage.save(data)
                return

        data["emoji_packs"].append({"name": name, "title": title, "count": count})
        self.storage.save(data)

    def increment_pack_count(self, name: str) -> None:
        """Збільшує лічильник емодзі в паку"""
        data = self.storage.load()
        if "emoji_packs" in data:
            for pack in data["emoji_packs"]:
                if pack["name"] == name:
                    pack["count"] = pack.get("count", 0) + 1
                    self.storage.save(data)
                    return

    def get_registered_emoji(self, original_custom_id: str) -> Optional[str]:
        """Повертає ID нашої копії емодзі, якщо він вже є в нашому паку"""
        data = self.storage.load()
        mapping = data.get("emoji_mapping", {}).get(original_custom_id)

        if not mapping:
            return None

        if isinstance(mapping, dict):
            return mapping.get("bot_id")

        return mapping  # Legacy string support

    def save_emoji_mapping(
        self, original_custom_id: str, bot_custom_id: str, alt: str = "✨"
    ) -> None:
        """Зберігає зв'язок між оригінальним емодзі та нашою копією"""
        data = self.storage.load()
        if "emoji_mapping" not in data:
            data["emoji_mapping"] = {}

        # v2.10.1: Зберігаємо як об'єкт з alt-символом
        data["emoji_mapping"][original_custom_id] = {
            "bot_id": bot_custom_id,
            "alt": alt,
        }
        self.storage.save(data)

    def get_all_cloned_emojis(self) -> List[Dict[str, str]]:
        """Повертає список всіх унікальних емодзі бота з їх символами"""
        data = self.storage.load()
        mapping = data.get("emoji_mapping", {})

        # Витягуємо унікальні за bot_id
        unique_emojis = {}
        for original, val in mapping.items():
            if isinstance(val, dict):
                bot_id = val.get("bot_id")
                alt = val.get("alt", "✨")
                if bot_id:
                    unique_emojis[bot_id] = alt
            elif isinstance(val, str):
                # Legacy support
                unique_emojis[val] = "✨"

        return [{"id": eid, "alt": alt} for eid, alt in unique_emojis.items()]
