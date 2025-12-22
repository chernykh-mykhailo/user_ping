"""
Staff Roles Domain
Manages bot role hierarchy: SuperOwner → Owners → Admins → Moderators → Ad Moderators
~320 lines, single responsibility
"""
from typing import List, Dict
from core.storage import JSONStorage


class StaffRolesDomain:
    """
    Handles staffrole hierarchy and permission checks
    Single Responsibility: Access control and role management
    """
    
    def __init__(self, storage: JSONStorage, super_owner_id: int):
        self.storage = storage
        self.SUPER_OWNER = super_owner_id
    
    # === Hierarchy Checks ===
    
    def is_super_owner(self, user_id: int) -> bool:
        """Checks if user is the SuperOwner (highest privilege)"""
        return int(user_id) == self.SUPER_OWNER
    
    def is_owner(self, user_id: int) -> bool:
        """Checks if user is Owner (Super OR additional owners)"""
        if self.is_super_owner(user_id):
            return True
            
        data = self.storage.load()
        return str(user_id) in data.get("bot_owners", [])
    
    def is_bot_admin(self, user_id: int) -> bool:
        """Checks if user is Bot Admin (Owner+ OR admin)"""
        if self.is_owner(user_id):
            return True
            
        data = self.storage.load()
        return str(user_id) in data.get("bot_admins", [])
    
    def is_bot_moderator(self, user_id: int) -> bool:
        """Checks if user is Moderator (Admin+ OR moderator)"""
        if self.is_bot_admin(user_id):
            return True
            
        data = self.storage.load()
        return str(user_id) in data.get("bot_mods", [])
    
    def is_ad_moderator(self, user_id: int) -> bool:
        """Checks if user is Ad Moderator (Admin+ OR ad moderator)"""
        if self.is_bot_admin(user_id):
            return True
            
        data = self.storage.load()
        return str(user_id) in data.get("ad_mods", [])
    
    # === Owner Management (SuperOwner only) ===
    
    def add_bot_owner(self, user_id: int) -> None:
        """Adds a bot owner (SuperOwner only)"""
        data = self.storage.load()
        if "bot_owners" not in data:
            data["bot_owners"] = []
        
        uid = str(user_id)
        if uid not in data["bot_owners"]:
            data["bot_owners"].append(uid)
            self.storage.save(data)
    
    def remove_bot_owner(self, user_id: int) -> bool:
        """Removes a bot owner (SuperOwner only)"""
        data = self.storage.load()
        uid = str(user_id)
        
        if "bot_owners" in data and uid in data["bot_owners"]:
            data["bot_owners"].remove(uid)
            self.storage.save(data)
            return True
        return False
    
    def get_bot_owners(self) -> List[str]:
        """Returns list of all bot owner IDs (excluding SuperOwner)"""
        data = self.storage.load()
        return data.get("bot_owners", [])
    
    # === Admin Management (Owner+) ===
    
    def add_bot_admin(self, user_id: int) -> None:
        """Adds a bot admin (Owner+ can do this)"""
        data = self.storage.load()
        if "bot_admins" not in data:
            data["bot_admins"] = []
        
        uid = str(user_id)
        if uid not in data["bot_admins"]:
            data["bot_admins"].append(uid)
            self.storage.save(data)
    
    def remove_bot_admin(self, user_id: int) -> bool:
        """Removes a bot admin (Owner+ can do this)"""
        data = self.storage.load()
        uid = str(user_id)
        
        if "bot_admins" in data and uid in data["bot_admins"]:
            data["bot_admins"].remove(uid)
            self.storage.save(data)
            return True
        return False
    
    def get_bot_admins(self) -> List[str]:
        """Returns list of all bot admin IDs"""
        data = self.storage.load()
        return data.get("bot_admins", [])
    
    # === Moderator Management (Admin+) ===
    
    def add_bot_moderator(self, user_id: int) -> None:
        """Adds a bot moderator (Admin+ can do this)"""
        data = self.storage.load()
        if "bot_mods" not in data:
            data["bot_mods"] = []
        
        uid = str(user_id)
        if uid not in data["bot_mods"]:
            data["bot_mods"].append(uid)
            self.storage.save(data)
    
    def remove_bot_moderator(self, user_id: int) -> bool:
        """Removes a bot moderator (Admin+ can do this)"""
        data = self.storage.load()
        uid = str(user_id)
        
        if "bot_mods" in data and uid in data["bot_mods"]:
            data["bot_mods"].remove(uid)
            self.storage.save(data)
            return True
        return False
    
    def get_bot_moderators(self) -> List[str]:
        """Returns list of all bot moderator IDs"""
        data = self.storage.load()
        return data.get("bot_mods", [])
    
    # === Ad Moderator Management (Admin+) ===
    
    def add_ad_moderator(self, user_id: int) -> None:
        """Adds an ad moderator (Admin+ can do this)"""
        data = self.storage.load()
        if "ad_mods" not in data:
            data["ad_mods"] = []
        
        uid = str(user_id)
        if uid not in data["ad_mods"]:
            data["ad_mods"].append(uid)
            self.storage.save(data)
    
    def remove_ad_moderator(self, user_id: int) -> bool:
        """Removes an ad moderator (Admin+ can do this)"""
        data = self.storage.load()
        uid = str(user_id)
        
        if "ad_mods" in data and uid in data["ad_mods"]:
            data["ad_mods"].remove(uid)
            self.storage.save(data)
            return True
        return False
    
    def get_ad_moderators(self) -> List[str]:
        """Returns list of all ad moderator IDs"""
        data = self.storage.load()
        return data.get("ad_mods", [])
    
    # === Aggregator ===
    
    def get_all_staff(self) -> Dict[str, List[str]]:
        """
        Returns all staff organized by role
        
        Returns:
            {
                "superowner": [str(SUPER_OWNER)],
                "owners": [...],
                "admins": [...],
                "moderators": [...],
                "ad_moderators": [...]
            }
        """
        data = self.storage.load()
        
        return {
            "superowner": [str(self.SUPER_OWNER)],
            "owners": data.get("bot_owners", []),
            "admins": data.get("bot_admins", []),
            "moderators": data.get("bot_mods", []),
            "ad_moderators": data.get("ad_mods", [])
        }
