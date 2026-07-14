"""Unit tests for refactored modules.

Tests for:
- ArbitrageScanner (scan_level, scan_all_levels, find_best_opportunities)
- TargetManager (create_target, get_user_targets, delete_target)
- WhitelistChecker (is_whitelisted, priority_boost)
- ItemBlacklistFilter (is_blocked, is_blacklisted)
- FilterFactory (get_filter)
- ExtendedShutdownHandler (async save_state)
- DMarketAPI (retry logic, error handling)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


# =====================================================================
# ArbitrageScanner
# =====================================================================


class TestArbitrageScanner:
    """Tests for ArbitrageScanner."""

    def _make_scanner(self, market_items: list | None = None):
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        api = AsyncMock()
        items = market_items or [
            {
                "itemId": "item_1",
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1000"},
                "suggestedPrice": {"USD": "1200"},
            },
        ]
        api.get_market_items = AsyncMock(return_value={"objects": items, "cursor": ""})
        return ArbitrageScanner(api_client=api), api

    @pytest.mark.asyncio()
    async def test_scan_level_returns_list(self):
        scanner, _ = self._make_scanner()
        result = await scanner.scan_level(game="csgo", level="standard")
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_scan_level_finds_profitable_items(self):
        scanner, _ = self._make_scanner()
        result = await scanner.scan_level(game="csgo", level="standard")
        assert len(result) > 0
        assert result[0]["profit_percent"] > 0

    @pytest.mark.asyncio()
    async def test_scan_level_filters_unprofitable(self):
        items = [
            {
                "itemId": "item_1",
                "title": "Expensive Item",
                "price": {"USD": "1200"},
                "suggestedPrice": {"USD": "1000"},  # Loss
            },
        ]
        scanner, _ = self._make_scanner(market_items=items)
        result = await scanner.scan_level(game="csgo", level="standard")
        assert len(result) == 0

    @pytest.mark.asyncio()
    async def test_scan_level_handles_api_error(self):
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        api = AsyncMock()
        api.get_market_items = AsyncMock(side_effect=Exception("API down"))
        scanner = ArbitrageScanner(api_client=api)
        result = await scanner.scan_level(game="csgo", level="standard")
        assert result == []

    @pytest.mark.asyncio()
    async def test_scan_level_no_api_client(self):
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=None)
        result = await scanner.scan_level(game="csgo", level="standard")
        assert result == []

    @pytest.mark.asyncio()
    async def test_scan_all_levels_returns_dict(self):
        scanner, _ = self._make_scanner()
        result = await scanner.scan_all_levels(game="csgo")
        assert isinstance(result, dict)
        assert "boost" in result
        assert "standard" in result
        assert "medium" in result

    @pytest.mark.asyncio()
    async def test_find_best_opportunities_sorted(self):
        items = [
            {
                "itemId": "low",
                "title": "Low Profit",
                "price": {"USD": "1000"},
                "suggestedPrice": {"USD": "1100"},  # 10%
            },
            {
                "itemId": "high",
                "title": "High Profit",
                "price": {"USD": "1000"},
                "suggestedPrice": {"USD": "1500"},  # 50%
            },
        ]
        scanner, _ = self._make_scanner(market_items=items)
        result = await scanner.find_best_opportunities(game="csgo", top_n=10)
        assert len(result) > 0
        # Should be sorted by profit descending
        if len(result) > 1:
            assert result[0]["profit_percent"] >= result[1]["profit_percent"]

    @pytest.mark.asyncio()
    async def test_scan_level_result_structure(self):
        scanner, _ = self._make_scanner()
        result = await scanner.scan_level(game="csgo", level="boost")
        assert len(result) > 0
        opp = result[0]
        assert "item" in opp
        assert "item_id" in opp
        assert "title" in opp
        assert "buy_price" in opp
        assert "suggested_price" in opp
        assert "profit_percent" in opp
        assert "level" in opp
        assert "game" in opp


# =====================================================================
# TargetManager
# =====================================================================


class TestTargetManager:
    """Tests for TargetManager."""

    @pytest.mark.asyncio()
    async def test_create_target_success(self):
        from src.dmarket.targets import TargetManager

        api = AsyncMock()
        api.create_target = AsyncMock(return_value={
            "Result": [{"TargetID": "t1", "Status": "Created"}],
        })
        manager = TargetManager(api_client=api)
        result = await manager.create_target(title="AK-47", price=10.0)
        assert "targetId" in result
        assert result["targetId"] == "t1"

    @pytest.mark.asyncio()
    async def test_create_target_validates_price(self):
        from src.dmarket.targets import TargetManager

        manager = TargetManager(api_client=AsyncMock())
        with pytest.raises(ValueError, match="Price must be"):
            await manager.create_target(title="AK-47", price=0.0)

    @pytest.mark.asyncio()
    async def test_create_target_validates_empty_title(self):
        from src.dmarket.targets import TargetManager

        manager = TargetManager(api_client=AsyncMock())
        with pytest.raises(ValueError, match="Title cannot be empty"):
            await manager.create_target(title="", price=10.0)

    @pytest.mark.asyncio()
    async def test_delete_target_success(self):
        from src.dmarket.targets import TargetManager

        api = AsyncMock()
        api.delete_target = AsyncMock(return_value={"success": True})
        manager = TargetManager(api_client=api)
        result = await manager.delete_target("t1")
        assert result is True

    @pytest.mark.asyncio()
    async def test_delete_target_failure(self):
        from src.dmarket.targets import TargetManager

        api = AsyncMock()
        api.delete_target = AsyncMock(side_effect=Exception("Not found"))
        manager = TargetManager(api_client=api)
        result = await manager.delete_target("nonexistent")
        assert result is False

    @pytest.mark.asyncio()
    async def test_get_user_targets_returns_list(self):
        from src.dmarket.targets import TargetManager

        api = AsyncMock()
        api.get_user_targets = AsyncMock(return_value={
            "Items": [{"targetId": "t1"}],
        })
        manager = TargetManager(api_client=api)
        result = await manager.get_user_targets(game="csgo")
        assert isinstance(result, list)
        assert len(result) == 1


# =====================================================================
# WhitelistChecker
# =====================================================================


class TestWhitelistChecker:
    """Tests for WhitelistChecker."""

    def test_empty_whitelist_allows_all(self):
        from src.dmarket.whitelist_config import WhitelistChecker

        checker = WhitelistChecker()
        assert checker.is_whitelisted("Any Item") is True

    def test_whitelist_blocks_non_members(self):
        from src.dmarket.whitelist_config import WhitelistChecker

        checker = WhitelistChecker(whitelist=["AK-47 | Redline"])
        assert checker.is_whitelisted("AK-47 | Redline") is True
        assert checker.is_whitelisted("AWP | Dragon Lore") is False

    def test_whitelist_accepts_dict(self):
        from src.dmarket.whitelist_config import WhitelistChecker

        checker = WhitelistChecker(whitelist=["AK-47 | Redline"])
        assert checker.is_whitelisted({"title": "AK-47 | Redline"}) is True
        assert checker.is_whitelisted({"title": "Other"}) is False

    def test_priority_boost_attributes(self):
        from src.dmarket.whitelist_config import WhitelistChecker

        checker = WhitelistChecker(
            enable_priority_boost=True,
            profit_boost_percent=2.0,
        )
        assert checker.enable_priority_boost is True
        assert checker.profit_boost_percent == 2.0

    def test_filter_items(self):
        from src.dmarket.whitelist_config import WhitelistChecker

        checker = WhitelistChecker(whitelist=["AK-47 | Redline"])
        items = [
            {"title": "AK-47 | Redline"},
            {"title": "AWP | Dragon Lore"},
        ]
        result = checker.filter_items(items)
        assert len(result) == 1
        assert result[0]["title"] == "AK-47 | Redline"


# =====================================================================
# ItemBlacklistFilter
# =====================================================================


class TestItemBlacklistFilter:
    """Tests for ItemBlacklistFilter."""

    def test_is_blocked(self):
        from src.dmarket.blacklist_filters import ItemBlacklistFilter

        bl = ItemBlacklistFilter(blacklist=["sticker", "souvenir"])
        assert bl.is_blocked("AK-47 | Sticker Bomb") is True
        assert bl.is_blocked("AWP | Dragon Lore") is False

    def test_is_blacklisted_alias(self):
        from src.dmarket.blacklist_filters import ItemBlacklistFilter

        bl = ItemBlacklistFilter(blacklist=["katowice"])
        assert bl.is_blacklisted("Item Katowice 2014") is True
        assert bl.is_blacklisted("Normal Item") is False

    def test_is_blacklisted_with_dict(self):
        from src.dmarket.blacklist_filters import ItemBlacklistFilter

        bl = ItemBlacklistFilter(blacklist=["sticker"])
        assert bl.is_blacklisted({"title": "AK Sticker"}) is True
        assert bl.is_blacklisted({"title": "Normal Item"}) is False

    def test_empty_blacklist_allows_all(self):
        from src.dmarket.blacklist_filters import ItemBlacklistFilter

        bl = ItemBlacklistFilter()
        assert bl.is_blocked("Any Item") is False

    def test_filter_items(self):
        from src.dmarket.blacklist_filters import ItemBlacklistFilter

        bl = ItemBlacklistFilter(blacklist=["souvenir"])
        items = [
            {"title": "Souvenir AK-47"},
            {"title": "Normal AK-47"},
        ]
        result = bl.filter_items(items)
        assert len(result) == 1
        assert result[0]["title"] == "Normal AK-47"


# =====================================================================
# FilterFactory
# =====================================================================


class TestFilterFactory:
    """Tests for FilterFactory."""

    def test_get_filter_returns_game_filter(self):
        from src.dmarket.filters.game_filters import FilterFactory

        f = FilterFactory.get_filter("csgo")
        assert f.game_name == "csgo"

    def test_get_filter_unknown_game(self):
        from src.dmarket.filters.game_filters import FilterFactory

        f = FilterFactory.get_filter("unknown_game")
        assert f.game_name == "unknown_game"

    def test_apply_filters_to_items(self):
        from src.dmarket.filters.game_filters import apply_filters_to_items

        items = [
            {"price": {"USD": "100"}},  # $1.00
            {"price": {"USD": "5000"}},  # $50.00
        ]
        result = apply_filters_to_items(items, "csgo", {"min_price": 5.0, "max_price": 100.0})
        assert len(result) == 1
        assert result[0]["price"]["USD"] == "5000"


# =====================================================================
# ExtendedShutdownHandler
# =====================================================================


class TestExtendedShutdownHandler:
    """Tests for ExtendedShutdownHandler."""

    @pytest.mark.asyncio()
    async def test_save_state_with_sync_provider(self, tmp_path):
        from src.utils.extended_shutdown_handler import ExtendedShutdownHandler

        handler = ExtendedShutdownHandler(state_file=tmp_path / "state.json")
        handler.register_targets_provider(lambda: [{"id": "t1"}])
        result = await handler.save_state()
        assert result is True

    @pytest.mark.asyncio()
    async def test_save_state_with_async_provider(self, tmp_path):
        from src.utils.extended_shutdown_handler import ExtendedShutdownHandler

        handler = ExtendedShutdownHandler(state_file=tmp_path / "state.json")

        async def get_targets():
            return [{"id": "t1"}, {"id": "t2"}]

        handler.register_targets_provider(get_targets)
        result = await handler.save_state()
        assert result is True

    @pytest.mark.asyncio()
    async def test_load_state(self, tmp_path):
        import json

        from src.utils.extended_shutdown_handler import ExtendedShutdownHandler

        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"targets": [{"id": "t1"}]}))

        handler = ExtendedShutdownHandler(state_file=state_file)
        state = await handler.load_state()
        assert state is not None
        assert len(state["targets"]) == 1

    @pytest.mark.asyncio()
    async def test_load_state_missing_file(self, tmp_path):
        from src.utils.extended_shutdown_handler import ExtendedShutdownHandler

        handler = ExtendedShutdownHandler(state_file=tmp_path / "nonexistent.json")
        state = await handler.load_state()
        assert state is None


# =====================================================================
# NetworkError exception
# =====================================================================


class TestNetworkError:
    """Tests for NetworkError exception."""

    def test_network_error_exists(self):
        from src.utils.exceptions import NetworkError
        assert issubclass(NetworkError, Exception)

    def test_network_error_message(self):
        from src.utils.exceptions import NetworkError
        err = NetworkError("Connection refused")
        assert str(err) == "Connection refused"
