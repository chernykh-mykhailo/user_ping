"""
User Activity Domain
Manages user activity tracking, timestamps, and filtered lists
~200 lines, focused responsibility
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
from core.storage import JSONStorage


class UserActivityDomain:
    """
    Handles user activity tracking and retrieval
    Single Responsibility: User presence and activity timestamps
    """

    def __init__(self, storage: JSONStorage):
        self.storage = storage

    def save_user_activity(
        self,
        chat_id: str,
        user_id: str,
        name: str,
        source: str = "message",
        profile_time: str = None,
        username: str = None,
    ) -> None:
        """
        Saves user activity (DOES NOT handle unreg - that's UnregDomain's job)

        Args:
            chat_id: Chat identifier
            user_id: User identifier (auto-converted to string)
            name: User display name
            source: 'message' (wrote in chat) or 'profile' (from sync/status)
            profile_time: ISO timestamp for profile status (optional)
        """
        user_id = str(user_id)  # Type safety
        data = self.storage.load()

        # Initialize chat if doesn't exist
        if chat_id not in data:
            data[chat_id] = {
                "users": {},
                "temp_unreg": [],
                "super_unreg": [],
                "super_puper_unreg": [],
            }

        if "users" not in data[chat_id]:
            data[chat_id] = {
                "users": data[chat_id],
                "temp_unreg": [],
                "super_unreg": [],
                "super_puper_unreg": [],
            }

        # HTML escaping
        safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        now = datetime.now().isoformat()
        user_entry = data[chat_id]["users"].get(user_id, {})

        if not isinstance(user_entry, dict):
            user_entry = {"name": safe_name[:20], "last_seen": "2000-01-01T00:00:00"}

        # Update username if provided
        if username:
            user_entry["username"] = username

        # Logic split by source type
        if source == "message":
            # Throttle: only update if >5 min since last activity
            last_seen_str = user_entry.get("last_seen", "2000-01-01T00:00:00")
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_str)
                if (datetime.now() - last_seen_dt).total_seconds() < 300:
                    # Only update name if changed
                    if user_entry.get("name") != safe_name[:20]:
                        user_entry["name"] = safe_name[:20]
                        data[chat_id]["users"][user_id] = user_entry
                        self.storage.save(data)
                    return
            except:
                pass

            user_entry["last_seen"] = now
            user_entry["name"] = safe_name[:20]

        else:  # source: profile (sync or status)
            p_time = profile_time or now
            # Only update if timestamp is newer
            old_p_time = user_entry.get("profile_seen", "2000-01-01T00:00:00")
            if p_time > old_p_time:
                user_entry["profile_seen"] = p_time

            # Always update name on sync
            user_entry["name"] = safe_name[:20]

        data[chat_id]["users"][user_id] = user_entry
        self.storage.save(data)

    def remove_user(self, chat_id: str, user_id: str) -> None:
        """Removes user from chat (e.g., left or kicked)"""
        import logging
        _log = logging.getLogger(__name__)

        user_id = str(user_id)
        data = self.storage.load()

        _log.info(f"🔍 remove_user: storage_id={id(self.storage)}, cache_id={id(data)}, user={user_id}")

        if chat_id in data and "users" in data[chat_id]:
            if user_id in data[chat_id]["users"]:
                del data[chat_id]["users"][user_id]
                self.storage.save(data)
                # Перевірка після збереження
                after = self.storage.load()
                still_there = user_id in after.get(chat_id, {}).get("users", {})
                _log.info(f"🔍 after remove: cache_id={id(after)}, still_in_cache={still_there}, users={list(after.get(chat_id, {}).get('users', {}).keys())}")
            else:
                _log.info(f"🔍 remove_user: user {user_id} NOT FOUND in users dict")
        else:
            _log.info(f"🔍 remove_user: chat {chat_id} not in data or no 'users' key")

    def get_all_user_ids(self, chat_id: str) -> List[str]:
        """Returns all user IDs for a given chat (v2.6.5)"""
        chat_data = self._get_chat_data(chat_id)
        return list(chat_data.get("users", {}).keys())

    def get_all_users_with_names(self, chat_id: str) -> Dict[str, str]:
        """Повертає ВСІХ користувачів з іменами (без фільтрації)"""
        chat_data = self._get_chat_data(chat_id)
        users = chat_data.get("users", {})
        
        result = {}
        for uid, udata in users.items():
            if isinstance(udata, dict):
                result[uid] = udata.get("name", f"User {uid}")
            else:
                result[uid] = f"User {uid}"
        return result

    def get_user_setting(self, user_id: str, key: str, default: Any = None) -> Any:
        """Gets user-specific setting (global)"""
        data = self.storage.load()
        user_settings = data.get("user_settings", {}).get(str(user_id), {})
        return user_settings.get(key, default)

    def set_user_setting(self, user_id: str, key: str, value: Any) -> None:
        """Sets user-specific setting (global)"""
        data = self.storage.load()
        if "user_settings" not in data:
            data["user_settings"] = {}

        uid = str(user_id)
        if uid not in data["user_settings"]:
            data["user_settings"][uid] = {}

        data["user_settings"][uid][key] = value
        self.storage.save(data)

    def get_active_users(self, chat_id: str) -> Dict[str, str]:
        """
        Returns active users (excluding unregged), sorted by activity
        NOTE: Unreg filtering is done here, but management is in UnregDomain

        Returns:
            Dict[user_id, name] sorted by most recent activity
        """
        from core.domains.users.unreg import UnregDomain
        import logging

        logger = logging.getLogger(__name__)

        chat_data = self._get_chat_data(chat_id)
        all_users_raw = chat_data.get("users", {})

        # Get unreg sets (delegating to UnregDomain would be circular, so we read directly)
        temp_unreg, super_unreg, global_unreg, global_super, super_puper, local_reg = (
            self._get_unreg_sets(chat_id)
        )

        # Filter unregs
        active_list = []
        filtered_count = 0
        now_dt = datetime.now()
        ghost_threshold = now_dt - timedelta(days=30)

        for uid, val in all_users_raw.items():
            # v2.10.18: Logic for being filtered out
            is_local_unreg = (
                uid in temp_unreg or uid in super_unreg or uid in super_puper
            )
            is_global_unreg = uid in global_unreg or uid in global_super

            # User is unregged if they have local unreg OR (global unreg AND NO local reg override)
            if is_local_unreg or (is_global_unreg and uid not in local_reg):
                filtered_count += 1
                continue

            # Handle both old and new format
            name = val["name"] if isinstance(val, dict) else val

            # Choose best timestamp (v1.8.5)
            last_seen_str = (
                val.get("last_seen", "2000-01-01T00:00:00")
                if isinstance(val, dict)
                else "2000-01-01T00:00:00"
            )
            profile_seen_str = (
                val.get("profile_seen", "2000-01-01T00:00:00")
                if isinstance(val, dict)
                else "2000-01-01T00:00:00"
            )

            # v2.6.6: Ghost Protection
            # If name is ID:xxx and user wasn't seen for 7 days - we assume they are gone or useless for pings
            try:
                actual_seen_str = max(last_seen_str, profile_seen_str)
                actual_seen_dt = datetime.fromisoformat(
                    actual_seen_str.replace("+00:00", "").replace("Z", "")
                )

                if name.startswith("ID:") and actual_seen_dt < ghost_threshold:
                    logger.debug(
                        f"[GHOST] Skipping ghost user {uid} (last seen {actual_seen_str})"
                    )
                    continue
            except:
                pass

            active_list.append(
                (
                    uid,
                    name,
                    last_seen_str if isinstance(val, dict) else "2000-01-01T00:00:00",
                )
            )  # Sort by last_seen (message activity) primarily

        logger.info(
            f"[UNREG DEBUG] filtered_count={filtered_count}, active_count={len(active_list)}"
        )

        # Sort: freshest timestamps first
        active_list.sort(key=lambda x: x[2], reverse=True)

        return {uid: name for uid, name, _ in active_list}

    def get_active_users_full(self, chat_id: str) -> List[Dict]:
        """
        Returns active users with full data (name, username, etc)
        """
        from core.domains.users.unreg import UnregDomain
        import logging

        logger = logging.getLogger(__name__)

        chat_data = self._get_chat_data(chat_id)
        all_users_raw = chat_data.get("users", {})

        temp_unreg, super_unreg, global_unreg, global_super, super_puper, local_reg = (
            self._get_unreg_sets(chat_id)
        )

        # Filter unregs
        active_list = []
        now_dt = datetime.now()
        ghost_threshold = now_dt - timedelta(days=30)

        for uid, val in all_users_raw.items():
            is_local_unreg = (
                uid in temp_unreg or uid in super_unreg or uid in super_puper
            )
            is_global_unreg = uid in global_unreg or uid in global_super

            if is_local_unreg or (is_global_unreg and uid not in local_reg):
                continue

            # Handle both old and new format
            user_data = (
                val
                if isinstance(val, dict)
                else {"name": val, "last_seen": "2000-01-01T00:00:00"}
            )
            name = user_data.get("name", "Unknown")

            # Choose best timestamp
            last_seen_str = user_data.get("last_seen", "2000-01-01T00:00:00")
            profile_seen_str = user_data.get("profile_seen", "2000-01-01T00:00:00")

            # Ghost Protection
            try:
                actual_seen_str = max(last_seen_str, profile_seen_str)
                actual_seen_dt = datetime.fromisoformat(
                    actual_seen_str.replace("+00:00", "").replace("Z", "")
                )

                if name.startswith("ID:") and actual_seen_dt < ghost_threshold:
                    continue
            except:
                pass

            # Prepare result object
            result_item = user_data.copy()
            result_item["id"] = uid
            active_list.append((uid, result_item, actual_seen_str))

        # Sort: freshest timestamps first
        active_list.sort(key=lambda x: x[2], reverse=True)

        return [item for _, item, _ in active_list]

    def get_filtered_users(
        self, chat_id: str, source: str = "both", hours: int = 24
    ) -> Dict[str, str]:
        """
        Returns users filtered by activity type and time window

        Args:
            chat_id: Chat identifier
            source: 'message' (wrote), 'profile' (online), or 'both'
            hours: Time window

        Returns:
            Dict[user_id, name] matching criteria
        """
        chat_data = self._get_chat_data(chat_id)
        all_users = chat_data.get("users", {})

        temp_unreg, super_unreg, global_unreg, global_super, super_puper, local_reg = (
            self._get_unreg_sets(chat_id)
        )

        threshold = datetime.now() - timedelta(hours=hours)
        result = {}

        for uid, val in all_users.items():
            is_local_unreg = (
                uid in temp_unreg or uid in super_unreg or uid in super_puper
            )
            is_global_unreg = uid in global_unreg or uid in global_super

            if is_local_unreg or (is_global_unreg and uid not in local_reg):
                continue

            if not isinstance(val, dict):
                continue

            ls_str = val.get("last_seen", "2000-01-01T00:00:00")
            ps_str = val.get("profile_seen", "2000-01-01T00:00:00")

            # v2.3.0: Handle mixed timezone-aware and naive datetimes
            try:
                ls = datetime.fromisoformat(
                    ls_str.replace("+00:00", "").replace("Z", "")
                )
                ps = datetime.fromisoformat(
                    ps_str.replace("+00:00", "").replace("Z", "")
                )
            except:
                continue  # Skip invalid dates

            match_found = False
            if source == "message" and ls > threshold:
                match_found = True
            elif source == "profile" and ps > threshold:
                match_found = True
            elif source == "both" and max(ls, ps) > threshold:
                match_found = True

            if match_found:
                result[uid] = val["name"]

        return result

    def get_all_chats(self) -> List[str]:
        """Returns list of all chat IDs in database"""
        data = self.storage.load()
        return [cid for cid in data.keys() if cid.startswith("-")]

    def _get_chat_data(self, chat_id: str) -> Dict:
        """Internal: Get chat data, creating if necessary"""
        data = self.storage.load()
        if chat_id not in data:
            data[chat_id] = {
                "users": {},
                "temp_unreg": [],
                "super_unreg": [],
                "super_puper_unreg": [],
            }
            self.storage.save(data)
        return data.get(chat_id)

    def _get_unreg_sets(self, chat_id: str) -> tuple:
        """
        Internal: Returns all 6 unreg sets as string sets
        (temp_unreg, super_unreg, global_temp, global_super, super_puper, local_reg)
        """
        data = self.storage.load()
        chat_data = data.get(chat_id, {})

        temp_unreg = set(map(str, chat_data.get("temp_unreg", [])))
        super_unreg = set(map(str, chat_data.get("super_unreg", [])))
        super_puper = set(map(str, chat_data.get("super_puper_unreg", [])))
        local_reg = set(map(str, chat_data.get("local_reg", [])))

        global_unreg = set(map(str, data.get("global_unreg", {}).get("temp", [])))
        global_super = set(map(str, data.get("global_unreg", {}).get("super", [])))

        return (
            temp_unreg,
            super_unreg,
            global_unreg,
            global_super,
            super_puper,
            local_reg,
        )
