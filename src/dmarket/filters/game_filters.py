"""Game filters."""
from typing import Any


class FilterFactory:
    """Factory for game-specific filters."""

    @classmethod
    def get_filter(cls, game: str) -> dict[str, Any]:
        """Get filter configuration for a game."""
        return {"game": game, "min_price": 0.10, "max_price": 50000}


def apply_filters_to_items(
    items: list[dict[str, Any]],
    game: str = "csgo",
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply filters to a list of items."""
    if not filters:
        return items
    min_p = filters.get("min_price", 0)
    max_p = filters.get("max_price", float("inf"))
    result = []
    for it in items:
        price = it.get("price", {})
        if isinstance(price, dict):
            p = int(price.get("USD", 0)) / 100.0
        else:
            p = float(price)
        if min_p <= p <= max_p:
            result.append(it)
    return result
