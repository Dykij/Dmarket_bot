"""
account.py — Account, balance, inventory, and transaction history.

Mixin with read-only account endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

from src.config import Config  # P1-20: centralized DRY_RUN
from src.utils.units import cents_to_usd
from datetime import datetime
import os
import time
from typing import Any

import structlog

logger = structlog.get_logger("DMarketAPI")


def _parse_iso_ts(val: Any) -> float:
    """Parse an ISO-8601 timestamp or numeric string/number into Unix seconds (0.0 if unset/epoch)."""
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else 0.0
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return 0.0
        try:
            num = float(s)
            return num if num > 0 else 0.0
        except ValueError:
            pass
        try:
            ts = datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
            return ts if ts > 0 else 0.0
        except ValueError:
            return 0.0
    return 0.0


class _AccountMixin:
    """Read-only account endpoints (balance, inventory, transactions)."""

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    # v16.3: In-memory balance cache to avoid $1000 fallback on 429
    _cached_balance: float | None = None
    _cached_balance_ts: float = 0.0
    _BALANCE_CACHE_TTL: float = 300.0  # 5 minutes

    async def get_real_balance(self) -> float:
        """Fetches the current USD & DMC balance. Supports Real Balance in Dry Run.

        v16.3: Caches last known real balance. On API failure, uses cached
        value instead of hardcoded $1000 fallback. Cache TTL = 5 minutes.
        """
        try:
            res = await self.make_request("GET", "/account/v1/balance")
            if not isinstance(res, dict):
                raise ValueError(f"Unexpected response type from balance API: {type(res)}")
            if "usdAvailableToWithdraw" in res:
                raw_val = res["usdAvailableToWithdraw"]
                try:
                    num_val = float(raw_val)
                except (ValueError, TypeError):
                    num_val = 0.0
                known_bal = float(res.get("balance") or 0)
                ratio_str = f"{num_val/known_bal}" if known_bal else "N/A"
                logger.info(f"OBSERVED (not used): usdAvailableToWithdraw={raw_val}, balance={known_bal}, ratio={ratio_str}")
            if "balance" in res:
                usd_balance = float(res["balance"])
            elif "usd" in res:
                usd_balance = cents_to_usd(res["usd"])
            else:
                raise KeyError("Balance fields missing in response")
            # Update cache on success
            type(self)._cached_balance = usd_balance
            type(self)._cached_balance_ts = time.monotonic()
            return usd_balance
            
        except (KeyError, ValueError, TypeError) as e:
            # Schema parsing error
            cached = type(self)._cached_balance
            cache_age = time.monotonic() - type(self)._cached_balance_ts
            if cached is not None and cache_age < type(self)._BALANCE_CACHE_TTL:
                logger.error(f"SCHEMA_ERROR: balance fetch parsing failed, using cached ${cached:.2f} (age={cache_age:.0f}s): {e}")
                return cached
            if Config.DRY_RUN:
                fallback = float(os.getenv("DRY_RUN_BALANCE_FALLBACK", "1000.0"))
                logger.error(f"SCHEMA_ERROR: balance fetch parsing failed (no cache), using fallback ${fallback:.2f}: {e}")
                return fallback
            raise e
            
        except Exception as e:
            # Network error or other issues
            cached = type(self)._cached_balance
            cache_age = time.monotonic() - type(self)._cached_balance_ts
            if cached is not None and cache_age < type(self)._BALANCE_CACHE_TTL:
                logger.warning(f"Balance fetch network failed, using cached ${cached:.2f} (age={cache_age:.0f}s): {e}")
                return cached
            if Config.DRY_RUN:
                fallback = float(os.getenv("DRY_RUN_BALANCE_FALLBACK", "1000.0"))
                logger.warning(f"Balance fetch network failed (no cache), using fallback ${fallback:.2f}: {e}")
                return fallback
            raise e

    async def get_user_inventory(
        self, game_id: str, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetch the user's inventory (one page).

        Endpoint: GET /marketplace-api/v2/user/inventory (spec v2.0.0:
        gameId + limit 1..100 required, cursor optional). The old
        /exchange/v1/user-inventory is absent from the spec and answered 404
        on the live read of 2026-11-15.

        Returns the legacy shape {"objects": [...], "cursor": str | None} that
        callers already use. Each object carries itemId/assetId (both =
        attributes.id), title, inGameAssetId and inMarket (item-level flag:
        True = held on DMarket, False = still in the Steam inventory, None =
        not present in the response). It is NOT verified whether items already
        listed for sale appear here. Errors are not swallowed.
        """
        params: dict[str, Any] = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        res = await self.make_request(
            "GET", "/marketplace-api/v2/user/inventory", params=params
        )
        objects: list[dict[str, Any]] = []
        for it in (res or {}).get("items") or []:
            attrs = it.get("attributes") or {}
            asset_id = attrs.get("id", "")
            objects.append(
                {
                    "itemId": asset_id,
                    "assetId": asset_id,
                    "title": attrs.get("title", ""),
                    "inGameAssetId": attrs.get("inGameAssetId", ""),
                    "inMarket": it.get("inMarket"),
                }
            )
        return {"objects": objects, "cursor": (res or {}).get("cursor") or None}

    # --- v12.2: Detailed Inventory with Status (Phase 2.1) ---
    # Confirmed: dmarket.com/blog/dmarket-public-api-updates/, 2026-03-24 — status values trade_protected/reverted, FinalizationTime field.
    async def get_user_inventory_detailed(
        self,
        game_id: str,
        limit: int = 100,
        cursor: str | None = None,
        basic: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch user inventory with FULL status info: trade_protected, reverted, FinalizationTime.

        Endpoint: GET /marketplace-api/v2/user/inventory (spec v2.0.0: gameId + limit 1..100, cursor).
        `basic` is kept in the signature for call compatibility and is not sent to v2.
        """
        del basic  # unused in v2
        all_items: list[dict[str, Any]] = []
        current_cursor = cursor or ""
        seen_cursors: set[str] = set()

        for _ in range(10):  # max 10 pages = 1000 items
            params: dict[str, Any] = {"gameId": game_id, "limit": limit}
            if current_cursor:
                params["cursor"] = current_cursor
            try:
                res = await self.make_request("GET", "/marketplace-api/v2/user/inventory", params=params)  # sel5:v2-path
            except Exception as e:
                logger.warning(f"Detailed inventory fetch failed: {e}", exc_info=True)
                return all_items

            now = time.time()
            items = (res or {}).get("items", (res or {}).get("objects", [])) or []
            for it in items:
                attrs = it.get("attributes") or {}
                item_id = attrs.get("id", "")  # sel5:map-item-id
                title = attrs.get("title", "")  # sel5:map-title

                unlock_ts = _parse_iso_ts(attrs.get("unlockDate"))
                revert_ts = _parse_iso_ts(attrs.get("revertPendingUntil"))
                finalization_time = max(unlock_ts, revert_ts)

                raw_status = str(attrs.get("status") or it.get("status") or "").strip().lower()
                is_locked = revert_ts > now or unlock_ts > now  # sel6:is-locked
                if raw_status in ("reverted", "sold", "trade_protected"):
                    status_lower = raw_status
                elif is_locked:
                    status_lower = "trade_protected"
                else:
                    status_lower = "active"

                created_at = _parse_iso_ts(it.get("createdAt") or it.get("acquiredAt"))

                all_items.append(
                    {
                        "itemId": item_id,
                        "title": title,
                        "status": status_lower,
                        "FinalizationTime": finalization_time,
                        "price": it.get("suggestedPrice") or it.get("price") or {},
                        "createdAt": created_at,
                    }
                )

            if current_cursor:
                seen_cursors.add(current_cursor)
            current_cursor = (res or {}).get("cursor") or ""  # sel5:cursor-next
            if not current_cursor or current_cursor in seen_cursors:
                break

        return all_items


