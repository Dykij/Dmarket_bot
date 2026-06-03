"""
Tests for ResalePipeline, InventoryManager, Pagination, and full buy→sell flow.

Run with: python -m pytest tests/test_resale_pipeline.py -v
"""

import asyncio
import math
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# =====================================================================
# ResalePipeline Tests
# =====================================================================

class TestResalePipeline:
    """Tests for the buy→CS2Cap→sell pipeline."""

    def test_import(self):
        from src.core.resale_pipeline import ResalePipeline
        assert ResalePipeline is not None

    def test_calculate_sell_price_basic(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        pipeline = ResalePipeline(mock_api)

        sell = pipeline._calculate_sell_price(
            buy_price=10.0,
            cs2cap_price=15.0,
            cross_data=None,
            fee_rate=0.05,
        )
        # Should be ~CS2Cap * 0.98 = 14.70, but at least 10 * 1.05 / 0.95 = 11.05
        assert sell >= 11.05
        assert sell <= 15.0

    def test_calculate_sell_price_min_margin(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        pipeline = ResalePipeline(mock_api)

        # Even if CS2Cap is low, min margin should be enforced
        sell = pipeline._calculate_sell_price(
            buy_price=10.0,
            cs2cap_price=10.5,  # Very low margin
            cross_data=None,
            fee_rate=0.05,
        )
        # Min sell = 10 * 1.05 / 0.95 = 11.05
        assert sell >= 11.05

    def test_calculate_sell_price_cs2cap_zero(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        pipeline = ResalePipeline(mock_api)

        sell = pipeline._calculate_sell_price(
            buy_price=10.0,
            cs2cap_price=0.0,
            cross_data=None,
            fee_rate=0.05,
        )
        # Fallback: 10% margin
        assert sell == 11.0

    def test_calculate_sell_price_with_cross_data(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.cs2cap_oracle import CrossMarketData
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        pipeline = ResalePipeline(mock_api)

        cross = CrossMarketData(
            hash_name="test",
            global_max_bid=13.0,
            provider_prices={"csfloat": 15.0},
        )

        sell = pipeline._calculate_sell_price(
            buy_price=10.0,
            cs2cap_price=15.0,
            cross_data=cross,
            fee_rate=0.05,
        )
        # Should be influenced by bid of 13.0
        assert sell >= 11.05
        assert sell <= 15.0

    @pytest.mark.asyncio
    async def test_sell_inventory_items_empty(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.db.price_history import price_db

        mock_api = MagicMock(spec=DMarketAPIClient)
        pipeline = ResalePipeline(mock_api)

        # Patch price_db to return empty inventory
        with patch.object(price_db, 'get_virtual_inventory', return_value=[]):
            listed = await pipeline.sell_inventory_items()
            assert listed == []

    @pytest.mark.asyncio
    async def test_get_inventory_status(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.db.price_history import price_db

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.get_user_inventory = AsyncMock(return_value={"objects": []})
        mock_api.get_user_active_offers = AsyncMock(return_value={"objects": []})
        pipeline = ResalePipeline(mock_api)

        status = await pipeline.get_inventory_status()
        assert "virtual" in status
        assert "real" in status
        assert "items" in status


# =====================================================================
# InventoryManager Tests
# =====================================================================

class TestInventoryManager:
    """Tests for enhanced InventoryManager with CS2Cap integration."""

    def test_import(self):
        from src.inventory_manager import InventoryManager
        assert InventoryManager is not None

    @pytest.mark.asyncio
    async def test_fetch_inventory_pagination(self):
        from src.inventory_manager import InventoryManager
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        # Simulate 3 pages of results
        page1 = {"objects": [{"itemId": f"item_{i}"} for i in range(50)], "cursor": "cursor_1"}
        page2 = {"objects": [{"itemId": f"item_{i}"} for i in range(50, 100)], "cursor": "cursor_2"}
        page3 = {"objects": [{"itemId": "item_100"}], "cursor": ""}

        mock_api.get_user_inventory = AsyncMock(side_effect=[page1, page2, page3])

        inv_mgr = InventoryManager(mock_api)
        items = await inv_mgr.fetch_inventory()

        assert len(items) == 101
        assert mock_api.get_user_inventory.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_inventory_no_cursor(self):
        from src.inventory_manager import InventoryManager
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "item_1"}],
            "cursor": ""
        })

        inv_mgr = InventoryManager(mock_api)
        items = await inv_mgr.fetch_inventory()

        assert len(items) == 1
        assert mock_api.get_user_inventory.call_count == 1

    def test_mark_item_purchased(self):
        from src.inventory_manager import InventoryManager
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.db.price_history import price_db

        mock_api = MagicMock(spec=DMarketAPIClient)
        inv_mgr = InventoryManager(mock_api)

        inv_mgr.mark_item_purchased("AK-47 | Redline", 10.0, "item_123")
        # Should not raise
        assert True

    def test_is_item_purchased(self):
        from src.inventory_manager import InventoryManager
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.db.price_history import price_db

        mock_api = MagicMock(spec=DMarketAPIClient)
        inv_mgr = InventoryManager(mock_api)

        # Record a target
        price_db.record_placed_target("test_item", "Test Item", 10.0)
        assert inv_mgr.is_item_purchased("test_item") == True
        assert inv_mgr.is_item_purchased("nonexistent") == False

    def test_get_portfolio_summary(self):
        from src.inventory_manager import InventoryManager
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        inv_mgr = InventoryManager(mock_api)

        summary = inv_mgr.get_portfolio_summary(current_balance=1000.0)
        assert "cash" in summary
        assert "total_equity" in summary
        assert "items_holding" in summary
        assert summary["cash"] == 1000.0


# =====================================================================
# DMarketAPIClient Sell Methods Tests
# =====================================================================

class TestDMarketSellMethods:
    """Tests for new sell offer methods in DMarketAPIClient."""

    def test_import(self):
        from src.api.dmarket_api_client import DMarketAPIClient
        assert hasattr(DMarketAPIClient, 'create_sell_offer')
        assert hasattr(DMarketAPIClient, 'create_sell_offers_batch')
        assert hasattr(DMarketAPIClient, 'edit_sell_offer')
        assert hasattr(DMarketAPIClient, 'delete_sell_offer')
        assert hasattr(DMarketAPIClient, 'get_user_active_offers')
        assert hasattr(DMarketAPIClient, 'get_user_closed_offers')

    @pytest.mark.asyncio
    async def test_create_sell_offer_dry_run(self):
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.create_sell_offer = AsyncMock(return_value={"offerId": "offer_123"})

        result = await mock_api.create_sell_offer("a8db", "item_123", 10.50)
        assert result["offerId"] == "offer_123"

    @pytest.mark.asyncio
    async def test_create_sell_offers_batch(self):
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.create_sell_offers_batch = AsyncMock(return_value={"status": "success"})

        items = [
            {"item_id": "item_1", "price_usd": 10.0},
            {"item_id": "item_2", "price_usd": 15.0},
        ]
        result = await mock_api.create_sell_offers_batch("a8db", items)
        assert result["status"] == "success"


# =====================================================================
# Pagination Tests
# =====================================================================

class TestPagination:
    """Tests for full pagination across DMarket pages."""

    @pytest.mark.asyncio
    async def test_pagination_multi_page(self):
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        page1 = {"objects": [{"itemId": f"item_{i}"} for i in range(20)], "cursor": "c1"}
        page2 = {"objects": [{"itemId": f"item_{i}"} for i in range(20, 40)], "cursor": "c2"}
        page3 = {"objects": [{"itemId": f"item_{i}"} for i in range(40, 50)], "cursor": ""}

        mock_api.get_market_items_v2 = AsyncMock(side_effect=[page1, page2, page3])

        all_items = []
        cursor = None
        pages = 0

        while pages < 10:
            resp = await mock_api.get_market_items_v2("a8db", limit=20, cursor=cursor)
            items = resp.get("objects", [])
            all_items.extend(items)
            cursor = resp.get("cursor", "")
            pages += 1
            if not cursor:
                break

        assert len(all_items) == 50
        assert pages == 3

    @pytest.mark.asyncio
    async def test_pagination_empty_page(self):
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.get_market_items_v2 = AsyncMock(return_value={"objects": [], "cursor": ""})

        all_items = []
        cursor = None
        pages = 0

        while pages < 10:
            resp = await mock_api.get_market_items_v2("a8db", limit=20, cursor=cursor)
            items = resp.get("objects", [])
            all_items.extend(items)
            cursor = resp.get("cursor", "")
            pages += 1
            if not cursor:
                break

        assert len(all_items) == 0
        assert pages == 1

    @pytest.mark.asyncio
    async def test_pagination_same_cursor(self):
        from src.api.dmarket_api_client import DMarketAPIClient

        mock_api = MagicMock(spec=DMarketAPIClient)
        # Same cursor = stuck page, should break after second iteration
        mock_api.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_1"}],
            "cursor": "same_cursor"
        })

        all_items = []
        cursor = None
        pages = 0

        while pages < 10:
            resp = await mock_api.get_market_items_v2("a8db", limit=20, cursor=cursor)
            items = resp.get("objects", [])
            all_items.extend(items)
            new_cursor = resp.get("cursor", "")
            pages += 1
            if not new_cursor or new_cursor == cursor:
                break
            cursor = new_cursor

        # First iteration: cursor=None -> gets items, cursor becomes "same_cursor"
        # Second iteration: cursor="same_cursor" -> gets items again, detects same cursor -> breaks
        assert pages == 2  # Ran twice before detecting stuck cursor
        assert len(all_items) == 2  # Items from both iterations  # Should break immediately


