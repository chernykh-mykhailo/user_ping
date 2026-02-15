import json
import os
from typing import Any, Dict
from contextvars import ContextVar

# Context variable to store current locale for the request
current_locale: ContextVar[str] = ContextVar("current_locale", default="uk")


class L10n:
    _instance = None
    _strings: Dict[str, Dict[str, Any]] = {}  # { 'uk': {...}, 'en': {...} }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(L10n, cls).__new__(cls)
            cls._instance._load_strings()
        return cls._instance

    def _load_strings(self):
        self._strings = {}
        # Base path relative to this file: utils / .. -> root
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        locales_dir = os.path.join(base_path, "locales")

        # Scan subdirectories (uk, en, etc.)
        if os.path.exists(locales_dir):
            for item in os.listdir(locales_dir):
                item_path = os.path.join(locales_dir, item)
                if os.path.isdir(item_path):
                    lang = item
                    if lang not in self._strings:
                        self._strings[lang] = {}

                    # Load all .json files in this dir
                    for filename in os.listdir(item_path):
                        if filename.endswith(".json"):
                            filepath = os.path.join(item_path, filename)
                            namespace = filename[:-5]
                            # Treat common.json as global/root
                            if namespace == "common":
                                namespace = None
                            self._load_file(lang, filepath, namespace)

    def _load_file(self, lang: str, filepath: str, namespace: str = None):
        if lang not in self._strings:
            self._strings[lang] = {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = json.load(f)

                if namespace:
                    if namespace not in self._strings[lang]:
                        self._strings[lang][namespace] = {}
                    if isinstance(content, dict):
                        self._strings[lang][namespace].update(content)
                else:
                    self._strings[lang].update(content)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    def set_locale(self, lang: str):
        current_locale.set(lang)

    def get_locale(self) -> str:
        return current_locale.get()

    @property
    def locales(self) -> list[str]:
        return list(self._strings.keys())

    def format_value(self, key: str, **kwargs) -> str:
        lang = self.get_locale()
        val = self._get_raw_value(lang, key)

        if val is None and lang != "uk":
            val = self._get_raw_value("uk", key)

        if val is not None:
            return str(val).format(**kwargs)

        return key

    def _get_raw_value(self, lang: str, key: str) -> Any:
        if lang not in self._strings:
            return None

        val = self._strings[lang]
        if isinstance(val, dict) and key in val:
            return val[key]

        parts = key.split(".")
        if len(parts) > 1:
            namespace = parts[0]
            if isinstance(val, dict) and namespace in val:
                ns_dict = val[namespace]
                remainder = ".".join(parts[1:])
                if isinstance(ns_dict, dict) and remainder in ns_dict:
                    return ns_dict[remainder]

        current = val
        for k in parts:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current if not isinstance(current, dict) else None


l10n = L10n()
