"""
ChatRepository Facade (v2.3.0 Migration Layer)
Delegates to new domains while maintaining old API for backward compatibility
Will be removed in v2.4.0 after all handlers are updated
"""

from typing import Dict, List, Optional, Any
from config import ADMIN_USER_ID

# Note: We use JSONDatabase directly from db parameter, not JSONStorage
from core.domains import (
    UserActivityDomain,
    UnregDomain,
    StaffRolesDomain,
    CustomTriggersDomain,
    CallGroupsDomain,
    ChatSettingsDomain,
    GlobalConfigDomain,
    EmojiPackDomain,
)


class ChatRepository:
    """
    ��TEMPORARY FACADE (v2.3.0)
    Maintains old API, delegates to new domain objects

    Migration path:
    v2.2 → v2.3: Use this facade (handlers unchanged)
    v2.3 → v2.4: Update handlers to use domains directly
    v2.4+: Remove this class entirely
    """

    def __init__(self, db):
        """
        Initializes all domain instances

        Args:
            db: JSONDatabase instance - we use it DIRECTLY to avoid cache issues
        """
        # CRITICAL: Use the SAME db instance, not a new JSONStorage!
        # Creating new storage causes cache desync between old and new code
        self.storage = db  # db is JSONDatabase, compatible with our domains
        self.db = db

        # Initialize all domains with the same storage
        self.activity = UserActivityDomain(self.storage)
        self.unreg = UnregDomain(self.storage)
        self.staff = StaffRolesDomain(self.storage, ADMIN_USER_ID)
        self.triggers_custom = CustomTriggersDomain(self.storage)
        self.triggers_groups = CallGroupsDomain(self.storage)
        self.chat_settings = ChatSettingsDomain(self.storage)
        self.global_config = GlobalConfigDomain(self.storage)
        self.emoji_packs = EmojiPackDomain(self.storage)

    # === User Activity (delegates to ActivityDomain) ===

    def save_user(
        self,
        chat_id: str,
        user_id: str,
        name: str,
        update_unreg: bool = True,
        source: str = "message",
        profile_time: str = None,
        username: str = None,
    ) -> None:
        """Saves user activity"""
        self.activity.save_user_activity(
            chat_id, user_id, name, source, profile_time, username
        )

        # v2.7.0: Handle unreg clearing with registration_disabled check
        # If registration_disabled is True, we DO NOT clear temp_unreg automatically
        reg_disabled = self.chat_settings.get_setting(
            chat_id, "registration_disabled", False
        )

        if update_unreg and source == "message" and not reg_disabled:
            # Super_unreg is PERMANENT - only cleared by explicit /reg command
            self.unreg.remove_from_temp_unreg(chat_id, user_id)
            # Also clear from global temp (NOT global super!)
            data = self.storage.load()
            user_id = str(user_id)
            if "global_unreg" in data and user_id in data.get("global_unreg", {}).get(
                "temp", []
            ):
                data["global_unreg"]["temp"].remove(user_id)
                self.storage.save(data)

    def remove_user(self, chat_id: str, user_id: str) -> None:
        """Повне видалення юзера з усіх списків чату (v2.10.26)"""
        self.activity.remove_user(chat_id, user_id)
        # Чистимо всі анреги юзера в цьому чаті
        self.unreg.remove_from_unreg(chat_id, user_id)
        self.unreg.remove_from_temp_unreg(chat_id, user_id)

    def get_active_users(self, chat_id: str) -> Dict[str, str]:
        """Returns active users (excluding unregged)"""
        return self.activity.get_active_users(chat_id)

    def get_active_users_full(self, chat_id: str) -> List[Dict]:
        """Returns active users with full details (v2.9.0)"""
        return self.activity.get_active_users_full(chat_id)

    def get_all_user_ids(self, chat_id: str) -> List[str]:
        """Returns all user IDs in chat (v2.6.5)"""
        return self.activity.get_all_user_ids(chat_id)

    def get_all_users_with_names(self, chat_id: str) -> Dict[str, str]:
        """Повертає ВСІХ користувачів з іменами (включаючи тих, хто в анрегу)"""
        return self.activity.get_all_users_with_names(chat_id)

    def get_all_chats(self) -> List[str]:
        """Returns all chat IDs"""
        return self.activity.get_all_chats()

    def get_chat_data(self, chat_id: str) -> Dict:
        """Gets chat data (DEPRECATED - use domains directly)"""
        return self.activity._get_chat_data(chat_id)

    def get_stats(self, chat_id: str) -> Dict[str, int]:
        """Returns chat statistics"""
        import logging
        _log = logging.getLogger(__name__)

        chat_data = self.activity._get_chat_data(chat_id)

        total = len(chat_data.get("users", {}))
        temp_unreg = len(chat_data.get("temp_unreg", []))
        super_unreg = len(chat_data.get("super_unreg", []))
        super_puper = len(chat_data.get("super_puper_unreg", []))
        active = total - temp_unreg - super_unreg - super_puper

        _log.info(f"📊 get_stats [{chat_id}]: total={total}, users={list(chat_data.get('users', {}).keys())}")

        return {
            "total": total,
            "active": active,
            "temp_unreg": temp_unreg,
            "super_unreg": super_unreg,
            "super_puper": super_puper,
        }

    # === User Settings (delegates to ActivityDomain) ===

    def get_user_setting(self, user_id: str, key: str, default: Any = None) -> Any:
        return self.activity.get_user_setting(user_id, key, default)

    def set_user_setting(self, user_id: str, key: str, value: Any) -> None:
        self.activity.set_user_setting(user_id, key, value)

    # === Unreg (delegates to UnregDomain) ===

    def add_to_temp_unreg(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.add_to_temp_unreg(chat_id, user_id)

    def add_to_super_unreg(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.add_to_super_unreg(chat_id, user_id)

    def add_to_super_puper_unreg(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.add_to_super_puper_unreg(chat_id, user_id)

    def remove_from_temp_unreg(self, chat_id: str, user_id: str) -> bool:
        """Removes from temp_unreg only (for middleware - doesn't touch super_unreg)"""
        return self.unreg.remove_from_temp_unreg(chat_id, user_id)

    def remove_from_unreg(self, chat_id: str, user_id: str) -> bool:
        """Removes from BOTH temp and super (for /reg command)"""
        return self.unreg.remove_from_unreg(chat_id, user_id)

    def add_to_global_unreg(self, user_id: str, is_super: bool = False) -> None:
        self.unreg.add_to_global_unreg(user_id, is_super)

    def remove_from_global_unreg(self, user_id: str) -> bool:
        return self.unreg.remove_from_global_unreg(user_id)

    def is_globally_unreg(self, user_id: str) -> Dict[str, bool]:
        return self.unreg.is_globally_unreg(user_id)

    def get_command_limit(self, chat_id: str, command: str) -> bool:
        return self.unreg.get_command_limit(chat_id, command)

    def set_command_limit(self, chat_id: str, command: str, disabled: bool) -> None:
        self.unreg.set_command_limit(chat_id, command, disabled)

    def clear_all_unreg_in_chat(self, chat_id: str, exclude_super: bool = False) -> int:
        return self.unreg.clear_all_unreg_in_chat(chat_id, exclude_super)

    def clear_chat_unreg(self, chat_id: str) -> int:
        return self.unreg.clear_chat_unreg(chat_id)

    def add_to_unreg_whitelist(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.add_to_unreg_whitelist(chat_id, user_id)

    def remove_from_unreg_whitelist(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.remove_from_unreg_whitelist(chat_id, user_id)

    def is_user_unreg_whitelisted(self, chat_id: str, user_id: str) -> bool:
        return self.unreg.is_user_unreg_whitelisted(chat_id, user_id)

    # === Staff (delegates to StaffRolesDomain) ===

    def is_owner(self, user_id: int) -> bool:
        return self.staff.is_owner(user_id)

    def is_bot_admin(self, user_id: int) -> bool:
        return self.staff.is_bot_admin(user_id)

    def is_bot_moderator(self, user_id: int) -> bool:
        return self.staff.is_bot_moderator(user_id)

    def is_ad_moderator(self, user_id: int) -> bool:
        return self.staff.is_ad_moderator(user_id)

    def add_bot_owner(self, user_id: int) -> None:
        self.staff.add_bot_owner(user_id)

    def remove_bot_owner(self, user_id: int) -> bool:
        return self.staff.remove_bot_owner(user_id)

    def get_bot_owners(self) -> List[str]:
        return self.staff.get_bot_owners()

    def add_bot_admin(self, user_id: int) -> None:
        self.staff.add_bot_admin(user_id)

    def remove_bot_admin(self, user_id: int) -> bool:
        return self.staff.remove_bot_admin(user_id)

    def get_bot_admins(self) -> List[str]:
        return self.staff.get_bot_admins()

    def add_bot_moderator(self, user_id: int) -> None:
        self.staff.add_bot_moderator(user_id)

    def remove_bot_moderator(self, user_id: int) -> bool:
        return self.staff.remove_bot_moderator(user_id)

    def get_bot_moderators(self) -> List[str]:
        return self.staff.get_bot_moderators()

    def add_ad_moderator(self, user_id: int) -> None:
        self.staff.add_ad_moderator(user_id)

    def remove_ad_moderator(self, user_id: int) -> bool:
        return self.staff.remove_ad_moderator(user_id)

    def get_ad_moderators(self) -> List[str]:
        return self.staff.get_ad_moderators()

    # === Custom Triggers (delegates to CustomTriggersDomain) ===

    def add_custom_ping_trigger(
        self, chat_id: str, trigger: str, trigger_type: str = "text"
    ) -> bool:
        return self.triggers_custom.add_custom_ping_trigger(
            chat_id, trigger, trigger_type
        )

    def remove_custom_ping_trigger(self, chat_id: str, trigger: str) -> bool:
        return self.triggers_custom.remove_custom_ping_trigger(chat_id, trigger)

    def get_custom_ping_triggers(self, chat_id: str) -> Dict[str, str]:
        return self.triggers_custom.get_custom_ping_triggers(chat_id)

    def add_global_ping_trigger(self, trigger: str, trigger_type: str = "text") -> bool:
        return self.triggers_custom.add_global_ping_trigger(trigger, trigger_type)

    def remove_global_ping_trigger(self, trigger: str) -> bool:
        return self.triggers_custom.remove_global_ping_trigger(trigger)

    def get_global_ping_triggers(self) -> Dict[str, str]:
        return self.triggers_custom.get_global_ping_triggers()

    # === Call Groups (delegates to CallGroupsDomain) ===

    def create_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        return self.triggers_groups.create_call_trigger(chat_id, trigger_name)

    def delete_call_trigger(self, chat_id: str, trigger_name: str) -> bool:
        return self.triggers_groups.delete_call_trigger(chat_id, trigger_name)

    def get_call_triggers(self, chat_id: str) -> Dict[str, List[str]]:
        return self.triggers_groups.get_call_triggers(chat_id)

    def add_user_to_trigger(
        self, chat_id: str, trigger_name: str, user_id: str
    ) -> bool:
        return self.triggers_groups.add_user_to_trigger(chat_id, trigger_name, user_id)

    def remove_user_from_trigger(
        self, chat_id: str, trigger_name: str, user_id: str
    ) -> bool:
        return self.triggers_groups.remove_user_from_trigger(
            chat_id, trigger_name, user_id
        )

    def get_trigger_users(self, chat_id: str, trigger_name: str) -> List[str]:
        return self.triggers_groups.get_trigger_users(chat_id, trigger_name)

    def set_trigger_emoji(self, chat_id: str, trigger_name: str, emoji: str) -> bool:
        return self.triggers_groups.set_trigger_emoji(chat_id, trigger_name, emoji)

    def get_trigger_emoji(self, chat_id: str, trigger_name: str) -> Optional[str]:
        return self.triggers_groups.get_trigger_emoji(chat_id, trigger_name)

    def get_all_trigger_emojis(self, chat_id: str) -> Dict[str, str]:
        return self.triggers_groups.get_all_trigger_emojis(chat_id)

    # === Settings (delegates to ChatSettingsDomain) ===

    def get_setting(self, chat_id: str, key: str, default: Any = None) -> Any:
        return self.chat_settings.get_setting(chat_id, key, default)

    def set_setting(self, chat_id: str, key: str, value: Any) -> None:
        self.chat_settings.set_setting(chat_id, key, value)

    def set_stop_flag(self, chat_id: str, value: bool) -> None:
        self.chat_settings.set_stop_flag(chat_id, value)

    def get_stop_flag(self, chat_id: str) -> bool:
        return self.chat_settings.get_stop_flag(chat_id)

    def add_call_template(self, chat_id: str, name: str, text: str) -> bool:
        return self.chat_settings.add_call_template(chat_id, name, text)

    def remove_call_template(self, chat_id: str, name: str) -> bool:
        return self.chat_settings.remove_call_template(chat_id, name)

    def get_call_templates(self, chat_id: str) -> Dict[str, str]:
        return self.chat_settings.get_call_templates(chat_id)

    # === Global Settings (delegates to GlobalConfigDomain) ===

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        return self.global_config.get_global_setting(key, default)

    def set_global_setting(self, key: str, value: Any) -> None:
        self.global_config.set_global_setting(key, value)
