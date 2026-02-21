"""Portfolio manager for handling portfolio operations.

Manages portfolio CRUD operations, price updates, and persistence.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from .models import ItemCategory, ItemRarity, Portfolio, PortfolioItem, PortfolioMetrics

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manager for portfolio operations.

    Handles:
    - Loading/saving portfolios
    - Adding/removing items
    - Syncing with DMarket inventory
    - Price updates

    Attributes:
        api: DMarket API client
        portfolios: Dict of user_id -> Portfolio
        storage_path: Path to JSON storage file
    """

    def __init__(
        self,
        api: IDMarketAPI | None = None,
        storage_path: str | Path = "data/portfolios.json",
    ) -> None:
        """Initialize manager.

        Args:
            api: DMarket API client
            storage_path: Path to JSON storage file
        """
        self.api = api
        self._portfolios: dict[int, Portfolio] = {}
        self._storage_path = Path(storage_path)

        # Load existing portfolios
        self._load_portfolios()

    def set_api(self, api: IDMarketAPI) -> None:
        """Set the API client."""
        self.api = api

    def get_portfolio(self, user_id: int) -> Portfolio:
        """Get or create portfolio for user.

        Args:
            user_id: Telegram user ID

        Returns:
            User's portfolio
        """
        if user_id not in self._portfolios:
            self._portfolios[user_id] = Portfolio(user_id=user_id)
            logger.info("portfolio_created", extra={"user_id": user_id})

        return self._portfolios[user_id]

    def add_item(
        self,
        user_id: int,
        item_id: str,
        title: str,
        game: str,
        buy_price: float,
        quantity: int = 1,
        category: str = "other",
        rarity: str = "mil_spec",
    ) -> PortfolioItem:
        """Add item to user's portfolio.

        Args:
            user_id: Telegram user ID
            item_id: DMarket item ID
            title: Item name
            game: Game code
            buy_price: Purchase price
            quantity: Number of items
            category: Item category
            rarity: Item rarity

        Returns:
            Added PortfolioItem
        """
        portfolio = self.get_portfolio(user_id)

        item = PortfolioItem(
            item_id=item_id,
            title=title,
            game=game,
            buy_price=Decimal(str(buy_price)),
            current_price=Decimal(str(buy_price)),  # Will be updated
            quantity=quantity,
            category=ItemCategory(category),
            rarity=ItemRarity(rarity),
        )

        portfolio.add_item(item)
        self._save_portfolios()

        logger.info(
            "item_added_to_portfolio",
            extra={
                "user_id": user_id,
                "item_id": item_id,
                "title": title,
                "buy_price": buy_price,
            },
        )

        return item

    def remove_item(
        self,
        user_id: int,
        item_id: str,
        quantity: int = 1,
        sell_price: float | None = None,
    ) -> PortfolioItem | None:
        """Remove item from user's portfolio.

        Args:
            user_id: Telegram user ID
            item_id: Item to remove
            quantity: Number to remove
            sell_price: Sale price (for P&L tracking)

        Returns:
            Removed item or None
        """
        portfolio = self.get_portfolio(user_id)
        removed = portfolio.remove_item(item_id, quantity)

        if removed:
            self._save_portfolios()
            logger.info(
                "item_removed_from_portfolio",
                extra={
                    "user_id": user_id,
                    "item_id": item_id,
                    "quantity": quantity,
                    "sell_price": sell_price,
                },
            )

        return removed

    async def sync_with_inventory(self, user_id: int) -> int:
        """Sync portfolio with user's DMarket inventory.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of items synced
        """
        if not self.api:
            logger.warning("sync_skipped_no_api")
            return 0

        try:
            # Get inventory from DMarket
            inventory = awAlgot self.api.get_user_inventory(
                game="csgo",
                limit=100,
            )

            portfolio = self.get_portfolio(user_id)
            synced = 0

            if "objects" in inventory:
                for item_data in inventory["objects"]:
                    item_id = item_data.get(
                        "itemId", item_data.get("extra", {}).get("offerId", "")
                    )
                    title = item_data.get("title", "Unknown Item")

                    # Check if already in portfolio
                    existing = portfolio.get_item(item_id)
                    if not existing:
                        # Parse price
                        price_data = item_data.get("price", {})
                        price_cents = int(
                            price_data.get("USD", price_data.get("amount", 0))
                        )
                        price_usd = Decimal(price_cents) / 100

                        # Detect category from title
                        category = self._detect_category(title)

                        item = PortfolioItem(
                            item_id=item_id,
                            title=title,
                            game=item_data.get("gameId", "csgo"),
                            buy_price=price_usd,
                            current_price=price_usd,
                            quantity=1,
                            category=category,
                        )
                        portfolio.add_item(item)
                        synced += 1

            self._save_portfolios()
            logger.info(
                "portfolio_synced",
                extra={"user_id": user_id, "synced_count": synced},
            )

            return synced

        except Exception as e:
            logger.exception("sync_fAlgoled", extra={"error": str(e)})
            return 0

    async def update_prices(self, user_id: int) -> int:
        """Update current prices for all portfolio items.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of prices updated
        """
        if not self.api:
            return 0

        portfolio = self.get_portfolio(user_id)
        if not portfolio.items:
            return 0

        updated = 0

        try:
            updated = awAlgot self._update_prices_by_game(portfolio)
            self._save_portfolios()
            logger.info(
                "prices_updated",
                extra={"user_id": user_id, "updated_count": updated},
            )
        except Exception as e:
            logger.exception("update_prices_fAlgoled", extra={"error": str(e)})

        return updated

    async def _update_prices_by_game(self, portfolio: Portfolio) -> int:
        """Update prices grouped by game.

        Args:
            portfolio: Portfolio to update

        Returns:
            Number of items updated
        """
        # Group items by game
        items_by_game: dict[str, list[PortfolioItem]] = {}
        for item in portfolio.items:
            if item.game not in items_by_game:
                items_by_game[item.game] = []
            items_by_game[item.game].append(item)

        updated = 0

        # Fetch prices for each game
        for game, items in items_by_game.items():
            game_updated = awAlgot self._fetch_and_update_prices(game, items)
            updated += game_updated

        return updated

    async def _fetch_and_update_prices(
        self, game: str, items: list[PortfolioItem]
    ) -> int:
        """Fetch and update prices for items in a game.

        Args:
            game: Game code
            items: Items to update

        Returns:
            Number of items updated
        """
        titles = [item.title for item in items]

        try:
            prices_data = awAlgot self.api.get_aggregated_prices_bulk(
                game=game,
                titles=titles,
                limit=len(titles),
            )
        except Exception as e:
            logger.warning(
                "price_fetch_error",
                extra={"game": game, "error": str(e)},
            )
            return 0

        if "aggregatedPrices" not in prices_data:
            return 0

        updated = 0
        for price_info in prices_data["aggregatedPrices"]:
            updated += self._update_item_price(price_info, items)

        return updated

    def _update_item_price(self, price_info: dict, items: list[PortfolioItem]) -> int:
        """Update item price from price info.

        Args:
            price_info: Price information from API
            items: Items to check

        Returns:
            1 if updated, 0 otherwise
        """
        title = price_info.get("title", "")
        offer_price = int(price_info.get("offerBestPrice", 0))

        if offer_price <= 0:
            return 0

        for item in items:
            if item.title == title:
                item.current_price = Decimal(offer_price) / 100
                return 1

        return 0

    def get_metrics(self, user_id: int) -> PortfolioMetrics:
        """Get portfolio metrics for user.

        Args:
            user_id: Telegram user ID

        Returns:
            Calculated metrics
        """
        portfolio = self.get_portfolio(user_id)
        return portfolio.calculate_metrics()

    def get_items(
        self,
        user_id: int,
        game: str | None = None,
        category: str | None = None,
    ) -> list[PortfolioItem]:
        """Get portfolio items with optional filtering.

        Args:
            user_id: Telegram user ID
            game: Filter by game
            category: Filter by category

        Returns:
            List of matching items
        """
        portfolio = self.get_portfolio(user_id)
        items = portfolio.items

        if game:
            items = [i for i in items if i.game == game]

        if category:
            items = [i for i in items if i.category.value == category]

        return items

    def take_snapshot(self, user_id: int) -> None:
        """Take a snapshot of user's portfolio."""
        portfolio = self.get_portfolio(user_id)
        portfolio.take_snapshot()
        self._save_portfolios()

    def _detect_category(self, title: str) -> ItemCategory:
        """Detect item category from title.

        Args:
            title: Item title

        Returns:
            Detected category
        """
        title_lower = title.lower()

        if "★" in title or "knife" in title_lower:
            return ItemCategory.KNIFE
        if "gloves" in title_lower or "wraps" in title_lower:
            return ItemCategory.GLOVES
        if "sticker" in title_lower:
            return ItemCategory.STICKER
        if "case" in title_lower:
            return ItemCategory.CASE
        if "key" in title_lower:
            return ItemCategory.KEY
        if "agent" in title_lower:
            return ItemCategory.AGENT
        if "music kit" in title_lower:
            return ItemCategory.MUSIC_KIT
        if "graffiti" in title_lower:
            return ItemCategory.GRAFFITI
        if "patch" in title_lower:
            return ItemCategory.PATCH
        if any(
            w in title_lower for w in ["ak-47", "awp", "m4a1", "usp", "glock", "deagle"]
        ):
            return ItemCategory.WEAPON
        return ItemCategory.OTHER

    def _load_portfolios(self) -> None:
        """Load portfolios from storage."""
        if not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, encoding="utf-8") as f:
                data = json.load(f)

            for user_id_str, portfolio_data in data.items():
                user_id = int(user_id_str)
                self._portfolios[user_id] = Portfolio.from_dict(portfolio_data)

            logger.info(
                "portfolios_loaded",
                extra={"count": len(self._portfolios)},
            )

        except Exception as e:
            logger.warning("load_portfolios_error", extra={"error": str(e)})

    def _save_portfolios(self) -> None:
        """Save portfolios to storage."""
        try:
            # Ensure directory exists
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                str(user_id): portfolio.to_dict()
                for user_id, portfolio in self._portfolios.items()
            }

            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.exception("save_portfolios_error", extra={"error": str(e)})


__all__ = ["PortfolioManager"]
