"""Blacklist filters."""
from typing import Any


class ItemBlacklistFilter:
    """Filters items based on a blacklist."""

    def __init__(self, blacklist: list[str] | None = None) -> None:
        self.blacklist = set(blacklist or [])

    def is_blocked(self, title: str) -> bool:
        """Check if an item is blacklisted."""
        lower = title.lower()
        return any(b in lower for b in self.blacklist)

    def filter_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out blacklisted items."""
        return [it for it in items if not self.is_blocked(it.get("title", ""))]
