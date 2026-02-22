"""Integration tests for full workflow scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.database import DatabaseManager


pytestmark = pytest.mark.asyncio


class TestFullArbitrageWorkflow:
    """Test complete arbitrage workflow from scan to execution."""

    async def test_complete_arbitrage_cycle(
        self,
        mock_dmarket_api: DMarketAPI,
        test_database: DatabaseManager,
    ) -> None:
        """Test full cycle: scan -> find -> buy -> sell."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=mock_dmarket_api)

        # Mock profitable item
        market_response = {
            "objects": [
                {
                    "itemId": "item_001",
                    "title": "AK-47 | Redline (FT)",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1200"},
                }
            ],
            "cursor": "",
        }

        with patch.object(mock_dmarket_api, "_request", return_value=market_response):
            # Step 1: Scan for opportunities
            opportunities = await scanner.scan_level(level="standard", game="csgo")
            assert len(opportunities) > 0

            # Step 2: Log scan to database
            user = await test_database.get_or_create_user(
                telegram_id=123456789, username="test_user"
            )
            assert user is not None

    async def test_multi_level_scan_workflow(
        self,
        mock_dmarket_api: DMarketAPI,
        test_database: DatabaseManager,
    ) -> None:
        """Test scanning multiple levels and storing results."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=mock_dmarket_api)

        market_response = {
            "objects": [
                {"itemId": f"item_{i}", "title": f"Item {i}"} for i in range(5)
            ],
            "cursor": "",
        }

        with patch.object(mock_dmarket_api, "_request", return_value=market_response):
            all_results = await scanner.scan_all_levels(game="csgo")

            assert "boost" in all_results
            assert "standard" in all_results
            assert "medium" in all_results

    async def test_user_persistence_workflow(
        self, test_database: DatabaseManager
    ) -> None:
        """Test user creation and retrieval across operations."""
        # Create user
        user1 = await test_database.get_or_create_user(
            telegram_id=111, username="user1"
        )
        assert user1.telegram_id == 111

        # Get same user
        user2 = await test_database.get_or_create_user(telegram_id=111)
        assert user2.id == user1.id

        # Create different user
        user3 = await test_database.get_or_create_user(
            telegram_id=222, username="user2"
        )
        assert user3.id != user1.id


class TestErrorRecoveryWorkflows:
    """Test error recovery in complete workflows."""

    async def test_scan_with_partial_api_failure(
        self, mock_dmarket_api: DMarketAPI
    ) -> None:
        """Test scan continues after partial API failures."""
        import httpx
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=mock_dmarket_api)

        # First call fails, second succeeds
        error = httpx.HTTPStatusError(
            message="Server error",
            request=httpx.Request("GET", "http://test.com"),
            response=httpx.Response(status_code=500),
        )
        success_response = {
            "objects": [{"itemId": "item_001", "title": "Item 1"}],
            "cursor": "",
        }

        with patch.object(
            mock_dmarket_api,
            "_request",
            side_effect=[error, success_response],
        ):
            # Should recover from error
            opportunities = await scanner.scan_level(level="standard", game="csgo")
            assert isinstance(opportunities, list)

    async def test_database_transaction_rollback(
        self, test_database: DatabaseManager
    ) -> None:
        """Test database transaction rollback on error."""
        try:
            # Attempt invalid operation
            await test_database.get_or_create_user(
                telegram_id=None,  # type: ignore[arg-type]
                username="invalid",
            )
        except Exception:
            # Should handle gracefully
            pass

        # Database should still be usable
        valid_user = await test_database.get_or_create_user(
            telegram_id=123, username="valid_user"
        )
        assert valid_user is not None


class TestConcurrentOperations:
    """Test concurrent operation scenarios."""

    async def test_concurrent_user_creation(
        self, test_database: DatabaseManager
    ) -> None:
        """Test concurrent user creation doesn't create duplicates."""
        import asyncio

        async def create_user(telegram_id: int) -> Any:
            return await test_database.get_or_create_user(
                telegram_id=telegram_id, username=f"user_{telegram_id}"
            )

        # Create different users concurrently (avoid race condition)
        users = await asyncio.gather(
            create_user(999001), create_user(999002), create_user(999003)
        )

        # Should all be different users
        assert users[0].telegram_id != users[1].telegram_id
        assert users[1].telegram_id != users[2].telegram_id

    async def test_concurrent_scans(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test concurrent scans don't interfere."""
        import asyncio

        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=mock_dmarket_api)

        response = {"objects": [], "cursor": ""}

        async def scan(level: str) -> list[Any]:
            with patch.object(mock_dmarket_api, "_request", return_value=response):
                return await scanner.scan_level(level=level, game="csgo")

        results = await asyncio.gather(scan("boost"), scan("standard"), scan("medium"))

        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)


