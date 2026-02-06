"""SuperMemory integration for persistent bot memory.

This module provides a wrapper around the SuperMemory API for storing
and retrieving conversation context, user preferences, and trading history.

Usage:
    from src.utils.supermemory_client import SuperMemoryClient

    client = SuperMemoryClient()
    await client.remember("User prefers CS2 arbitrage", user_id=123)
    results = await client.recall("What games does user prefer?", user_id=123)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog


if TYPE_CHECKING:
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)


class SuperMemoryClient:
    """Client for SuperMemory persistent memory API.

    Provides methods for storing and retrieving memories across sessions,
    enabling the bot to remember user preferences and trading patterns.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize SuperMemory client.

        Args:
            api_key: SuperMemory API key. If not provided, reads from
                     SUPERMEMORY_API_KEY environment variable.
        """
        self._api_key = api_key or os.getenv("SUPERMEMORY_API_KEY")
        self._enabled = os.getenv("SUPERMEMORY_ENABLED", "true").lower() == "true"
        self._client: Any = None

        if self._api_key and self._enabled:
            try:
                from supermemory import Supermemory

                self._client = Supermemory(api_key=self._api_key)
                logger.info("supermemory_initialized", enabled=True)
            except ImportError:
                logger.warning(
                    "supermemory_not_installed",
                    hint="pip install supermemory",
                )
        else:
            logger.info(
                "supermemory_disabled",
                has_key=bool(self._api_key),
                enabled=self._enabled,
            )

    @property
    def is_available(self) -> bool:
        """Check if SuperMemory is available and configured."""
        return self._client is not None

    async def remember(
        self,
        content: str,
        user_id: int | str | None = None,
        container_tag: str = "dmarket_bot",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Store a memory in SuperMemory.

        Args:
            content: The content to remember
            user_id: Optional user ID for user-specific memories
            container_tag: Tag for organizing memories
            metadata: Additional metadata to store

        Returns:
            Response from SuperMemory API or None if unavailable
        """
        if not self.is_available:
            logger.debug("supermemory_skip", reason="not_available")
            return None

        try:
            full_metadata = dict(metadata) if metadata else {}
            if user_id:
                full_metadata["user_id"] = str(user_id)
                container_tag = f"{container_tag}_user_{user_id}"

            response = self._client.memories.add(
                content=content,
                container_tag=container_tag,
                metadata=full_metadata,
            )

            logger.info(
                "supermemory_stored",
                container=container_tag,
                content_length=len(content),
            )
            return response

        except Exception:
            logger.exception("supermemory_store_error")
            return None

    async def recall(
        self,
        query: str,
        user_id: int | str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memories in SuperMemory.

        Args:
            query: Search query
            user_id: Optional user ID to filter by
            limit: Maximum number of results

        Returns:
            List of matching memories
        """
        if not self.is_available:
            logger.debug("supermemory_skip", reason="not_available")
            return []

        try:
            # Add user context to query if provided
            if user_id:
                query = f"user {user_id}: {query}"

            response = self._client.search.execute(q=query)

            results = response.results[:limit] if response.results else []
            logger.info(
                "supermemory_recalled",
                query=query[:50],
                results_count=len(results),
            )
            return results

        except Exception:
            logger.exception("supermemory_recall_error")
            return []

    async def remember_trade(
        self,
        user_id: int,
        item_name: str,
        game: str,
        action: str,
        price: float,
        profit: float | None = None,
    ) -> dict[str, Any] | None:
        """Store a trade memory for pattern learning.

        Args:
            user_id: User who made the trade
            item_name: Name of traded item
            game: Game (csgo, dota2, etc.)
            action: buy/sell
            price: Trade price
            profit: Profit if known

        Returns:
            Response from SuperMemory API
        """
        content = f"Trade: {action} {item_name} ({game}) at ${price:.2f}" + (
            f" with {profit:.1f}% profit" if profit else ""
        )

        return await self.remember(
            content=content,
            user_id=user_id,
            container_tag=f"trades_{game}",
            metadata={
                "item_name": item_name,
                "game": game,
                "action": action,
                "price": price,
                "profit": profit,
            },
        )

    async def remember_preference(
        self,
        user_id: int,
        preference_type: str,
        value: str,
    ) -> dict[str, Any] | None:
        """Store a user preference.

        Args:
            user_id: User ID
            preference_type: Type of preference (game, level, notification, etc.)
            value: Preference value

        Returns:
            Response from SuperMemory API
        """
        content = f"User preference: {preference_type} = {value}"

        return await self.remember(
            content=content,
            user_id=user_id,
            container_tag="preferences",
            metadata={
                "preference_type": preference_type,
                "value": value,
            },
        )

    async def get_user_context(self, user_id: int) -> str:
        """Get aggregated context about a user for AI prompts.

        Args:
            user_id: User ID to get context for

        Returns:
            Formatted context string for AI prompts
        """
        if not self.is_available:
            return ""

        try:
            # Get user preferences and recent trades
            preferences = await self.recall(
                f"preferences for user {user_id}",
                user_id=user_id,
                limit=10,
            )
            trades = await self.recall(
                f"recent trades by user {user_id}",
                user_id=user_id,
                limit=5,
            )

            context_parts = []
            if preferences:
                context_parts.append("User preferences:")
                for pref in preferences:
                    if hasattr(pref, "content"):
                        context_parts.append(f"  - {pref.content}")

            if trades:
                context_parts.append("Recent trades:")
                for trade in trades:
                    if hasattr(trade, "content"):
                        context_parts.append(f"  - {trade.content}")

            return "\n".join(context_parts) if context_parts else ""

        except Exception:
            logger.exception("supermemory_context_error")
            return ""


# Global client instance (lazy initialization)
_client: SuperMemoryClient | None = None


def get_supermemory_client() -> SuperMemoryClient:
    """Get or create global SuperMemory client."""
    global _client
    if _client is None:
        _client = SuperMemoryClient()
    return _client