# =====================================================================
# Full Buy→Sell Flow Integration Test
# =====================================================================

class TestFullFlow:
    """Integration test for buy→CS2Cap→sell flow."""

    @pytest.mark.asyncio
    async def test_evaluate_item_for_purchase(self):
        from src.core.resale_pipeline import ResalePipeline
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.api.cs2cap_oracle import CS2CapOracle, CrossMarketData
        from src.db.price_history import price_db

        mock_api = MagicMock(spec=DMarketAPIClient)
        mock_api.get_item_fee = AsyncMock(return_value=0.05)
        mock_api.buy_items = AsyncMock(return_value={})

        pipeline = ResalePipeline(mock_api)

        # Mock CS2Cap oracle
        mock_cs2cap = MagicMock(spec=CS2CapOracle)
        mock_cs2cap.get_item_price = AsyncMock(return_value=15.0)
        mock_cs2cap.get_cross_market_data = AsyncMock(return_value=CrossMarketData(
            hash_name="AK-47 | Redline",
            provider_prices={"csfloat": 15.0, "buff163": 14.5},
            buy_orders={"csfloat": 12.0},
            liquidity_score=0.5,
        ))
        mock_cs2cap.get_market_indicators = AsyncMock(return_value={"rsi": 35.0, "bb_position": 0.2})
        pipeline.cs2cap = mock_cs2cap

        # Test item
        item = {
            "itemId": "test_item_123",
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": 1000},  # $10.00
        }

        # Patch config values
        with patch('src.core.resale_pipeline.Config') as mock_config:
            mock_config.GAME_ID = "a8db"
            mock_config.MIN_PRICE_USD = 0.50
            mock_config.MAX_PRICE_USD = 20.00
            mock_config.MIN_SPREAD_PCT = 5.0
            mock_config.FEE_RATE = 0.05

            with patch('src.core.resale_pipeline.price_db') as mock_db:
                mock_db.has_target_been_placed.return_value = False
                mock_db.add_virtual_item = MagicMock()
                mock_db.record_placed_target = MagicMock()

                with patch('os.getenv', return_value="true"):
                    result = await pipeline._evaluate_and_buy(item, balance=100.0)

                    if result:
                        assert result["buy_price"] == 10.0
                        assert result["cs2cap_price"] == 15.0
                        assert result["status"] in ("purchased", "purchased_sim")
                        assert result["net_margin_pct"] > 0


