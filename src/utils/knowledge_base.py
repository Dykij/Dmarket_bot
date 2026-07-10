"""Knowledge base."""
from enum import Enum
from typing import Any


class KnowledgeType(Enum):
    TRADING_PATTERN = "trading_pattern"
    LESSON = "lesson"
    MARKET_INSIGHT = "market_insight"


_knowledge_base_cache: dict[int, Any] = {}


class KnowledgeBase:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self._entries: list[dict[str, Any]] = []

    async def add_knowledge(
        self, knowledge_type: KnowledgeType, title: str, content: dict
    ) -> str:
        entry_id = f"kb_{len(self._entries)}"
        self._entries.append({
            "id": entry_id,
            "type": knowledge_type.value,
            "title": title,
            "content": content,
        })
        return entry_id

    async def query_relevant(self, context: dict) -> list:
        return []

    async def get_summary(self) -> dict:
        by_type: dict[str, int] = {}
        for e in self._entries:
            t = e.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {"total_entries": len(self._entries), "by_type": by_type}


def get_knowledge_base(user_id: int = 0) -> KnowledgeBase:
    if user_id not in _knowledge_base_cache:
        _knowledge_base_cache[user_id] = KnowledgeBase(user_id)
    return _knowledge_base_cache[user_id]


def clear_knowledge_base_cache() -> None:
    _knowledge_base_cache.clear()
