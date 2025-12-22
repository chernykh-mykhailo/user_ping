"""
JSON Storage Layer (extracted from database.py)
Handles low-level file operations and caching
"""
import json
import os
import shutil
from abc import ABC, abstractmethod
from typing import Dict
from datetime import datetime, timedelta


class IStorage(ABC):
    """Interface for storage implementations"""
    
    @abstractmethod
    def load(self) -> Dict:
        pass
    
    @abstractmethod
    def save(self, data: Dict, force: bool = False) -> None:
        pass


class JSONStorage(IStorage):
    """
    JSON file storage with caching and automatic backups
    Extracted from JSONDatabase to separate storage concerns
    """
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._cache = None
        self._last_save = 0
    
    def load(self) -> Dict:
        """Returns data from cache or reads from disk"""
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
        """Saves data to cache and periodically to disk"""
        self._cache = data
        
        # If force=True or more than 10 seconds passed since last save
        import time
        current_time = time.time()
        
        if not force and (current_time - self._last_save) < 10:
            return

        self._last_save = current_time
        
        # Create backup directory
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # 1. Daily backup
        daily_path = os.path.join(backup_dir, f"daily_{os.path.basename(self.filepath)}")
        if self._should_backup(daily_path, days=1):
            self._create_backup(daily_path)

        # 2. Main save
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _should_backup(self, backup_path: str, days: int) -> bool:
        """Checks if it's time to make a new backup"""
        if not os.path.exists(self.filepath):
            return False
            
        if not os.path.exists(backup_path):
            return True
            
        # Get last modification time of backup
        mtime = os.path.getmtime(backup_path)
        last_backup = datetime.fromtimestamp(mtime)
        
        # If enough time has passed
        return datetime.now() - last_backup > timedelta(days=days)

    def _create_backup(self, backup_path: str) -> None:
        """Creates a file copy"""
        try:
            if os.path.exists(self.filepath):
                shutil.copy2(self.filepath, backup_path)
        except Exception as e:
            print(f"Error creating backup {backup_path}: {e}")
