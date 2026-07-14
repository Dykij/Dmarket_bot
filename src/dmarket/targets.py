"""Target management — creates, lists, and deletes buy targets."""
from __future__ import annotations

from typing import Any


class TargetManager:
    """Manages DMarket buy targets (orders)."""

    def __init__(self, api_client: Any = None, game_id: str = "a8db") -> None:
        self.api = api_client
        self.game_id = game_id

    async def create_target(
        self,
        title: str,
        price: float,
        amount: int = 1,
        game: str = "a8db",
    ) -> dict[str, Any]:
        """Create a buy target.

        Raises:
            ValueError: If price <= 0 or title is empty.
        """
        if price <= 0:
            raise ValueError("Price must be > 0 (больше 0)")
        if not title:
            raise ValueError("Title cannot be empty")

        if self.api is None:
            return {"target_id": "", "title": title, "price": price}

        result = await self.api.create_target(
            game_id=game,
            targets=[{
                "Title": title,
                "Amount": amount,
                "Price": {"Amount": int(price * 100), "Currency": "USD"},
            }],
        )
        targets = result.get("Result", result.get("Targets", []))
        if targets and isinstance(targets, list) and len(targets) > 0:
            first = targets[0]
            return {
                "targetId": first.get("TargetID", first.get("targetId", "")),
                "title": title,
                "price": price,
                "status": first.get("Status", "created"),
            }
        return {"targetId": result.get("targetId", ""), "title": title, "price": price}

    async def get_targets(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get active targets."""
        if self.api is None:
            return []
        result = await self.api.get_targets(game_id=self.game_id, limit=limit)
        return result.get("Items", result.get("items", []))

    async def get_user_targets(
        self,
        game: str = "a8db",
        status: str = "active",
        limit: int = 100,
        offset: int = 0,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Get user's active targets."""
        if self.api is None:
            return []
        result = await self.api.get_user_targets(game_id=game, limit=limit)
        items = result.get("Items", result.get("items", result.get("targets", [])))
        if isinstance(items, list):
            return items
        return []

    async def delete_target(self, target_id: str) -> bool:
        """Delete a target. Returns True on success, False on failure."""
        if self.api is None:
            return True
        try:
            result = await self.api.delete_target(target_id)
            if isinstance(result, dict) and result.get("error"):
                return False
            return True
        except Exception:
            return False

    async def delete_all_targets(self) -> int:
        """Delete all targets. Returns count of deleted targets."""
        if self.api is None:
            return 0
        targets = await self.get_user_targets()
        deleted = 0
        for t in targets:
            tid = t.get("targetId", t.get("TargetID", ""))
            if tid and await self.delete_target(tid):
                deleted += 1
        return deleted
