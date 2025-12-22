"""
Unreg Domain
Manages all 4 unreg types: local temp/super, global temp/super
~260 lines, single responsibility
"""
from typing import Dict
from core.storage import JSONStorage


class UnregDomain:
    """
    Handles complete unreg system
    Single Responsibility: User opt-out from pings
    """
   

    def __init__(self, storage: JSONStorage):
        self.storage = storage
    
    # === Local Unreg (per-chat) ===
    
    def add_to_temp_unreg(self, chat_id: str, user_id: str) -> bool:
        """
        Adds user to temporary unreg (cleared on next message)
        
        Returns:
            True if added, False if already in temp_unreg
        """
        user_id = str(user_id)  # Type safety
        data = self.storage.load()
        
        # Initialize chat if doesn't exist
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        if "temp_unreg" not in data[chat_id]:
            data[chat_id]["temp_unreg"] = []
        if "super_unreg" not in data[chat_id]:
            data[chat_id]["super_unreg"] = []
        
        # Remove from super if exists (downgrade)
        if user_id in data[chat_id].get("super_unreg", []):
            data[chat_id]["super_unreg"].remove(user_id)
        
        if user_id not in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].append(user_id)
            self.storage.save(data)
            return True
        return False
    
    def add_to_super_unreg(self, chat_id: str, user_id: str) -> bool:
        """
        Adds user to permanent unreg (Premium feature)
        
        Returns:
            True if added, False if already in super_unreg
        """
        user_id = str(user_id)
        data = self.storage.load()
        
        # Initialize chat if doesn't exist
        if chat_id not in data:
            data[chat_id] = {"users": {}, "temp_unreg": [], "super_unreg": []}
        if "temp_unreg" not in data[chat_id]:
            data[chat_id]["temp_unreg"] = []
        if "super_unreg" not in data[chat_id]:
            data[chat_id]["super_unreg"] = []
        
        # Remove from temp (upgrade)
        if user_id in data[chat_id].get("temp_unreg", []):
            data[chat_id]["temp_unreg"].remove(user_id)
        
        if user_id not in data[chat_id].get("super_unreg", []):
            data[chat_id]["super_unreg"].append(user_id)
            self.storage.save(data)
            return True
        return False
    
    def remove_from_unreg(self, chat_id: str, user_id: str) -> bool:
        """
        Removes user from BOTH temp and super unreg
        
        Returns:
            True if removed from any list, False if wasn't in unreg
        """
        user_id = str(user_id)
        data = self.storage.load()
        
        # Initialize chat if doesn't exist
        if chat_id not in data:
            return False  # Nothing to remove
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
            self.storage.save(data)
        return removed
    
    def is_in_unreg(self, chat_id: str, user_id: str) -> Dict[str, bool]:
        """
        Checks user's unreg status in a specific chat
        
        Returns:
            {"temp": bool, "super": bool}
        """
        user_id = str(user_id)
        data = self.storage.load()
        
        chat_data = data.get(chat_id, {})
        return {
            "temp": user_id in chat_data.get("temp_unreg", []),
            "super": user_id in chat_data.get("super_unreg", [])
        }
    
    # === Global Unreg (all chats) ===
    
    def add_to_global_unreg(self, user_id: str, is_super: bool = False) -> None:
        """
        Adds user to global unreg (affects ALL chats)
        
        Args:
            user_id: User identifier
            is_super: If True, adds to global super (permanent), else temp
        """
        user_id = str(user_id)
        data = self.storage.load()
        
        if "global_unreg" not in data:
            data["global_unreg"] = {"temp": [], "super": []}
            
        target = "super" if is_super else "temp"
        other = "temp" if is_super else "super"
        
        # Remove from other list if exists
        if user_id in data["global_unreg"][other]:
            data["global_unreg"][other].remove(user_id)
            
        if user_id not in data["global_unreg"][target]:
            data["global_unreg"][target].append(user_id)
            self.storage.save(data)
    
    def remove_from_global_unreg(self, user_id: str) -> bool:
        """
        Removes user from ALL global unreg lists
        
        Returns:
            True if removed, False if wasn't in global unreg
        """
        user_id = str(user_id)
        data = self.storage.load()
        
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
            self.storage.save(data)
        return removed
    
    def is_globally_unreg(self, user_id: str) -> Dict[str, bool]:
        """
        Checks if user is in global unreg lists
        
        Returns:
            {"temp": bool, "super": bool}
        """
        user_id = str(user_id)
        data = self.storage.load()
        
        glob = data.get("global_unreg", {})
        return {
            "temp": user_id in glob.get("temp", []),
            "super": user_id in glob.get("super", [])
        }
    
    # === Helper for filtering ===
    
    def get_all_unreg_sets(self, chat_id: str) -> tuple:
        """
        Returns all 4 unreg sets as string sets for efficient filtering
        
        Returns:
            (temp_unreg, super_unreg, global_temp, global_super)
            All as set[str] for O(1) membership checking
        """
        data = self.storage.load()
        chat_data = data.get(chat_id, {})
        
        temp_unreg = set(map(str, chat_data.get("temp_unreg", [])))
        super_unreg = set(map(str, chat_data.get("super_unreg", [])))
        
        global_unreg = set(map(str, data.get("global_unreg", {}).get("temp", [])))
        global_super = set(map(str, data.get("global_unreg", {}).get("super", [])))
        
        return temp_unreg, super_unreg, global_unreg, global_super
    
    def clear_temp_unreg_for_user(self, user_id: str) -> int:
        """
        Clears temp unreg from global AND specific chat (called when user sends message)
        NOTE: This is called by ActivityMiddleware, not by user commands
        
        Returns:
            Number of lists cleared from
        """
        user_id = str(user_id)
        data = self.storage.load()
        cleared_count = 0
        
        # Clear from global temp
        if "global_unreg" in data and user_id in data["global_unreg"].get("temp", []):
            data["global_unreg"]["temp"].remove(user_id)
            cleared_count += 1
        
        # Note: We don't clear from chat-specific temp here because we don't know which chat
        # That's handled in save_user_activity when update_unreg=True
        
        if cleared_count > 0:
            self.storage.save(data)
        
        return cleared_count