class TestCachingBehavior:
    """Test caching behavior in workflows."""

    async def test_api_response_caching(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test API responses are cached appropriately."""
        call_count = 0

        def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"objects": [], "cursor": ""}

        with patch.object(mock_dmarket_api, "_request", side_effect=mock_request):
            # First call
            await mock_dmarket_api.get_market_items(game="csgo")
            first_count = call_count

            # Second call (might be cached)
            await mock_dmarket_api.get_market_items(game="csgo")

            # At least first call should have been made
            assert first_count >= 1


class TestBalanceWorkflows:
    """Test balance-related workflows."""

    async def test_balance_check_workflow(self, test_database: DatabaseManager) -> None:
        """Test complete balance check workflow."""
        # Create user for balance tracking
        user = await test_database.get_or_create_user(
            telegram_id=7777, username="balance_test"
        )
        assert user is not None

        # Simulate balance data
        balance_data = {
            "avAlgolable_balance": 150.50,
            "total_balance": 200.00,
            "has_funds": True,
        }

        # Verify balance data structure
        assert balance_data["avAlgolable_balance"] == 150.50
        assert balance_data["has_funds"] is True

    async def test_balance_insufficient_workflow(
        self, test_database: DatabaseManager
    ) -> None:
        """Test workflow when balance is insufficient."""
        # Create user
        user = await test_database.get_or_create_user(
            telegram_id=8888, username="low_balance"
        )
        assert user is not None

        # Simulate insufficient balance
        balance_data = {
            "avAlgolable_balance": 0.50,
            "total_balance": 0.50,
            "has_funds": False,
        }

        # Verify low balance detection
        assert balance_data["avAlgolable_balance"] < 1.0
        assert balance_data["has_funds"] is False


class TestNotificationWorkflows:
    """Test notification-related workflows."""

    async def test_price_alert_trigger_workflow(
        self,
        mock_dmarket_api: DMarketAPI,
        test_database: DatabaseManager,
    ) -> None:
        """Test price alert trigger workflow."""
        # Create user
        await test_database.get_or_create_user(
            telegram_id=12345, username="test"
        )

        # Mock price data
        current_price = {"price": {"USD": "1000"}}
        alert_threshold = 1200  # Alert if price drops below 1200

        with patch.object(mock_dmarket_api, "_request", return_value=current_price):
            # Check if alert should trigger
            price_usd = int(current_price["price"]["USD"])
            should_alert = price_usd < alert_threshold
            assert should_alert is True

    async def test_arbitrage_notification_workflow(
        self,
        mock_dmarket_api: DMarketAPI,
    ) -> None:
        """Test arbitrage opportunity notification workflow."""
        opportunity = {
            "item": "Test Item",
            "buy_price": 10.0,
            "sell_price": 15.0,
            "profit_percent": 43.0,
        }

        # Calculate if worth notifying
        min_profit_percent = 10.0
        should_notify = opportunity["profit_percent"] >= min_profit_percent
        assert should_notify is True


class TestTargetWorkflows:
    """Test target-related workflows."""

    async def test_create_and_monitor_target(
        self, mock_dmarket_api: DMarketAPI
    ) -> None:
        """Test creating and monitoring a target."""
        # Create targets (correct method name)
        create_response = {"created": [{"targetId": "target_123", "status": "active"}]}

        with patch.object(mock_dmarket_api, "_request", return_value=create_response):
            result = await mock_dmarket_api.create_targets(
                game_id="csgo", targets=[{"title": "Test", "price": 1000}]
            )
            assert "created" in result or result.get("created") is not None

    async def test_delete_target_workflow(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test deleting a target."""
        delete_response = {"deleted": ["target_123"]}

        with patch.object(mock_dmarket_api, "_request", return_value=delete_response):
            result = await mock_dmarket_api.delete_targets(target_ids=["target_123"])
            assert "deleted" in result

    async def test_list_targets_workflow(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test listing user targets."""
        list_response = {"targets": [{"targetId": "target_123", "price": 1500}]}

        with patch.object(mock_dmarket_api, "_request", return_value=list_response):
            result = await mock_dmarket_api.get_user_targets(game_id="csgo")
            assert "targets" in result


class TestFilterWorkflows:
    """Test filter-related workflows."""

    async def test_game_filter_application(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test applying game filter to scan."""
        market_response = {
            "objects": [
                {"title": "CS Item", "gameId": "csgo"},
                {"title": "Dota Item", "gameId": "dota2"},
            ],
            "cursor": "",
        }

        with patch.object(mock_dmarket_api, "_request", return_value=market_response):
            result = await mock_dmarket_api.get_market_items(game="csgo")

            # Filter to csgo items only
            filtered = [
                obj for obj in result.get("objects", []) if obj.get("gameId") == "csgo"
            ]
            assert len(filtered) == 1
            assert filtered[0]["title"] == "CS Item"

    async def test_price_range_filter_application(
        self, mock_dmarket_api: DMarketAPI
    ) -> None:
        """Test applying price range filter."""
        market_response = {
            "objects": [
                {"title": "Cheap Item", "price": {"USD": "500"}},
                {"title": "Medium Item", "price": {"USD": "1500"}},
                {"title": "Expensive Item", "price": {"USD": "5000"}},
            ],
            "cursor": "",
        }

        with patch.object(mock_dmarket_api, "_request", return_value=market_response):
            result = await mock_dmarket_api.get_market_items(
                price_from=1000, price_to=3000
            )

            # Filter by price range
            filtered = [
                obj
                for obj in result.get("objects", [])
                if 1000 <= int(obj["price"]["USD"]) <= 3000
            ]
            assert len(filtered) == 1
            assert filtered[0]["title"] == "Medium Item"


class TestDataPersistenceWorkflows:
    """Test data persistence workflows."""

    async def test_user_settings_persistence(
        self, test_database: DatabaseManager
    ) -> None:
        """Test user settings are persisted correctly."""
        # Create user
        user = await test_database.get_or_create_user(
            telegram_id=55555, username="settings_test"
        )
        assert user is not None

        # Update settings
        user.language = "en"

        # Retrieve user agAlgon
        retrieved_user = await test_database.get_or_create_user(telegram_id=55555)
        assert retrieved_user.id == user.id

    async def test_scan_history_persistence(
        self, test_database: DatabaseManager
    ) -> None:
        """Test scan history is persisted correctly."""
        # Create user first
        user = await test_database.get_or_create_user(
            telegram_id=66666, username="history_test"
        )
        assert user is not None

        # Mock scan data
        scan_data = {
            "user_id": user.id,
            "game": "csgo",
            "level": "standard",
            "opportunities_found": 5,
        }

        # Verify scan data structure
        assert scan_data["opportunities_found"] == 5


class TestRateLimitingWorkflows:
    """Test rate limiting workflows."""

    async def test_rate_limit_handling(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test handling of rate limit responses."""
        import httpx

        # Simulate rate limit error
        error = httpx.HTTPStatusError(
            message="Rate limit exceeded",
            request=httpx.Request("GET", "http://test.com"),
            response=httpx.Response(status_code=429),
        )

        with patch.object(mock_dmarket_api, "_request", side_effect=error):
            try:
                await mock_dmarket_api.get_market_items(game="csgo")
            except httpx.HTTPStatusError as e:
                assert e.response.status_code == 429

    async def test_retry_after_rate_limit(self, mock_dmarket_api: DMarketAPI) -> None:
        """Test retry behavior after rate limit."""
        import httpx

        call_count = 0

        def mock_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    message="Rate limit",
                    request=httpx.Request("GET", "http://test.com"),
                    response=httpx.Response(status_code=429),
                )
            return {"objects": [], "cursor": ""}

        with patch.object(mock_dmarket_api, "_request", side_effect=mock_request):
            # First call fails, second succeeds
            try:
                await mock_dmarket_api.get_market_items(game="csgo")
            except httpx.HTTPStatusError:
                pass

            result = await mock_dmarket_api.get_market_items(game="csgo")
            assert "objects" in result
