"""
Settings Domains
Chat-specific and global configuration
~220 lines total
"""
from typing import Dict, Any
from core.storage import JSONStorage


class ChatSettingsDomain:
    """
    Per-chat bot settings (pin, speed, cleanup, etc.)
    Single Responsibility: Chat configuration
    """
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
    
    def get_setting(self, chat_id: str, key: str, default: Any = None) -> Any:
        """Gets chat setting"""
        data = self.storage.load()
        if chat_id in data:
            settings = data[chat_id].get("settings", {})
            return settings.get(key, default)
        return default
    
    def set_setting(self, chat_id: str, key: str, value: Any) -> None:
        """Sets chat setting"""
        data = self.storage.load()
        
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
            
        if "settings" not in data[chat_id]:
            data[chat_id]["settings"] = {}
        
        data[chat_id]["settings"][key] = value
        self.storage.save(data)
    
    def get_all_settings(self, chat_id: str) -> Dict[str, Any]:
        """Returns all settings for chat"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("settings", {})
        return {}
    
    # === Stop Flag (for /stop command) ===
    
    def set_stop_flag(self, chat_id: str, value: bool) -> None:
        """Sets stop flag (cancels ongoing ping)"""
        data = self.storage.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        data[chat_id]["stop_call"] = value
        self.storage.save(data)
    
    def get_stop_flag(self, chat_id: str) -> bool:
        """Checks if stop flag is set"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("stop_call", False)
        return False
    
    # === Templates ===
    
    def add_call_template(self, chat_id: str, name: str, text: str) -> bool:
        """Adds call template"""
        data = self.storage.load()
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        
        if "call_templates" not in data[chat_id]:
            data[chat_id]["call_templates"] = {}
        
        data[chat_id]["call_templates"][name] = text
        self.storage.save(data)
        return True
    
    def remove_call_template(self, chat_id: str, name: str) -> bool:
        """Removes call template"""
        data = self.storage.load()
        
        if chat_id in data and "call_templates" in data[chat_id]:
            if name in data[chat_id]["call_templates"]:
                del data[chat_id]["call_templates"][name]
                self.storage.save(data)
                return True
        return False
    
    def get_call_templates(self, chat_id: str) -> Dict[str, str]:
        """Returns all call templates"""
        data = self.storage.load()
        if chat_id in data:
            return data[chat_id].get("call_templates", {})
        return {}


class GlobalConfigDomain:
    """
    Bot-wide global settings (userbot toggle, etc.)
    Single Responsibility: Global configuration
    """
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
    
    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Gets global setting (Owner access)"""
        data = self.storage.load()
        settings = data.get("global_settings", {})
        return settings.get(key, default)
    
    def set_global_setting(self, key: str, value: Any) -> None:
        """Sets global setting"""
        data = self.storage.load()
        
        if "global_settings" not in data:
            data["global_settings"] = {}
            
        data["global_settings"][key] = value
        self.storage.save(data)
    
    def get_all_global_settings(self) -> Dict[str, Any]:
        """Returns all global settings"""
        data = self.storage.load()
        return data.get("global_settings", {})