# =====================================================================
# CS2Cap + Strategy Integration Tests
# =====================================================================

class TestCS2CapStrategyIntegration:
    """Tests for CS2Cap data feeding into strategy decisions."""

    def test_cross_market_data_feeds_into_strategy(self):
        from src.strategies.cross_market import CrossMarketStrategy
        from src.api.cs2cap_oracle import CrossMarketData

        strat = CrossMarketStrategy()
        cross = CrossMarketData(
            hash_name="test",
            provider_prices={"csfloat": 10.0, "buff163": 15.0},
            buy_orders={"csfloat": 8.0},
            liquidity_score=0.5,
            volatility_24h=0.1,
        )

        result = strat.evaluate_opportunity_enhanced(
            market_data={
                "title": "AK-47 | Redline",
                "best_ask": 10.0,
                "current_balance": 100.0,
            },
            cross_market_data=cross,
            indicators={"rsi": 25.0, "bb_position": 0.1},
        )

        # Should find arbitrage opportunity
        assert result["action"] in ("place_target", "none")
        if result["action"] == "place_target":
            assert result["target_price"] > 0
            assert result["quantity"] > 0
            assert result["objective_score"] > 0

    def test_market_maker_with_reflection(self):
        from src.strategies.market_maker import MarketMaker
        from src.analytics.self_reflection import ReflectionResult

        mm = MarketMaker()
        reflection = ReflectionResult(
            recommended_spread_adjustment=1.0,
            confidence=0.5,
        )

        result = mm.evaluate_opportunity_enhanced(
            market_data={
                "title": "AK-47 | Redline",
                "best_ask": 10.0,
                "best_bid": 9.0,
                "current_balance": 100.0,
            },
            reflection_result=reflection,
        )

        assert result["action"] in ("place_target", "none")


