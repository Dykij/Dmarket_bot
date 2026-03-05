"""
Script: src/bot/trader.py (The Hands)
Description: Manages Targets (Buying) and Offers (Selling).
Executes orders based on opportunities from the Scanner.
Includes deduplication to avoid placing duplicate buy orders.
"""

import asyncio
import logging
import time
from typing import Dict, Set

import aiohttp

from src.config import Config
from src.models import TargetsResponse
from src.utils.api_client import AsyncDMarketClient
from src.utils.db import profit_db
from src.utils.notifier import get_notifier

logger = logging.getLogger("Trader")

# How often to refresh active targets cache (seconds)
TARGETS_CACHE_TTL = 60


class MarketMaker:
    """
    Places Targets (Bids) and lists purchased items (Asks).
    Handles the actual trading operations with deduplication.
    """

    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.dry_run = Config.DRY_RUN
        self.game_id = Config.GAME_ID

        # Cache of currently active target titles — refreshed every TARGETS_CACHE_TTL seconds
        self._active_target_titles: Set[str] = set()
        self._targets_cache_time: float = 0.0

    async def _refresh_active_targets(self, force: bool = False) -> None:
        """Refreshes the local cache of active target titles from the API."""
        now = time.time()
        if not force and (now - self._targets_cache_time) < TARGETS_CACHE_TTL:
            return  # Cache is fresh

        if self.dry_run:
            self._targets_cache_time = now
            return

        try:
            raw_response = await self.client.get_user_targets(game=self.game_id)
            response = TargetsResponse.model_validate(raw_response)
            targets = response.all_targets
            self._active_target_titles = {t.Title for t in targets if t.Title}
            self._targets_cache_time = now
            logger.debug(
                "Active targets cache refreshed: %d targets",
                len(self._active_target_titles),
            )
        except aiohttp.ClientResponseError as e:
            logger.warning(
                "Could not refresh active targets (API %s): %s", e.status, e.message
            )
        except asyncio.TimeoutError:
            logger.warning("Could not refresh active targets: timeout")
        except Exception as e:
            logger.warning("Could not refresh active targets: %s", e)

    async def place_target(self, opportunity: Dict) -> bool:
        """Places a Buy Order (Target) — skips if one already exists for this item."""
        title = opportunity["title"]
        target_price = opportunity["target_price"]
        profit_usd = opportunity["profit"] / 100.0

        # --- DEDUPLICATION CHECK ---
        await self._refresh_active_targets()
        if title in self._active_target_titles:
            logger.debug("⏭️ SKIP (already active): %s", title)
            return False

        # Check MAX open targets cap
        if len(self._active_target_titles) >= Config.MAX_OPEN_TARGETS:
            logger.warning(
                "🚫 MAX_OPEN_TARGETS (%d) reached. Skipping %s.",
                Config.MAX_OPEN_TARGETS,
                title,
            )
            return False

        # --- Smart Attributes (Float) ---
        attrs = []
        if Config.PREFER_LOW_FLOAT:
            exterior_code = None
            if "(Factory New)" in title:
                exterior_code = "FN"
            elif "(Minimal Wear)" in title:
                exterior_code = "MW"
            elif "(Field-Tested)" in title:
                exterior_code = "FT"
            elif "(Well-Worn)" in title:
                exterior_code = "WW"
            elif "(Battle-Scarred)" in title:
                exterior_code = "BS"

            if exterior_code and exterior_code in Config.FLOAT_CODES:
                best_floats = Config.FLOAT_CODES[exterior_code]
                for code in best_floats:
                    attrs.append({"Name": "floatPartValue", "Value": code})

        if self.dry_run:
            attr_str = f" [Attrs: {attrs}]" if attrs else ""
            logger.info(
                f"🎯 [SIMULATION] Placed TARGET on '{title}' at ${(target_price / 100):.2f}{attr_str}"
            )
            # Track in the local set for deduplication within the same dry-run session
            self._active_target_titles.add(title)
            return True

        try:
            target_data = {
                "Amount": 1,
                "Price": {"Amount": target_price, "Currency": "USD"},
                "Title": title,
            }
            if attrs:
                target_data["Attrs"] = attrs

            await self.client.request(
                "POST",
                "/marketplace-api/v1/user-targets/create",
                body={"GameID": self.game_id, "Targets": [target_data]},
            )

            logger.info(
                f"✅ TARGET ACTIVE: {title} @ ${(target_price / 100):.2f} (Net Profit: ${profit_usd:.2f})"
            )
            # Update local cache immediately
            self._active_target_titles.add(title)

            # Record in SQLite and notify TG
            sell_price_est = int(
                target_price + (profit_usd * 100) / (1.0 - Config.FEE_RATE)
            )
            expected_profit = int(profit_usd * 100)
            await profit_db.record_target(
                title, target_price, sell_price_est, expected_profit
            )
            await get_notifier().send_message(
                f"🎯 *TARGET PLACED*\n"
                f"Item: `{title}`\n"
                f"Buy at: `${target_price / 100:.2f}`\n"
                f"Sell est: `${sell_price_est / 100:.2f}`\n"
                f"Est. Profit: `${expected_profit / 100:.2f}`"
            )

            return True

        except aiohttp.ClientResponseError as e:
            logger.error(f"❌ Target API error on {title} ({e.status}): {e.message}")
            return False
        except asyncio.TimeoutError:
            logger.error(f"❌ Target timeout on {title}")
            return False
        except Exception as e:
            logger.error(
                f"❌ Target unexpected error on {title}: {type(e).__name__}: {e}"
            )
            return False

    async def cancel_stale_targets(
        self, current_opportunities: Dict[str, Dict]
    ) -> None:
        """
        Cancels active targets whose items are no longer profitable.
        Call this once per cycle with the latest scan opportunities dict.
        """
        if self.dry_run:
            return  # Nothing to cancel in simulation mode

        try:
            raw_response = await self.client.get_user_targets(game=self.game_id)
            response = TargetsResponse.model_validate(raw_response)
            targets = response.all_targets

            to_cancel = []
            for target in targets:
                target_id = target.target_id
                title = target.Title

                if title not in current_opportunities:
                    logger.info(
                        f"🗑️ Cancelling stale target: {title} (no longer profitable)"
                    )
                    to_cancel.append({"TargetID": target_id})

            if to_cancel:
                await self.client.delete_target(to_cancel)
                logger.info(f"🗑️ Cancelled {len(to_cancel)} stale targets.")
                self._targets_cache_time = 0.0

        except aiohttp.ClientResponseError as e:
            logger.error(f"cancel_stale_targets API error ({e.status}): {e.message}")
        except asyncio.TimeoutError:
            logger.error("cancel_stale_targets timeout")
        except Exception as e:
            logger.error(f"cancel_stale_targets failed: {type(e).__name__}: {e}")
