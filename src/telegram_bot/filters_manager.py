"""
Filter manager for notification filters.

This module provides a centralized way to manage notification filters
for different users.
"""

from typing import Any

# Simple in-memory storage for filters (in production, use database)
_filters_storage: dict[int, dict[str, Any]] = {}


class FiltersManager:
    """Manages notification filters for users."""

    def __init__(self) -> None:
        """Initialize the filters manager."""
        self.storage = _filters_storage

    def get_filters(self, user_id: int) -> dict[str, Any]:
        """Get filters for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Dictionary of filters for the user
        """
        if user_id not in self.storage:
            self.storage[user_id] = {
                "games": set(),
                "levels": set(),
                "min_profit": 0.0,
                "max_price": float("inf"),
            }
        return self.storage[user_id]

    def update_filter(self, user_id: int, filter_key: str, value: Any) -> None:
        """Update a specific filter for a user.

        Args:
            user_id: Telegram user ID
            filter_key: Key of the filter to update
            value: New value for the filter
        """
        filters = self.get_filters(user_id)
        filters[filter_key] = value

    def add_to_set_filter(self, user_id: int, filter_key: str, value: str) -> None:
        """Add a value to a set-based filter.

        Args:
            user_id: Telegram user ID
            filter_key: Key of the set filter
            value: Value to add to the set
        """
        filters = self.get_filters(user_id)
        if filter_key not in filters:
            filters[filter_key] = set()
        if isinstance(filters[filter_key], set):
            filters[filter_key].add(value)

    def remove_from_set_filter(self, user_id: int, filter_key: str, value: str) -> None:
        """Remove a value from a set-based filter.

        Args:
            user_id: Telegram user ID
            filter_key: Key of the set filter
            value: Value to remove from the set
        """
        filters = self.get_filters(user_id)
        if filter_key in filters and isinstance(filters[filter_key], set):
            filters[filter_key].discard(value)

    def clear_filters(self, user_id: int) -> None:
        """Clear all filters for a user.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self.storage:
            del self.storage[user_id]


# Global instance
_filters_manager = FiltersManager()


def get_filters_manager() -> FiltersManager:
    """Get the global filters manager instance.

    Returns:
        Global FiltersManager instance
    """
    return _filters_manager
