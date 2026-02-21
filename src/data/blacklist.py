"""Blacklist Module for filtering problematic sellers and items.

This module handles:
- Seller blacklisting (manual and automatic)
- Keyword filtering for item names
- Automatic blacklisting based on failed transactions
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Tuple

logger = logging.getLogger(__name__)


class BlacklistManager:
    """Manager for seller and item blacklists."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        blacklist_file: str = "data/blacklist.json",
    ):
        self.config = config or {}
        self.blacklist_file = Path(blacklist_file)
        self.blacklisted_sellers: set[str] = set()
        self.forbidden_keywords: list[str] = []

        # Load logic
        self._load_config()
        self._load_blacklist()

    def _load_config(self) -> None:
        """Load blacklist settings from config."""
        self.forbidden_keywords = [
            "Souvenir",
            "Well-Worn",
            "Inscribed Gem",
            "StatTrak™ Music Kit",
        ]

    def _load_blacklist(self) -> None:
        """Load blacklist from JSON file."""
        if not self.blacklist_file.exists():
            return

        try:
            with open(self.blacklist_file, encoding="utf-8") as f:
                data = json.load(f)

            # Load keywords (merge)
            file_keywords = data.get("forbidden_keywords", [])
            for kw in file_keywords:
                if kw not in self.forbidden_keywords:
                    self.forbidden_keywords.append(kw)

        except Exception as e:
            logger.warning(f"Failed to load blacklist file: {e}")

    def is_item_forbidden(self, item_title: str) -> bool:
        """Check if an item contains forbidden keywords."""
        title_lower = item_title.lower()
        return any(
            keyword.lower() in title_lower for keyword in self.forbidden_keywords
        )

    def should_skip_item(self, item: dict[str, Any]) -> Tuple[bool, str]:
        """Check if an item should be skipped based on blacklist."""
        title = item.get("title", "")
        if self.is_item_forbidden(title):
            return True, "Item contains forbidden keyword"
        return False, ""