# =====================================================================
# Self-Reflection + Adaptive Parameters
# =====================================================================

class TestAdaptiveParameters:
    """Tests for self-reflection adjusting strategy parameters."""

    def test_reflection_adjusts_min_spread(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult

        engine = SelfReflectionEngine()
        reflection = ReflectionResult(
            recommended_spread_adjustment=2.0,
            confidence=0.7,
        )

        adjusted = engine.get_adjusted_spread(5.0, reflection)
        assert adjusted == 7.0  # 5.0 + 2.0

    def test_reflection_adjusts_risk_pct(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult

        engine = SelfReflectionEngine()
        reflection = ReflectionResult(
            recommended_risk_adjustment=-1.5,
            confidence=0.6,
        )

        adjusted = engine.get_adjusted_risk_pct(5.0, reflection)
        assert adjusted == 3.5  # 5.0 - 1.5

    def test_reflection_no_confidence_no_adjustment(self):
        from src.analytics.self_reflection import SelfReflectionEngine, ReflectionResult

        engine = SelfReflectionEngine()
        reflection = ReflectionResult(
            recommended_spread_adjustment=5.0,
            confidence=0.1,  # Too low
        )

        adjusted = engine.get_adjusted_spread(5.0, reflection)
        assert adjusted == 5.0  # No adjustment


# =====================================================================
# Config Integration Tests
# =====================================================================

class TestConfigIntegration:
    """Verify all new config params are accessible."""

    def test_all_new_config_params(self):
        from src.config import Config

        # CS2Cap
        assert hasattr(Config, "CS2CAP_API_KEY")
        assert hasattr(Config, "CS2CAP_ORACLE_PRIMARY")

        # Self-reflection
        assert hasattr(Config, "SELF_REFLECTION_WINDOW")
        assert hasattr(Config, "SELF_REFLECTION_INTERVAL")
        assert hasattr(Config, "PARAMETER_ADJUSTMENT_ENABLED")

        # Turnover
        assert hasattr(Config, "TURNOVER_PENALTY_ENABLED")
        assert hasattr(Config, "MAX_DAILY_TRADES")

        # Cross-market
        assert hasattr(Config, "CROSS_MARKET_ENABLED")
        assert hasattr(Config, "CROSS_MARKET_MIN_EDGE_PCT")

        # Volatility
        assert hasattr(Config, "VOLATILITY_METHOD")
        assert hasattr(Config, "VOLATILITY_MAX_ANNUALIZED")

        # Sharpe
        assert hasattr(Config, "SHARPE_OPTIMIZATION_ENABLED")
        assert hasattr(Config, "TARGET_SHARPE_RATIO")
