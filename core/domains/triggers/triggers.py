"""
Triggers Domains
Manages custom ping triggers and call groups
Combined into ~400 lines total
"""
from typing import Dict, List, Optional
from core.storage import JSONStorage


class CustomTriggersDomain:
    """
    Handles custom ping trigger words (e.g., !стоп → /all Стоп)
    Per-chat and global triggers
    """
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
    
    # === Chat Triggers ===
    
    def add_custom_ping_trigger(self, chat_id: str, trigger: str, trigger_type: str = "text") -> bool:
        """
        Adds custom ping trigger (Admin only)
        
        Args:
            trigger: Word that triggers ping (stored lowercase)
            trigger_type: 'text', 'emoji', 'active', 'active_week', 'writers', 'online'
        """
        data = self.storage.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
            
        if "custom_ping_triggers" not in data[chat_id]:
            data[chat_id]["custom_ping_triggers"] = {}
            
        # Trigger always stored lowercase
        trigger = trigger.lower()
        
        data[chat_id]["custom_ping_triggers"][trigger] = trigger_type
        self.storage.save(data)
        return True
    
    def remove_custom_ping_trigger(self, chat_id: str, trigger: str) -> bool:
        """Removes custom ping trigger"""
        data = self.storage.load()
        trigger = trigger.lower()
        
        if chat_id in data and "custom_ping_triggers" in data[chat_id]:
            if trigger in data[chat_id]["custom_ping_triggers"]:
                del data[chat_id]["custom_ping_triggers"][trigger]
                self.storage.save(data)
                return True
        return False
    
    def get_custom_ping_triggers(self, chat_id: str) -> Dict[str, str]:
        """Returns all custom triggers for chat"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("custom_ping_triggers", {})
        return {}
    
    # === Global Triggers (Owner only) ===
    
    def add_global_ping_trigger(self, trigger: str, trigger_type: str = "text") -> bool:
        """Adds global ping trigger (works in all chats)"""
        data = self.storage.load()
        
        if "global_ping_triggers" not in data:
            data["global_ping_triggers"] = {}
            
        trigger = trigger.lower()
        data["global_ping_triggers"][trigger] = trigger_type
        self.storage.save(data)
        return True
    
    def remove_global_ping_trigger(self, trigger: str) -> bool:
        """Removes global ping trigger"""
        data = self.storage.load()
        trigger = trigger.lower()
        
        if "global_ping_triggers" in data and trigger in data["global_ping_triggers"]:
            del data["global_ping_triggers"][trigger]
            self.storage.save(data)
            return True
        return False
    
    def get_global_ping_triggers(self) -> Dict[str, str]:
        """Returns all global triggers"""
        data = self.storage.load()
        return data.get("global_ping_triggers", {})


class CallGroupsDomain:
    """
    Handles call trigger groups (e.g., !croco → pings specific users)
    Users can self-register via roles panel
    """
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
    
    # === Group Management ===
    
    def create_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        """Creates empty call group"""
        data = self.storage.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
            
        if "call_triggers" not in data[chat_id]:
            data[chat_id]["call_triggers"] = {}
        
        if trigger_name in data[chat_id]["call_triggers"]:
            return False  # Trigger already exists
        
        data[chat_id]["call_triggers"][trigger_name] = []
        self.storage.save(data)
        return True
    
    def delete_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        """Deletes call group"""
        data = self.storage.load()
        
        if chat_id in data and "call_triggers" in data[chat_id]:
            if trigger_name in data[chat_id]["call_triggers"]:
                del data[chat_id]["call_triggers"][trigger_name]
                self.storage.save(data)
                return True
        return False
    
    def get_call_triggers(self, chat_id: str) -> Dict[str, List[str]]:
        """Returns all call groups in chat"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("call_triggers", {})
        return {}
    
    # === User Management ===
    
    def add_user_to_trigger(self, chat_id: str, trigger_name: str, user_id: str) -> bool:
        """Adds user to call group"""
        user_id = str(user_id)
        data = self.storage.load()
        
        if chat_id not in data or "call_triggers" not in data[chat_id]:
            return False
        
        if trigger_name not in data[chat_id]["call_triggers"]:
            return False
        
        if user_id not in data[chat_id]["call_triggers"][trigger_name]:
            data[chat_id]["call_triggers"][trigger_name].append(user_id)
            self.storage.save(data)
        
        return True
    
    def remove_user_from_trigger(self, chat_id: str, trigger_name: str, user_id: str) -> bool:
        """Removes user from call group"""
        user_id = str(user_id)
        data = self.storage.load()
        
        if chat_id in data and "call_triggers" in data[chat_id]:
            if trigger_name in data[chat_id]["call_triggers"]:
                if user_id in data[chat_id]["call_triggers"][trigger_name]:
                    data[chat_id]["call_triggers"][trigger_name].remove(user_id)
                    self.storage.save(data)
                    return True
        
        return False
    
    def get_trigger_users(self, chat_id: str, trigger_name: str) -> List[str]:
        """Returns list of users in call group"""
        triggers = self.get_call_triggers(chat_id)
        return triggers.get(trigger_name, [])
    
    # === Emoji Mapping ===
    
    def set_trigger_emoji(self, chat_id: str, trigger_name: str, emoji: str) -> bool:
        """Sets emoji for call group (display in roles panel)"""
        data = self.storage.load()
        
        if chat_id not in data or "call_triggers" not in data[chat_id]:
            return False
        
        if trigger_name not in data[chat_id]["call_triggers"]:
            return False
        
        if "trigger_emojis" not in data[chat_id]:
            data[chat_id]["trigger_emojis"] = {}
        
        data[chat_id]["trigger_emojis"][trigger_name] = emoji
        self.storage.save(data)
        return True
    
    def get_trigger_emoji(self, chat_id: str, trigger_name: str) -> Optional[str]:
        """Returns emoji for call group, if set"""
        data = self.storage.load()
        if chat_id in data and "trigger_emojis" in data[chat_id]:
            return data[chat_id]["trigger_emojis"].get(trigger_name)
        return None
    
    def get_all_trigger_emojis(self, chat_id: str) -> Dict[str, str]:
        """Returns all trigger emoji mappings"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("trigger_emojis", {})
        return {}
