"""
Core module exports (v2.3.0 - Domain Architecture)
"""
# New: Domain-based architecture
from .chat_repository import ChatRepository

# Old: Legacy database classes (for compatibility)
from .database import JSONDatabase, PremiumRepository, ChatPremiumRepository, ReferralRepository

__all__ = [
    "ChatRepository",
    "JSONDatabase",
    "PremiumRepository",
    "ChatPremiumRepository",
    "ReferralRepository"
]
