"""
InventoryManager — Tracks DMarket inventory + CS2Cap price data.

Features:
- Full pagination for inventory/offers
- Marks purchased items in virtual_inventory table
- CS2Cap price checks for each held item
- PnL tracking per item
"""

import logging
import time
from typing import Any, Dict, List

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.db.price_history import price_db

logger = logging.getLogger("InventoryManager")


class InventoryManager:
    """
    Manages User's DMarket Inventory for Auto-Resale Tracking.
    Full pagination support + CS2Cap price intelligence.
    """

    def __init__(self, api_client: DMarketAPIClient):
        self.api = api_client
        self.cs2cap = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
        self.cached_inventory: List[Dict[str, Any]] = []
        self.cached_offers: List[Dict[str, Any]] = []

    # =================================================================
    # 1. INVENTORY FETCHING (with full pagination)
    # =================================================================

    async def fetch_inventory(self, game_id: str = "a8db") -> List[Dict[str, Any]]:
        """
        Fetches the primary user inventory (items NOT on sale).
        Uses full cursor-based pagination to gather ALL items.
        """
        inventory = []
        cursor = None
        page = 0
        max_pages = 50  # Safety limit

        try:
            while page < max_pages:
                response = await self.api.get_user_inventory(
                    game_id=game_id, limit=50, cursor=cursor
                )
                items = response.get("objects", [])
                inventory.extend(items)

                cursor = response.get("cursor")
                page += 1

                if not cursor or len(items) < 50:
                    break

            self.cached_inventory = inventory
            logger.info(f"📦 Fetched {len(inventory)} inventory items ({page} pages)")
            return inventory

        except Exception as e:
            logger.error(f"Failed to fetch DMarket inventory: {e}", exc_info=True)
            return self.cached_inventory

    async def fetch_active_offers(self, game_id: str = "a8db") -> List[Dict[str, Any]]:
        """
        Fetches items currently listed for sale on DMarket.
        Full pagination support.
        """
        offers = []
        cursor = None
        page = 0
        max_pages = 50

        try:
            while page < max_pages:
                response = await self.api.get_user_active_offers(
                    game_id=game_id, limit=50, cursor=cursor
                )
                items = response.get("objects", [])
                offers.extend(items)

                cursor = response.get("cursor")
                page += 1

                if not cursor or len(items) < 50:
                    break

            self.cached_offers = offers
            logger.info(f"🏷️ Fetched {len(offers)} active sell offers ({page} pages)")
            return offers

        except Exception as e:
            logger.error(f"Failed to fetch active offers: {e}", exc_info=True)
            return []

    async def fetch_all_with_cs2cap(self, game_id: str = "a8db") -> Dict[str, Any]:
        """
        Fetch inventory + offers + CS2Cap prices for each item.
        Returns enriched data with current market values.

        Phase 6 optimization: merges the two near-identical loops over
        inventory and offers into a single pass, deduplicates titles, and
        fetches CS2Cap prices in one /prices/batch call (1 HTTP request
        instead of N).
        """
        inventory = await self.fetch_inventory(game_id)
        offers = await self.fetch_active_offers(game_id)

        # --- One pass over (inventory + offers) with a status flag ---
        enriched_items: List[Dict[str, Any]] = []
        unique_titles: List[str] = []

        for item in inventory:
            title = item.get("title", "")
            item_id = item.get("itemId", "")
            price_cents = int(item.get("price", {}).get("USD", 0))
            buy_price = price_cents / 100.0
            if title and title not in unique_titles:
                unique_titles.append(title)
            enriched_items.append({
                "item_id": item_id,
                "title": title,
                "buy_price": buy_price,
                "cs2cap_price": 0.0,
                "profit_pct": 0.0,
                "status": "inventory",
            })

        for offer in offers:
            title = offer.get("title", "")
            offer_id = offer.get("offerId", "")
            price_cents = int(offer.get("price", {}).get("USD", 0))
            list_price = price_cents / 100.0
            if title and title not in unique_titles:
                unique_titles.append(title)
            enriched_items.append({
                "item_id": offer_id,
                "title": title,
                "list_price": list_price,
                "cs2cap_price": 0.0,
                "status": "on_sale",
            })

        # --- 1 CS2Cap call for all unique titles (Phase 6 batch) ---
        cs_prices: Dict[str, float] = {}
        if self.cs2cap and unique_titles:
            try:
                snapshots = await self.cs2cap.get_prices_batch(unique_titles)
                cs_prices = {
                    t: s.min_price for t, s in snapshots.items() if s.has_data
                }
            except AttributeError:
                # Fallback for CSFloat oracle (no batch endpoint)
                for title in unique_titles:
                    try:
                        p = await self.cs2cap.get_item_price(title)
                        if p > 0:
                            cs_prices[title] = p
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"CS2Cap batch failed in fetch_all_with_cs2cap: {e}")

        # --- Backfill the enriched_items with the batched prices ---
        for entry in enriched_items:
            title = entry.get("title", "")
            cs2cap_price = cs_prices.get(title, 0.0)
            entry["cs2cap_price"] = cs2cap_price
            buy_price = entry.get("buy_price", 0.0)
            if cs2cap_price > 0 and buy_price > 0:
                entry["profit_pct"] = (
                    (cs2cap_price * 0.95 - buy_price) / buy_price
                ) * 100

        return {
            "inventory": enriched_items,
            "inventory_count": len(inventory),
            "offers_count": len(offers),
            "total_items": len(inventory) + len(offers),
        }

    # =================================================================
    # 2. ITEM TRACKING
    # =================================================================

    def mark_item_purchased(self, title: str, buy_price: float, item_id: str = ""):
        """Mark an item as purchased in the virtual inventory."""
        price_db.add_virtual_item(title, buy_price, trade_lock_hours=168)
        if item_id:
            price_db.record_placed_target(item_id, title, buy_price)
        logger.info(f"📝 Marked as purchased: {title} @ ${buy_price:.2f}")

    def mark_item_listed(self, item_db_id: int, sell_price: float):
        """Mark an item as listed for sale."""
        price_db.update_virtual_status(item_db_id, 'selling')
        logger.info(f"📝 Marked as listed: item#{item_db_id} @ ${sell_price:.2f}")

    def mark_item_sold(self, item_db_id: int, sell_price: float, fee: float = 0.0):
        """Mark an item as sold and record PnL."""
        price_db.record_virtual_sale(item_db_id, sell_price, fee)
        logger.info(f"💰 Marked as sold: item#{item_db_id} @ ${sell_price:.2f}")

    def is_item_purchased(self, item_id: str) -> bool:
        """Check if an item has already been purchased."""
        return price_db.has_target_been_placed(item_id)

    # =================================================================
    # 3. P&L TRACKING
    # =================================================================

    def get_portfolio_summary(self, current_balance: float = 0.0) -> Dict[str, Any]:
        """Get full portfolio summary with PnL."""
        equity = price_db.get_total_equity(current_balance)

        # Get all items for detailed PnL
        all_items = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
        selling = price_db.get_virtual_inventory(status='selling')
        sold = price_db.get_virtual_inventory(status='sold')

        total_invested = sum(i['buy_price'] for i in all_items + selling)
        total_realized = sum(
            (i['sell_price'] or 0) - (i['buy_price'] or 0) - (i['fee_paid'] or 0)
            for i in sold
        )

        return {
            "cash": equity['cash'],
            "assets_value": equity['assets'],
            "total_equity": equity['total'],
            "total_invested": total_invested,
            "total_realized_pnl": total_realized,
            "items_holding": len(all_items) + len(selling),
            "items_sold": len(sold),
            "avg_buy_price": total_invested / max(1, len(all_items) + len(selling)),
        }

    # =================================================================
    # 4. CS2Cap PRICE CHECK FOR HELD ITEMS
    # =================================================================

    async def check_held_items_prices(self) -> List[Dict[str, Any]]:
        """
        Check CS2Cap prices for all held items.
        Returns list of items with current market value.

        Phase 6 optimization: uses CS2Cap /prices/batch in 1 call instead
        of N per-item calls.
        """
        items = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
        if not items:
            return []

        unique_titles = list({it['hash_name'] for it in items})
        cs_prices: Dict[str, float] = {}
        if self.cs2cap and unique_titles:
            try:
                snapshots = await self.cs2cap.get_prices_batch(unique_titles)
                cs_prices = {
                    t: s.min_price for t, s in snapshots.items() if s.has_data
                }
            except AttributeError:
                for title in unique_titles:
                    try:
                        p = await self.cs2cap.get_item_price(title)
                        if p > 0:
                            cs_prices[title] = p
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"CS2Cap batch failed in check_held_items_prices: {e}")

        results: List[Dict[str, Any]] = []
        for item in items:
            title = item['hash_name']
            buy_price = item['buy_price']
            cs2cap_price = cs_prices.get(title, 0.0)
            unrealized_pnl = 0.0
            if cs2cap_price > 0 and buy_price > 0:
                unrealized_pnl = ((cs2cap_price * 0.95 - buy_price) / buy_price) * 100

            results.append({
                "title": title,
                "buy_price": buy_price,
                "cs2cap_price": cs2cap_price,
                "unrealized_pnl_pct": unrealized_pnl,
                "status": item['status'],
                "acquired": time.ctime(item['acquired_at']),
            })

        return results

    # =================================================================
    # 5. CACHE
    # =================================================================

    def get_inventory(self) -> List[Dict[str, Any]]:
        """Returns the last fetched inventory cache."""
        return self.cached_inventory

    def get_offers(self) -> List[Dict[str, Any]]:
        """Returns the last fetched offers cache."""
        return self.cached_offers
