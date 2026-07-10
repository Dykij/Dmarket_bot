"""Whitelist configuration."""
from typing import Any


class WhitelistChecker:
    """Checks items against a whitelist."""

    def __init__(self, whitelist: list[str] | None = None) -> None:
        self.whitelist = set(whitelist or [])

    def is_whitelisted(self, title: str) -> bool:
        """Check if an item is whitelisted."""
        if not self.whitelist:
            return True  # Empty whitelist = allow all
        return title in self.whitelist

    def filter_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter to only whitelisted items."""
        if not self.whitelist:
            return items
        return [it for it in items if self.is_whitelisted(it.get("title", ""))]
