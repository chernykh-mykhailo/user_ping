import json
import os
import shutil
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class IDatabase(ABC):
    """Interface для бази даних (Dependency Inversion Principle)"""
    
    @abstractmethod
    def load(self) -> Dict:
        pass
    
    @abstractmethod
    def save(self, data: Dict) -> None:
        pass


class JSONDatabase(IDatabase):
    """Конкретна реалізація для JSON файлів"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._cache = None
        self._last_save = 0
    
    def load(self) -> Dict:
        """Повертає дані з кешу або читає з диска"""
        if self._cache is not None:
            return self._cache

        if os.path.exists(self.filepath) and os.path.getsize(self.filepath) > 0:
            with open(self.filepath, "r", encoding="utf-8") as f:
                try:
                    self._cache = json.load(f)
                    return self._cache
                except json.JSONDecodeError:
                    self._cache = {}
                    return {}
        self._cache = {}
        return {}
    
    def save(self, data: Dict, force: bool = False) -> None:
        """Зберігає дані в кеш і періодично на диск"""
        self._cache = data
        
        # Якщо force=True або пройшло більше 10 секунд з останнього збереження
        import time
        current_time = time.time()
        
        if not force and (current_time - self._last_save) < 10:
            return

        self._last_save = current_time
        
        # Створюємо папку для бекапів
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # 1. Робимо щоденний бекап
        daily_path = os.path.join(backup_dir, f"daily_{os.path.basename(self.filepath)}")
        if self._should_backup(daily_path, days=1):
            self._create_backup(daily_path)

        # 3. Основне збереження
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _should_backup(self, backup_path: str, days: int) -> bool:
        """Перевіряє чи пора робити новий бекап"""
        if not os.path.exists(self.filepath):
            return False
            
        if not os.path.exists(backup_path):
            return True
            
        # Отримуємо час останньої зміни бекапу
        mtime = os.path.getmtime(backup_path)
        last_backup = datetime.fromtimestamp(mtime)
        
        # Якщо пройшло достатньо часу
        return datetime.now() - last_backup > timedelta(days=days)

    def _create_backup(self, backup_path: str) -> None:
        """Створює копію файлу"""
        try:
            if os.path.exists(self.filepath):
                shutil.copy2(self.filepath, backup_path)
        except Exception as e:
            print(f"Помилка при створенні бекапу {backup_path}: {e}")


class ChatRepository:
    """Repository для роботи з чатами (Single Responsibility)"""
    
    def __init__(self, db: IDatabase):
        self.db = db
    
    def get_chat_data(self, chat_id: str) -> Dict:
        """Отримує дані чату"""
        data = self.db.load()
        if chat_id not in data:
            data[chat_id] = {
                "users": {},
                "temp_unreg": [],
                "super_unreg": []
            }
            self.db.save(data)
        return data.get(chat_id)
    def get_all_chats(self) -> List[str]:
        """Повертає список ID всіх чатів у базі"""
        data = self.db.load()
        return [cid for cid in data.keys() if cid != "global_unreg"]
    
    def save_user(self, chat_id: str, user_id: str, name: str, update_unreg: bool = True, source: str = "message", profile_time: str = None) -> None:
        """
        Зберігає користувача. 
        source: 'message' (повідомлення в чаті) або 'profile' (статус в профілі)
        """
        user_id = str(user_id)
        data = self.db.load()
        
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        if "users" not in data[chat_id]:
            if isinstance(data[chat_id], dict) and "users" not in data[chat_id]:
                data[chat_id] = {"users": data[chat_id], "temp_unreg": [], "super_unreg": []}
        
        # Екранування HTML
        safe_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        now = datetime.now().isoformat()
        user_entry = data[chat_id]["users"].get(user_id, {})
        
        if not isinstance(user_entry, dict):
            user_entry = {"name": safe_name[:20], "last_seen": "2000-01-01T00:00:00"}

        # v1.8.5: Розподілена логіка запису
        if source == "message":
            # Перевірка дроселя (5 хв)
            last_seen_str = user_entry.get("last_seen", "2000-01-01T00:00:00")
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_str)
                if (datetime.now() - last_seen_dt).total_seconds() < 300:
                    # Оновлюємо ім'я якщо воно змінилось
                    if user_entry.get("name") != safe_name[:20]:
                        user_entry["name"] = safe_name[:20]
                        data[chat_id]["users"][user_id] = user_entry
                        self.db.save(data)
                    return
            except:
                pass

            user_entry["last_seen"] = now
            user_entry["name"] = safe_name[:20]
            
            # Знімаємо анрег тільки при ПОВІДОМЛЕННІ
            if update_unreg:
                if user_id in data[chat_id].get("temp_unreg", []):
                    data[chat_id]["temp_unreg"].remove(user_id)
                if "global_unreg" in data and user_id in data["global_unreg"].get("temp", []):
                    data["global_unreg"]["temp"].remove(user_id)
        else:
            # Source: profile (синхронізація або статус)
            p_time = profile_time or now
            # Оновлюємо profile_seen тільки якщо він новіший
            old_p_time = user_entry.get("profile_seen", "2000-01-01T00:00:00")
            if p_time > old_p_time:
                user_entry["profile_seen"] = p_time
            
            # Оновлюємо ім'я завжди при синхронізації
            user_entry["name"] = safe_name[:20]

        data[chat_id]["users"][user_id] = user_entry
        self.db.save(data)
    
    def remove_user(self, chat_id: str, user_id: str) -> None:
        """Видаляє користувача"""
        data = self.db.load()
        if chat_id in data and "users" in data[chat_id]:
            if user_id in data[chat_id]["users"]:
                del data[chat_id]["users"][user_id]
                self.db.save(data)
    
    async def get_active_users(self, chat_id: str) -> Dict[str, str]:
        """Повертає активних користувачів (без анрегів), відсортованих за активністю (повідомлення або статус)"""
        chat_data = self.get_chat_data(chat_id)
        
        all_users_raw = chat_data.get("users", {})
        temp_unreg = set(map(str, chat_data.get("temp_unreg", [])))
        super_unreg = set(map(str, chat_data.get("super_unreg", [])))
        
        # Перевіряємо глобальні анреги
        db_data = self.db.load()
        global_unreg = set(map(str, db_data.get("global_unreg", {}).get("temp", [])))
        global_super = set(map(str, db_data.get("global_unreg", {}).get("super", [])))
        
        # Фільтруємо анреги
        active_list = []
        for uid, val in all_users_raw.items():
            if uid in temp_unreg or uid in super_unreg or uid in global_unreg or uid in global_super:
                continue
            
            # Обробляємо і старий, і новий формат
            name = val["name"] if isinstance(val, dict) else val
            
            # Вибираємо найкращий таймстамп (v1.8.5)
            last_seen = val.get("last_seen", "2000-01-01T00:00:00") if isinstance(val, dict) else "2000-01-01T00:00:00"
            profile_seen = val.get("profile_seen", "2000-01-01T00:00:00") if isinstance(val, dict) else "2000-01-01T00:00:00"
            
            # Використовуємо максимум з двох
            actual_seen = max(last_seen, profile_seen)
            active_list.append((uid, name, actual_seen))
            
        # Сортуємо: свіжі таунспампи спочатку
        active_list.sort(key=lambda x: x[2], reverse=True)
        
        return {uid: name for uid, name, _ in active_list}

    def add_to_global_unreg(self, user_id: str, is_super: bool = False) -> None:
        """Додає користувача до глобального анрегу"""
        user_id = str(user_id)
        data = self.db.load()
        if "global_unreg" not in data:
            data["global_unreg"] = {"temp": [], "super": []}
            
        target = "super" if is_super else "temp"
        other = "temp" if is_super else "super"
        
        # Видаляємо з іншого списку, якщо він там є
        if user_id in data["global_unreg"][other]:
            data["global_unreg"][other].remove(user_id)
            
        if user_id not in data["global_unreg"][target]:
            data["global_unreg"][target].append(user_id)
            self.db.save(data)

    def remove_from_global_unreg(self, user_id: str) -> bool:
        """Видаляє користувача з усіх глобальних анрегів"""
        user_id = str(user_id)
        data = self.db.load()
        if "global_unreg" not in data:
            return False
            
        removed = False
        if user_id in data["global_unreg"].get("temp", []):
            data["global_unreg"]["temp"].remove(user_id)
            removed = True
        if user_id in data["global_unreg"].get("super", []):
            data["global_unreg"]["super"].remove(user_id)
            removed = True
            
        if removed:
            self.db.save(data)
        return removed

    def is_globally_unreg(self, user_id: str) -> Dict[str, bool]:
        """Перевіряє чи є користувач у глобальних списках"""
        data = self.db.load()
        glob = data.get("global_unreg", {})
        return {
            "temp": user_id in glob.get("temp", []),
            "super": user_id in glob.get("super", [])
        }
    
    def add_to_temp_unreg(self, chat_id: str, user_id: str) -> bool:
        """Додає до тимчасового анрегу"""
        user_id = str(user_id)
        data = self.db.load()
        
        # Ініціалізуємо чат, якщо не існує
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        if "temp_unreg" not in data[chat_id]:
            data[chat_id]["temp_unreg"] = []
        if "super_unreg" not in data[chat_id]:
            data[chat_id]["super_unreg"] = []
        
        if user_id in data[chat_id].get("super_unreg", []):
            data[chat_id]["super_unreg"].remove(user_id)
        
        if user_id not in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].append(user_id)
            self.db.save(data)
            return True
        return False
    
    def add_to_super_unreg(self, chat_id: str, user_id: str) -> bool:
        """Додає до постійного анрегу"""
        user_id = str(user_id)
        data = self.db.load()
        
        # Ініціалізуємо чат, якщо не існує
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        if "temp_unreg" not in data[chat_id]:
            data[chat_id]["temp_unreg"] = []
        if "super_unreg" not in data[chat_id]:
            data[chat_id]["super_unreg"] = []
        
        if user_id in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
        
        if user_id not in data[chat_id].get("super_unreg", []):
            data[chat_id]["super_unreg"].append(user_id)
            self.db.save(data)
            return True
        return False
    
    def remove_from_unreg(self, chat_id: str, user_id: str) -> bool:
        """Видаляє з обох списків анрегу"""
        user_id = str(user_id)
        data = self.db.load()
        
        # Ініціалізуємо чат, якщо не існує
        if chat_id not in data:
            return False  # Нічого видаляти
        if "temp_unreg" not in data[chat_id]:
            data[chat_id]["temp_unreg"] = []
        if "super_unreg" not in data[chat_id]:
            data[chat_id]["super_unreg"] = []
        
        removed = False
        if user_id in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
            removed = True
        if user_id in data[chat_id].get("super_unreg", []):
            data[chat_id]["super_unreg"].remove(user_id)
            removed = True
        
        if removed:
            self.db.save(data)
        return removed
    
    def get_stats(self, chat_id: str) -> Dict[str, int]:
        """Повертає статистику чату"""
        chat_data = self.get_chat_data(chat_id)
        
        # v2.3.0: Ensure chat_data is not None
        if not chat_data:
            return {
                "total": 0,
                "active": 0,
                "temp_unreg": 0,
                "super_unreg": 0
            }
        
        total = len(chat_data.get("users", {}))
        temp_unreg = len(chat_data.get("temp_unreg", []))
        super_unreg = len(chat_data.get("super_unreg", []))
        active = total - temp_unreg - super_unreg
        
        return {
            "total": total,
            "active": active,
            "temp_unreg": temp_unreg,
            "super_unreg": super_unreg
        }
    
    def add_call_template(self, chat_id: str, name: str, text: str) -> bool:
        """Додає шаблон виклику"""
        data = self.db.load()
        chat_data = self.get_chat_data(chat_id)
        
        if "call_templates" not in data[chat_id]:
            data[chat_id]["call_templates"] = {}
        
        data[chat_id]["call_templates"][name] = text
        self.db.save(data)
        return True
    
    def remove_call_template(self, chat_id: str, name: str) -> bool:
        """Видаляє шаблон виклику"""
        data = self.db.load()
        
        if chat_id in data and "call_templates" in data[chat_id]:
            if name in data[chat_id]["call_templates"]:
                del data[chat_id]["call_templates"][name]
                self.db.save(data)
                return True
        return False
    
    def get_call_templates(self, chat_id: str) -> Dict[str, str]:
        """Повертає всі шаблони викликів"""
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("call_templates", {})
    
    def set_stop_flag(self, chat_id: str, value: bool) -> None:
        """Встановлює прапорець зупинки виклику"""
        data = self.db.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        data[chat_id]["stop_call"] = value
        self.db.save(data)
    
    def get_stop_flag(self, chat_id: str) -> bool:
        """Перевіряє прапорець зупинки"""
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("stop_call", False)
    
    # === Call Triggers ===
    
    def create_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        """Створює новий тригер виклику"""
        data = self.db.load()
        
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        if "call_triggers" not in data[chat_id]:
            data[chat_id]["call_triggers"] = {}
        
        if trigger_name in data[chat_id]["call_triggers"]:
            return False  # Тригер вже існує
        
        data[chat_id]["call_triggers"][trigger_name] = []
        self.db.save(data)
        return True
    
    def delete_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        """Видаляє тригер виклику"""
        data = self.db.load()
        
        if chat_id in data and "call_triggers" in data[chat_id]:
            if trigger_name in data[chat_id]["call_triggers"]:
                del data[chat_id]["call_triggers"][trigger_name]
                self.db.save(data)
                return True
        return False
    
    def add_user_to_trigger(self, chat_id: str, trigger_name: str, user_id: str) -> bool:
        """Додає користувача до тригера"""
        data = self.db.load()
        
        if chat_id not in data or "call_triggers" not in data[chat_id]:
            return False
        
        if trigger_name not in data[chat_id]["call_triggers"]:
            return False
        
        if user_id not in data[chat_id]["call_triggers"][trigger_name]:
            data[chat_id]["call_triggers"][trigger_name].append(user_id)
            self.db.save(data)
        
        return True
    
    def remove_user_from_trigger(self, chat_id: str, trigger_name: str, user_id: str) -> bool:
        """Видаляє користувача з тригера"""
        data = self.db.load()
        
        if chat_id not in data or "call_triggers" not in data[chat_id]:
            return False
        
        if trigger_name not in data[chat_id]["call_triggers"]:
            return False
        
        if user_id in data[chat_id]["call_triggers"][trigger_name]:
            data[chat_id]["call_triggers"][trigger_name].remove(user_id)
            self.db.save(data)
            return True
        
        return False
    
    def get_call_triggers(self, chat_id: str) -> Dict[str, list]:
        """Повертає всі тригери чату"""
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("call_triggers", {})
    
    def get_trigger_users(self, chat_id: str, trigger_name: str) -> list:
        """Повертає список користувачів тригера"""
        triggers = self.get_call_triggers(chat_id)
        return triggers.get(trigger_name, [])
    
    def set_trigger_emoji(self, chat_id: str, trigger_name: str, emoji: str) -> bool:
        """Встановлює емодзі для тригера"""
        data = self.db.load()
        
        if chat_id not in data or "call_triggers" not in data[chat_id]:
            return False
        
        if trigger_name not in data[chat_id]["call_triggers"]:
            return False
        
        if "trigger_emojis" not in data[chat_id]:
            data[chat_id]["trigger_emojis"] = {}
        
        data[chat_id]["trigger_emojis"][trigger_name] = emoji
        self.db.save(data)
        return True
    
    def get_trigger_emoji(self, chat_id: str, trigger_name: str) -> str:
        """Повертає емодзі тригера"""
        chat_data = self.get_chat_data(chat_id)
        emojis = chat_data.get("trigger_emojis", {})
        return emojis.get(trigger_name, "🎯")
    
    def get_all_trigger_emojis(self, chat_id: str) -> dict:
        """Повертає всі емодзі тригерів"""
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("trigger_emojis", {})
    
    # === Settings ===
    
    def get_setting(self, chat_id: str, key: str, default: any = None) -> any:
        """Отримує налаштування чату"""
        chat_data = self.get_chat_data(chat_id)
        if not chat_data:
            return default
        settings = chat_data.get("settings", {})
        return settings.get(key, default)
    
    def set_setting(self, chat_id: str, key: str, value: any) -> None:
        """Зберігає налаштування чату"""
        data = self.db.load()
        
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
            
        if "settings" not in data[chat_id]:
            data[chat_id]["settings"] = {}
        
        data[chat_id]["settings"][key] = value
        self.db.save(data)
    
    # === Global Settings ===
    
    def get_global_setting(self, key: str, default: any = None) -> any:
        """Отримує глобальне налаштування (для Owner)"""
        data = self.db.load()
        settings = data.get("global_settings", {})
        return settings.get(key, default)
    
    def set_global_setting(self, key: str, value: any) -> None:
        """Встановлює глобальне налаштування"""
        data = self.db.load()
        
        if "global_settings" not in data:
            data["global_settings"] = {}
            
        data["global_settings"][key] = value
        self.db.save(data)
    
    # === Custom Ping Triggers ===
    
    def add_custom_ping_trigger(self, chat_id: str, trigger: str, start_type: str = "text") -> bool:
        """Додає кастомний тригер для пінгу"""
        data = self.db.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
            
        if "custom_ping_triggers" not in data[chat_id]:
            data[chat_id]["custom_ping_triggers"] = {}
            
        # trigger always stored in lower case
        trigger = trigger.lower()
        
        data[chat_id]["custom_ping_triggers"][trigger] = start_type
        self.db.save(data)
        return True

    def remove_custom_ping_trigger(self, chat_id: str, trigger: str) -> bool:
        """Видаляє кастомний тригер"""
        data = self.db.load()
        trigger = trigger.lower()
        
        if chat_id in data and "custom_ping_triggers" in data[chat_id]:
            if trigger in data[chat_id]["custom_ping_triggers"]:
                del data[chat_id]["custom_ping_triggers"][trigger]
                self.db.save(data)
                return True
        return False

    def get_custom_ping_triggers(self, chat_id: str) -> Dict[str, str]:
        """Повертає всі кастомні тригери чату {trigger: type}"""
        chat_data = self.get_chat_data(chat_id)
        return chat_data.get("custom_ping_triggers", {})
    
    # === Global Custom Triggers ===
    
    def add_global_ping_trigger(self, trigger: str, start_type: str = "text") -> None:
        """Додає глобальний тригер"""
        data = self.db.load()
        if "global_ping_triggers" not in data:
            data["global_ping_triggers"] = {}
            
        trigger = trigger.lower()
        data["global_ping_triggers"][trigger] = start_type
        self.db.save(data)

    def remove_global_ping_trigger(self, trigger: str) -> bool:
        """Видаляє глобальний тригер"""
        data = self.db.load()
        trigger = trigger.lower()
        
        if "global_ping_triggers" in data and trigger in data["global_ping_triggers"]:
            del data["global_ping_triggers"][trigger]
            self.db.save(data)
            return True
        return False

    def get_global_ping_triggers(self) -> Dict[str, str]:
        """Повертає глобальні тригери"""
        data = self.db.load()
        return data.get("global_ping_triggers", {})

    # === Bot Owners (v2.1.0) ===
    
    def add_bot_owner(self, user_id: int) -> None:
        """Додає додаткового власника бота (тільки SuperOwner)"""
        data = self.db.load()
        if "bot_owners" not in data:
            data["bot_owners"] = []
        uid = str(user_id)
        if uid not in data["bot_owners"]:
            data["bot_owners"].append(uid)
            self.db.save(data)

    def remove_bot_owner(self, user_id: int) -> bool:
        """Видаляє додаткового власника бота"""
        data = self.db.load()
        uid = str(user_id)
        if "bot_owners" in data and uid in data["bot_owners"]:
            data["bot_owners"].remove(uid)
            self.db.save(data)
            return True
        return False

    def is_owner(self, user_id: int) -> bool:
        """Перевіряє чи є користувач власником (Super або додатковим)"""
        from config import ADMIN_USER_ID
        if user_id == ADMIN_USER_ID:
            return True
        data = self.db.load()
        return str(user_id) in data.get("bot_owners", [])

    def get_bot_owners(self) -> List[str]:
        data = self.db.load()
        return data.get("bot_owners", [])

    # === Global Bot Admins (v1.9.8) ===
    
    def add_bot_admin(self, user_id: int) -> None:
        """Додає глобального адміна бота"""
        data = self.db.load()
        if "bot_admins" not in data:
            data["bot_admins"] = []
        
        uid = str(user_id)
        if uid not in data["bot_admins"]:
            data["bot_admins"].append(uid)
            self.db.save(data)

    def remove_bot_admin(self, user_id: int) -> bool:
        """Видаляє глобального адміна бота"""
        data = self.db.load()
        uid = str(user_id)
        if "bot_admins" in data and uid in data["bot_admins"]:
            data["bot_admins"].remove(uid)
            self.db.save(data)
            return True
        return False

    def is_bot_admin(self, user_id: int) -> bool:
        """Перевіряє чи є користувач адміном бота (або власником)"""
        if self.is_owner(user_id):
            return True
            
        data = self.db.load()
        return str(user_id) in data.get("bot_admins", [])

    def get_bot_admins(self) -> List[str]:
        """Повертає список ID всіх адмінів бота"""
        data = self.db.load()
        return data.get("bot_admins", [])

    # === Bot Moderators (v2.0.0) ===
    
    def add_bot_moderator(self, user_id: int) -> None:
        """Додає модератора бота"""
        data = self.db.load()
        if "bot_mods" not in data:
            data["bot_mods"] = []
        uid = str(user_id)
        if uid not in data["bot_mods"]:
            data["bot_mods"].append(uid)
            self.db.save(data)

    def remove_bot_moderator(self, user_id: int) -> bool:
        """Видаляє модератора бота"""
        data = self.db.load()
        uid = str(user_id)
        if "bot_mods" in data and uid in data["bot_mods"]:
            data["bot_mods"].remove(uid)
            self.db.save(data)
            return True
        return False

    def is_bot_moderator(self, user_id: int) -> bool:
        """Чи є користувач модератором (або вище)"""
        # Ієрархія: Owner > Admin > Mod
        if self.is_bot_admin(user_id):
            return True
        data = self.db.load()
        return str(user_id) in data.get("bot_mods", [])

    def get_bot_moderators(self) -> List[str]:
        data = self.db.load()
        return data.get("bot_mods", [])

    # === Ad Moderators (v2.0.0) ===
    
    def add_ad_moderator(self, user_id: int) -> None:
        """Додає модератора реклами"""
        data = self.db.load()
        if "ad_mods" not in data:
            data["ad_mods"] = []
        uid = str(user_id)
        if uid not in data["ad_mods"]:
            data["ad_mods"].append(uid)
            self.db.save(data)

    def remove_ad_moderator(self, user_id: int) -> bool:
        """Видаляє модератора реклами"""
        data = self.db.load()
        uid = str(user_id)
        if "ad_mods" in data and uid in data["ad_mods"]:
            data["ad_mods"].remove(uid)
            self.db.save(data)
            return True
        return False

    def is_ad_moderator(self, user_id: int) -> bool:
        """Чи є користувач модератором реклами (або вище)"""
        if self.is_bot_admin(user_id):
            return True
        data = self.db.load()
        return str(user_id) in data.get("ad_mods", [])

    def get_ad_moderators(self) -> List[str]:
        data = self.db.load()
        return data.get("ad_mods", [])



class PremiumRepository:
    """Repository для роботи з преміумом"""
    
    def __init__(self, db: IDatabase):
        self.db = db
    
    def has_premium(self, user_id: str) -> bool:
        """Перевіряє наявність активного преміуму"""
        data = self.db.load()
        
        if "premium_users" not in data:
            return False
        
        if user_id not in data["premium_users"]:
            return False
        
        expiry = datetime.fromisoformat(data["premium_users"][user_id])
        return datetime.now() < expiry
    
    def grant_premium(self, user_id: str, days: int) -> datetime:
        """Надає преміум на вказану кількість днів"""
        data = self.db.load()
        
        if "premium_users" not in data:
            data["premium_users"] = {}
        
        # Продовжуємо з поточної дати закінчення або з зараз
        if user_id in data["premium_users"]:
            current_expiry = datetime.fromisoformat(data["premium_users"][user_id])
            if current_expiry > datetime.now():
                new_expiry = current_expiry + timedelta(days=days)
            else:
                new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        
        data["premium_users"][user_id] = new_expiry.isoformat()
        self.db.save(data)
        
        return new_expiry
    
    def get_expiry(self, user_id: str) -> Optional[datetime]:
        """Повертає дату закінчення преміуму"""
        data = self.db.load()
        
        if "premium_users" not in data or user_id not in data["premium_users"]:
            return None
        
        return datetime.fromisoformat(data["premium_users"][user_id])
    
    def save_payment(self, user_id: str, charge_id: str, amount: int) -> None:
        """
        Зберігає інформацію про платіж для можливості рефанду
        
        Args:
            user_id: ID користувача
            charge_id: telegram_payment_charge_id
            amount: Сума в Stars
        """
        data = self.db.load()
        
        if "payments" not in data:
            data["payments"] = {}
        
        if user_id not in data["payments"]:
            data["payments"][user_id] = []
        
        payment_info = {
            "charge_id": charge_id,
            "amount": amount,
            "date": datetime.now().isoformat(),
            "refunded": False
        }
        
        data["payments"][user_id].append(payment_info)
        self.db.save(data)
    
    def get_user_payments(self, user_id: str) -> list:
        """Повертає всі платежі користувача"""
        data = self.db.load()
        
        if "payments" not in data or user_id not in data["payments"]:
            return []
        
        return data["payments"][user_id]
    
    def mark_payment_refunded(self, user_id: str, charge_id: str) -> bool:
        """
        Позначає платіж як повернений
        
        Returns:
            True якщо платіж знайдено та оновлено
        """
        data = self.db.load()
        
        if "payments" not in data or user_id not in data["payments"]:
            return False
        
        for payment in data["payments"][user_id]:
            if payment["charge_id"] == charge_id:
                payment["refunded"] = True
                self.db.save(data)
                return True
        
        return False
    
    def revoke_premium(self, user_id: str) -> bool:
        """
        Відбирає преміум у користувача
        
        Returns:
            True якщо преміум було відібрано
        """
        data = self.db.load()
        
        if "premium_users" not in data or user_id not in data["premium_users"]:
            return False
        
        del data["premium_users"][user_id]
        self.db.save(data)
        return True


class ChatPremiumRepository:
    """Repository для роботи з Chat Premium (v1.5.0)"""
    
    def __init__(self, db: IDatabase):
        self.db = db
    
    def has_chat_premium(self, chat_id: str) -> bool:
        """Перевіряє наявність активного Chat Premium"""
        data = self.db.load()
        
        if "chat_premium" not in data:
            return False
        
        if chat_id not in data["chat_premium"]:
            return False
        
        expiry = datetime.fromisoformat(data["chat_premium"][chat_id]["expiry"])
        return datetime.now() < expiry
    
    def purchase_chat_premium(self, chat_id: str, purchased_by: str, days: int) -> datetime:
        """Купує Chat Premium для чату"""
        data = self.db.load()
        
        if "chat_premium" not in data:
            data["chat_premium"] = {}
        
        # Продовжуємо з поточної дати або з зараз
        if chat_id in data["chat_premium"]:
            current_expiry = datetime.fromisoformat(data["chat_premium"][chat_id]["expiry"])
            if current_expiry > datetime.now():
                new_expiry = current_expiry + timedelta(days=days)
            else:
                new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        
        data["chat_premium"][chat_id] = {
            "expiry": new_expiry.isoformat(),
            "purchased_by": purchased_by,
            "purchase_date": datetime.now().isoformat()
        }
        
        self.db.save(data)
        return new_expiry
    
    def get_chat_premium_expiry(self, chat_id: str) -> Optional[datetime]:
        """Повертає дату закінчення Chat Premium"""
        data = self.db.load()
        
        if "chat_premium" not in data or chat_id not in data["chat_premium"]:
            return None
        
        return datetime.fromisoformat(data["chat_premium"][chat_id]["expiry"])
    
    def revoke_chat_premium(self, chat_id: str) -> bool:
        """Відбирає Chat Premium у чату"""
        data = self.db.load()
        
        if "chat_premium" not in data or chat_id not in data["chat_premium"]:
            return False
        
        del data["chat_premium"][chat_id]
        self.db.save(data)
        return True


class ReferralRepository:
    """Repository для роботи з реферальною системою (v1.5.0)"""
    
    def __init__(self, db: IDatabase):
        self.db = db
    
    def get_referral_code(self, user_id: str) -> str:
        """Повертає реферальний код користувача"""
        data = self.db.load()
        
        if "referrals" not in data:
            data["referrals"] = {}
        
        if user_id not in data["referrals"]:
            # Створюємо новий код
            code = f"ref_{user_id}"
            data["referrals"][user_id] = {
                "referral_code": code,
                "referred_users": [],
                "total_bonus_days": 0,
                "stats": {
                    "total_referrals": 0,
                    "premium_referrals": 0
                }
            }
            self.db.save(data)
        
        return data["referrals"][user_id]["referral_code"]
    
    def track_referral(self, referrer_id: str, referred_id: str) -> bool:
        """Відстежує реферала"""
        data = self.db.load()
        
        if "referrals" not in data or referrer_id not in data["referrals"]:
            return False
        
        # Перевіряємо чи вже є цей реферал
        if referred_id in data["referrals"][referrer_id]["referred_users"]:
            return False
        
        # Додаємо реферала
        data["referrals"][referrer_id]["referred_users"].append(referred_id)
        data["referrals"][referrer_id]["stats"]["total_referrals"] += 1
        
        self.db.save(data)
        return True
    
    def mark_premium_referral(self, referrer_id: str, referred_id: str) -> bool:
        """Позначає що реферал купив Premium"""
        data = self.db.load()
        
        if "referrals" not in data or referrer_id not in data["referrals"]:
            return False
        
        if referred_id not in data["referrals"][referrer_id]["referred_users"]:
            return False
        
        data["referrals"][referrer_id]["stats"]["premium_referrals"] += 1
        self.db.save(data)
        return True
    
    def add_bonus_days(self, user_id: str, days: int) -> int:
        """Додає бонусні дні користувачу"""
        data = self.db.load()
        
        if "referrals" not in data or user_id not in data["referrals"]:
            return 0
        
        data["referrals"][user_id]["total_bonus_days"] += days
        self.db.save(data)
        
        return data["referrals"][user_id]["total_bonus_days"]
    
    def get_referral_stats(self, user_id: str) -> dict:
        """Повертає статистику рефералів"""
        data = self.db.load()
        
        if "referrals" not in data or user_id not in data["referrals"]:
            return {
                "total_referrals": 0,
                "premium_referrals": 0,
                "total_bonus_days": 0,
                "referral_code": self.get_referral_code(user_id)
            }
        
        ref_data = data["referrals"][user_id]
        return {
            "total_referrals": ref_data["stats"]["total_referrals"],
            "premium_referrals": ref_data["stats"]["premium_referrals"],
            "total_bonus_days": ref_data["total_bonus_days"],
            "referral_code": ref_data["referral_code"]
        }
