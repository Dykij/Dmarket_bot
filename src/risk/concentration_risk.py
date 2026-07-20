"""
concentration_risk.py — Portfolio Concentration Risk Management.

Kelly criterion calculates position size in isolation — it doesn't see
that 5 skins from the same collection = one big bet on that collection.

This module adds collection-level and category-level concentration checks
to prevent over-correlation risk.

Source: ROADMAP_DMARKET2026.md — Portfolio Concentration Risk
Complexity: O(N) where N = number of items in inventory
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ConcentrationRisk")


@dataclass
class ConcentrationCheck:
    """Result of a concentration check."""
    allowed: bool = True
    reason: str = ""
    current_concentration: float = 0.0
    max_allowed: float = 0.0
    collection: str = ""
    category: str = ""


@dataclass
class CollectionExposure:
    """Exposure to a single collection/category."""
    name: str
    item_count: int = 0
    total_value_usd: float = 0.0
    pct_of_portfolio: float = 0.0
    items: list[str] = field(default_factory=list)


class ConcentrationRiskManager:
    """
    Portfolio concentration risk management.

    Prevents over-concentration in:
    - Same item (hash_name)
    - Same collection (weapon collection)
    - Same category (knife, glove, rifle, etc.)
    - Same price tier (low, mid, high)

    Usage:
        crm = ConcentrationRiskManager(price_db)
        check = crm.check_concentration(
            item_title="AK-47 | Redline",
            buy_price=15.0,
            current_balance=100.0,
        )
        if not check.allowed:
            # Skip — too concentrated
    """

    # Concentration limits
    MAX_SAME_ITEM_PCT: float = 0.20       # Max 20% in same item
    MAX_SAME_COLLECTION_PCT: float = 0.30  # Max 30% in same collection
    MAX_SAME_CATEGORY_PCT: float = 0.40    # Max 40% in same category
    MAX_SAME_ITEM_COUNT: int = 3           # Max 3 units of same item

    # Category classification
    CATEGORIES = {
        "knife": ["Karambit", "Butterfly", "M9 Bayonet", "Bayonet", "Flip",
                   "Gut", "Huntsman", "Falchion", "Bowie", "Shadow Daggers",
                   "Navaja", "Stiletto", "Talon", "Ursus", "Classic"],
        "glove": ["Sport Gloves", "Driver Gloves", "Hand Wraps", "Moto Gloves",
                   "Specialist Gloves", "Hydra Gloves", "Broken Fang Gloves"],
        "rifle": ["AK-47", "M4A4", "M4A1-S", "AWP", "SSG 08", "SG 553", "AUG"],
        "pistol": ["Desert Eagle", "USP-S", "Glock-18", "P250", "Five-SeveN",
                    "Tec-9", "CZ75-Auto", "R8 Revolver"],
        "smg": ["MP9", "MAC-10", "UMP-45", "P90", "PP-Bizon", "MP7", "MP5-SD"],
        "shotgun": ["Nova", "XM1014", "Sawed-Off", "MAG-7"],
        "machinegun": ["M249", "Negev"],
    }

    def __init__(self, price_db: Any) -> None:
        self.price_db = price_db

    def check_concentration(
        self,
        item_title: str,
        buy_price: float,
        current_balance: float,
    ) -> ConcentrationCheck:
        """
        Check if buying this item would violate concentration limits.

        Args:
            item_title: Item name (e.g., "AK-47 | Redline (Field-Tested)")
            buy_price: Price of the item to buy
            current_balance: Current available balance

        Returns:
            ConcentrationCheck with allowed=True/False and reason.
        """
        if current_balance <= 0:
            return ConcentrationCheck(allowed=False, reason="Zero balance")

        # Get current inventory
        inventory = self._get_inventory()
        if not inventory:
            return ConcentrationCheck(allowed=True)  # Empty inventory — OK

        total_value = sum(item.get("buy_price", 0) for item in inventory)
        total_value += buy_price  # Include proposed purchase

        if total_value <= 0:
            return ConcentrationCheck(allowed=True)

        # 1. Check same item count
        same_item_count = sum(
            1 for item in inventory
            if item.get("hash_name", "") == item_title
        )
        if same_item_count >= self.MAX_SAME_ITEM_COUNT:
            return ConcentrationCheck(
                allowed=False,
                reason=f"Max {self.MAX_SAME_ITEM_COUNT} units of same item "
                       f"(have {same_item_count})",
                current_concentration=same_item_count,
                max_allowed=self.MAX_SAME_ITEM_COUNT,
            )

        # 2. Check same item value concentration
        same_item_value = sum(
            item.get("buy_price", 0) for item in inventory
            if item.get("hash_name", "") == item_title
        )
        same_item_value += buy_price
        same_item_pct = same_item_value / total_value

        if same_item_pct > self.MAX_SAME_ITEM_PCT:
            return ConcentrationCheck(
                allowed=False,
                reason=f"Same item concentration {same_item_pct:.0%} "
                       f"> {self.MAX_SAME_ITEM_PCT:.0%}",
                current_concentration=same_item_pct,
                max_allowed=self.MAX_SAME_ITEM_PCT,
            )

        # 3. Check collection concentration
        collection = self._extract_collection(item_title)
        if collection:
            collection_value = sum(
                item.get("buy_price", 0) for item in inventory
                if self._extract_collection(item.get("hash_name", "")) == collection
            )
            collection_value += buy_price
            collection_pct = collection_value / total_value

            if collection_pct > self.MAX_SAME_COLLECTION_PCT:
                return ConcentrationCheck(
                    allowed=False,
                    reason=f"Collection '{collection}' concentration "
                           f"{collection_pct:.0%} > {self.MAX_SAME_COLLECTION_PCT:.0%}",
                    current_concentration=collection_pct,
                    max_allowed=self.MAX_SAME_COLLECTION_PCT,
                    collection=collection,
                )

        # 4. Check category concentration
        category = self._classify_category(item_title)
        if category:
            category_value = sum(
                item.get("buy_price", 0) for item in inventory
                if self._classify_category(item.get("hash_name", "")) == category
            )
            category_value += buy_price
            category_pct = category_value / total_value

            if category_pct > self.MAX_SAME_CATEGORY_PCT:
                return ConcentrationCheck(
                    allowed=False,
                    reason=f"Category '{category}' concentration "
                           f"{category_pct:.0%} > {self.MAX_SAME_CATEGORY_PCT:.0%}",
                    current_concentration=category_pct,
                    max_allowed=self.MAX_SAME_CATEGORY_PCT,
                    category=category,
                )

        return ConcentrationCheck(allowed=True)

    def get_exposure_report(self) -> dict[str, Any]:
        """Get current portfolio exposure breakdown."""
        inventory = self._get_inventory()
        if not inventory:
            return {"total_items": 0, "total_value": 0.0}

        total_value = sum(item.get("buy_price", 0) for item in inventory)

        # Group by collection
        collections: dict[str, CollectionExposure] = {}
        categories: dict[str, CollectionExposure] = {}

        for item in inventory:
            name = item.get("hash_name", "unknown")
            price = item.get("buy_price", 0)

            # Collection
            coll = self._extract_collection(name)
            if coll:
                if coll not in collections:
                    collections[coll] = CollectionExposure(name=coll)
                collections[coll].item_count += 1
                collections[coll].total_value_usd += price
                collections[coll].items.append(name)

            # Category
            cat = self._classify_category(name)
            if cat:
                if cat not in categories:
                    categories[cat] = CollectionExposure(name=cat)
                categories[cat].item_count += 1
                categories[cat].total_value_usd += price
                categories[cat].items.append(name)

        # Calculate percentages
        for exp in collections.values():
            exp.pct_of_portfolio = exp.total_value_usd / total_value if total_value > 0 else 0
        for exp in categories.values():
            exp.pct_of_portfolio = exp.total_value_usd / total_value if total_value > 0 else 0

        return {
            "total_items": len(inventory),
            "total_value": round(total_value, 2),
            "collections": {
                k: {"count": v.item_count, "value": round(v.total_value_usd, 2),
                    "pct": round(v.pct_of_portfolio, 3)}
                for k, v in sorted(collections.items(),
                                   key=lambda x: x[1].total_value_usd, reverse=True)
            },
            "categories": {
                k: {"count": v.item_count, "value": round(v.total_value_usd, 2),
                    "pct": round(v.pct_of_portfolio, 3)}
                for k, v in sorted(categories.items(),
                                   key=lambda x: x[1].total_value_usd, reverse=True)
            },
        }

    def _get_inventory(self) -> list[dict[str, Any]]:
        """Get current virtual inventory."""
        try:
            idle = self.price_db.get_virtual_inventory(status="idle", only_unlocked=False)
            selling = self.price_db.get_virtual_inventory(status="selling")
            listed = self.price_db.get_virtual_inventory(status="listed")
            all_items = idle + selling + listed
            return [dict(row) for row in all_items]
        except Exception as e:
            logger.error(f"[ConcentrationRisk] Failed to get inventory: {e}")
            return []

    def _extract_collection(self, title: str) -> str:
        """Extract weapon type from item title for concentration tracking.

        Note: DMarket titles follow "Weapon | Skin (Wear)" format.
        The weapon type (e.g., "AK-47", "Karambit") is used as a proxy
        for collection grouping since true collection names aren't in titles.

        Examples:
            "AK-47 | Redline (Field-Tested)" -> "AK-47"
            "Karambit | Doppler (Factory New)" -> "Karambit"
            "Operation Bravo Case" -> "Operation Bravo Case"
        """
        if " | " in title:
            return title.split(" | ")[0].strip()
        # For cases, capsules, etc. — use full title
        return title.strip()

    def _classify_category(self, title: str) -> str:
        """Classify item into category."""
        title_lower = title.lower()
        for category, keywords in self.CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    return category
        return "other"

    def get_state(self) -> dict[str, Any]:
        """Get current state for diagnostics."""
        return {
            "max_same_item_pct": self.MAX_SAME_ITEM_PCT,
            "max_same_collection_pct": self.MAX_SAME_COLLECTION_PCT,
            "max_same_category_pct": self.MAX_SAME_CATEGORY_PCT,
            "max_same_item_count": self.MAX_SAME_ITEM_COUNT,
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for ConcentrationRiskManager."""
    from unittest.mock import MagicMock

    # Mock price_db with some inventory
    mock_db = MagicMock()
    mock_db.get_virtual_inventory = MagicMock(side_effect=[
        # idle
        [
            {"hash_name": "AK-47 | Redline", "buy_price": 15.0, "status": "idle"},
            {"hash_name": "AK-47 | Asiimov", "buy_price": 20.0, "status": "idle"},
            {"hash_name": "AWP | Dragon Lore", "buy_price": 50.0, "status": "idle"},
        ],
        # selling
        [],
        # listed
        [],
    ])

    crm = ConcentrationRiskManager(mock_db)

    # Test: buying another AK-47 should be blocked (too many same category)
    check = crm.check_concentration("AK-47 | Vulcan", 10.0, 100.0)
    print(f"[ConcentrationRisk] AK-47 check: allowed={check.allowed}, reason={check.reason}")

    # Test: buying a knife should be allowed (different category)
    check2 = crm.check_concentration("Karambit | Doppler", 10.0, 100.0)
    print(f"[ConcentrationRisk] Karambit check: allowed={check2.allowed}")

    # Test: exposure report
    report = crm.get_exposure_report()
    print(f"[ConcentrationRisk] Report: {report['total_items']} items, "
          f"${report['total_value']:.2f} total")

    # Test: same item count limit
    mock_db.get_virtual_inventory = MagicMock(side_effect=[
        [
            {"hash_name": "AK-47 | Redline", "buy_price": 15.0, "status": "idle"},
            {"hash_name": "AK-47 | Redline", "buy_price": 15.0, "status": "idle"},
            {"hash_name": "AK-47 | Redline", "buy_price": 15.0, "status": "idle"},
        ],
        [],
        [],
    ])
    crm2 = ConcentrationRiskManager(mock_db)
    check3 = crm2.check_concentration("AK-47 | Redline", 15.0, 100.0)
    print(f"[ConcentrationRisk] 3x same item: allowed={check3.allowed}, reason={check3.reason}")
    assert check3.allowed is False

    print("[ConcentrationRisk] Self-check PASSED")


if __name__ == "__main__":
    _demo()
