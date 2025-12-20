"""
Database layer - Repository Pattern (SOLID: SRP, DIP)
Абстракція для роботи з даними
"""
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import secrets


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
    
    def load(self) -> Dict:
        if os.path.exists(self.filepath) and os.path.getsize(self.filepath) > 0:
            with open(self.filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}
    
    def save(self, data: Dict) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


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
        return data[chat_id]
    
    def save_user(self, chat_id: str, user_id: str, name: str) -> None:
        """Зберігає користувача"""
        data = self.db.load()
        
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        if "users" not in data[chat_id]:
            data[chat_id] = {"users": data[chat_id], "temp_unreg": [], "super_unreg": []}
        
        # Екранування HTML
        safe_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        data[chat_id]["users"][user_id] = safe_name[:20]
        
        # Знімаємо тимчасовий анрег якщо користувач написав
        if user_id in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
        
        self.db.save(data)
    
    def remove_user(self, chat_id: str, user_id: str) -> None:
        """Видаляє користувача"""
        data = self.db.load()
        if chat_id in data and "users" in data[chat_id]:
            if user_id in data[chat_id]["users"]:
                del data[chat_id]["users"][user_id]
                self.db.save(data)
    
    def get_active_users(self, chat_id: str) -> Dict[str, str]:
        """Повертає активних користувачів (без анрегів)"""
        chat_data = self.get_chat_data(chat_id)
        
        all_users = chat_data.get("users", {})
        temp_unreg = set(chat_data.get("temp_unreg", []))
        super_unreg = set(chat_data.get("super_unreg", []))
        
        return {
            uid: name for uid, name in all_users.items()
            if uid not in temp_unreg and uid not in super_unreg
        }
    
    def add_to_temp_unreg(self, chat_id: str, user_id: str) -> bool:
        """Додає до тимчасового анрегу"""
        data = self.db.load()
        chat_data = self.get_chat_data(chat_id)
        
        if user_id in chat_data.get("super_unreg", []):
            data[chat_id]["super_unreg"].remove(user_id)
        
        if user_id not in chat_data.get("temp_unreg", []):
            data[chat_id]["temp_unreg"].append(user_id)
            self.db.save(data)
            return True
        return False
    
    def add_to_super_unreg(self, chat_id: str, user_id: str) -> bool:
        """Додає до постійного анрегу"""
        data = self.db.load()
        chat_data = self.get_chat_data(chat_id)
        
        if user_id in chat_data.get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
        
        if user_id not in chat_data.get("super_unreg", []):
            data[chat_id]["super_unreg"].append(user_id)
            self.db.save(data)
            return True
        return False
    
    def remove_from_unreg(self, chat_id: str, user_id: str) -> bool:
        """Видаляє з обох списків анрегу"""
        data = self.db.load()
        chat_data = self.get_chat_data(chat_id)
        
        removed = False
        if user_id in chat_data.get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
            removed = True
        if user_id in chat_data.get("super_unreg", []):
            data[chat_id]["super_unreg"].remove(user_id)
            removed = True
        
        if removed:
            self.db.save(data)
        return removed
    
    def get_stats(self, chat_id: str) -> Dict[str, int]:
        """Повертає статистику чату"""
        chat_data = self.get_chat_data(chat_id)
        
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
