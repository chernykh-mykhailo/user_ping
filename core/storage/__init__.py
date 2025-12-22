"""Storage layer for data persistence"""
from .json_storage import IStorage, JSONStorage

__all__ = ["IStorage", "JSONStorage"]
