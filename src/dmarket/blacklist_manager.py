"""Blacklist Module for filtering problematic sellers and items.

This module handles:
- Seller blacklisting (manual and automatic)
- Keyword filtering for item names
- Automatic blacklisting based on failed transactions
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BlacklistManager:
    """Manager for seller and item blacklists."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        blacklist_file: str = "data/blacklist.json",
    ):
        """Initialize blacklist manager.

        Args:
            config: Configuration dictionary
            blacklist_file: Path to blacklist JSON file
        """
        self.config = config or {}
        self.blacklist_file = Path(blacklist_file)

        # Blacklisted seller IDs
        self.blacklisted_sellers: set[str] = set()

        # Forbidden keywords in item names
        self.forbidden_keywords: list[str] = []

        # Blacklisted items (from expanded format)
        self.blacklisted_items: list[str] = []

        # Blocked profile settings
        self.blocked_profiles: dict[str, Any] = {}

        # Suspicious tags
        self.suspicious_tags: list[str] = []

        # Price filters
        self.price_filters: dict[str, Any] = {}

        # Failure tracking for auto-blacklist
        self._failure_counter: dict[str, int] = {}
        self._failure_threshold = self.config.get("auto_blacklist_threshold", 3)

        # Last failure timestamps for cleanup
        self._failure_timestamps: dict[str, datetime] = {}
        self._failure_expiry_hours = self.config.get("failure_expiry_hours", 24)

        # Load configuration
        self._load_config()

        # Load saved blacklist
        self._load_blacklist()

        logger.info(
            f"BlacklistManager initialized: "
            f"{len(self.blacklisted_sellers)} sellers, "
            f"{len(self.forbidden_keywords)} keywords, "
            f"{len(self.blacklisted_items)} items"
        )

    def _load_config(self) -> None:
        """Load blacklist settings from config."""
        security_config = self.config.get("security", {})

        # Load seller blacklist from config
        config_sellers = security_config.get("blacklisted_sellers", [])
        self.blacklisted_sellers.update(config_sellers)

        # Load forbidden keywords from config
        self.forbidden_keywords = security_config.get(
            "forbidden_keywords",
            [
                "Souvenir",  # Souvenir skins have low liquidity
                "Well-Worn",  # Hardest wear to sell quickly
                "Inscribed Gem",  # Cheap Dota 2 gems
                "StatTrak™ Music Kit",  # Very niche items
            ],
        )

    def _load_blacklist(self) -> None:
        """Load blacklist from JSON file."""
        if not self.blacklist_file.exists():
            return

        try:
            with open(self.blacklist_file, encoding="utf-8") as f:
                data = json.load(f)

            # Load sellers
            file_sellers = data.get("blacklisted_sellers", [])
            self.blacklisted_sellers.update(file_sellers)

            # Load keywords (merge with config)
            file_keywords = data.get("forbidden_keywords", [])
            for kw in file_keywords:
                if kw not in self.forbidden_keywords:
                    self.forbidden_keywords.append(kw)

            # Load blacklisted items (expanded format)
            self.blacklisted_items = data.get("blacklisted_items", [])

            # Load blocked profile settings
            self.blocked_profiles = data.get(
                "blocked_profiles",
                {
                    "min_trust_score": 40,
                    "block_private_inventories": True,
                    "block_new_accounts": True,
                    "min_account_age_days": 7,
                },
            )

            # Load suspicious tags
            self.suspicious_tags = data.get("suspicious_tags", [])

            # Load price filters
            self.price_filters = data.get(
                "price_filters",
                {
                    "max_discount_percent": 60,
                    "min_daily_volume": 5,
                    "max_price_deviation_percent": 25,
                },
            )

            logger.info(f"Loaded blacklist from {self.blacklist_file}")

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load blacklist file: {e}")

    def _save_blacklist(self) -> None:
        """Save blacklist to JSON file."""
        try:
            # Ensure directory exists
            self.blacklist_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "blacklisted_sellers": list(self.blacklisted_sellers),
                "forbidden_keywords": self.forbidden_keywords,
                "last_updated": datetime.now(UTC).isoformat(),
            }

            with open(self.blacklist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved blacklist to {self.blacklist_file}")

        except OSError:
            logger.exception("Failed to save blacklist")

    def is_seller_blacklisted(self, seller_id: str) -> bool:
        """Check if a seller is blacklisted.

        Args:
            seller_id: Seller's unique ID

        Returns:
            True if seller is blacklisted
        """
        return seller_id in self.blacklisted_sellers

    def is_item_forbidden(self, item_title: str) -> bool:
        """Check if an item contains forbidden keywords.

        Args:
            item_title: Item's display name

        Returns:
            True if item should be skipped
        """
        title_lower = item_title.lower()
        return any(
            keyword.lower() in title_lower for keyword in self.forbidden_keywords
        )

    def should_skip_item(
        self,
        item: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if an item should be skipped based on blacklist.

        Args:
            item: Item data from API

        Returns:
            Tuple of (should_skip, reason)
        """
        # Check seller
        seller_id = item.get("owner", item.get("sellerId", item.get("userId")))
        if seller_id and self.is_seller_blacklisted(seller_id):
            return True, f"Seller {seller_id[:8]}... is blacklisted"

        # Check item name
        title = item.get("title", "")
        if self.is_item_forbidden(title):
            return True, "Item contains forbidden keyword"

        return False, ""

    def add_seller_to_blacklist(
        self,
        seller_id: str,
        reason: str = "Manual addition",
    ) -> None:
        """Add a seller to the blacklist.

        Args:
            seller_id: Seller's unique ID
            reason: Reason for blacklisting
        """
        if seller_id not in self.blacklisted_sellers:
            self.blacklisted_sellers.add(seller_id)
            self._save_blacklist()
            logger.warning(f"🚫 Seller {seller_id[:16]}... blacklisted: {reason}")

    def remove_seller_from_blacklist(self, seller_id: str) -> bool:
        """Remove a seller from the blacklist.

        Args:
            seller_id: Seller's unique ID

        Returns:
            True if seller was in blacklist and removed
        """
        if seller_id in self.blacklisted_sellers:
            self.blacklisted_sellers.discard(seller_id)
            self._save_blacklist()
            logger.info(f"✅ Seller {seller_id[:16]}... removed from blacklist")
            return True
        return False

    def add_forbidden_keyword(self, keyword: str) -> None:
        """Add a forbidden keyword.

        Args:
            keyword: Keyword to block
        """
        if keyword not in self.forbidden_keywords:
            self.forbidden_keywords.append(keyword)
            self._save_blacklist()
            logger.info(f"🚫 Keyword '{keyword}' added to blacklist")

    def remove_forbidden_keyword(self, keyword: str) -> bool:
        """Remove a forbidden keyword.

        Args:
            keyword: Keyword to unblock

        Returns:
            True if keyword was in list and removed
        """
        if keyword in self.forbidden_keywords:
            self.forbidden_keywords.remove(keyword)
            self._save_blacklist()
            logger.info(f"✅ Keyword '{keyword}' removed from blacklist")
            return True
        return False

    def record_failure(
        self,
        seller_id: str,
        error_code: int | str = 0,
    ) -> bool:
        """Record a transaction failure for a seller.

        If failures exceed threshold, seller is auto-blacklisted.

        Args:
            seller_id: Seller's unique ID
            error_code: Error code from API (400, 409, etc.)

        Returns:
            True if seller was auto-blacklisted
        """
        now = datetime.now(UTC)

        # Clean up old failures
        self._cleanup_old_failures()

        # Increment failure counter
        self._failure_counter[seller_id] = self._failure_counter.get(seller_id, 0) + 1
        self._failure_timestamps[seller_id] = now

        failure_count = self._failure_counter[seller_id]
        logger.debug(
            f"Transaction failure #{failure_count} for seller {seller_id[:16]}... "
            f"(error: {error_code})"
        )

        # Check if threshold exceeded
        if failure_count >= self._failure_threshold:
            self.add_seller_to_blacklist(
                seller_id,
                reason=f"Auto-blacklisted after {failure_count} failed transactions",
            )
            # Reset counter after blacklisting
            del self._failure_counter[seller_id]
            del self._failure_timestamps[seller_id]
            return True

        return False

    def _cleanup_old_failures(self) -> None:
        """Remove expired failure records."""
        now = datetime.now(UTC)
        expiry_delta = timedelta(hours=self._failure_expiry_hours)

        expired_sellers = [
            seller_id
            for seller_id, timestamp in self._failure_timestamps.items()
            if now - timestamp > expiry_delta
        ]

        for seller_id in expired_sellers:
            del self._failure_counter[seller_id]
            del self._failure_timestamps[seller_id]

    def get_blacklist_summary(self) -> dict[str, Any]:
        """Get summary of blacklist contents.

        Returns:
            Summary dictionary
        """
        return {
            "blacklisted_sellers_count": len(self.blacklisted_sellers),
            "forbidden_keywords_count": len(self.forbidden_keywords),
            "pending_failures": len(self._failure_counter),
            "auto_blacklist_threshold": self._failure_threshold,
            "keywords": self.forbidden_keywords[:10],  # First 10
        }

    def reset_failure_counter(self, seller_id: str) -> None:
        """Reset failure counter for a seller (e.g., after successful transaction).

        Args:
            seller_id: Seller's unique ID
        """
        if seller_id in self._failure_counter:
            del self._failure_counter[seller_id]
        if seller_id in self._failure_timestamps:
            del self._failure_timestamps[seller_id]
