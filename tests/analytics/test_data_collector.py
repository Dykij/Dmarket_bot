"""
Tests for Historical Market Data Collector.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.analytics.data_collector import MarketDataCollector
from src.dmarket.dmarket_api import DMarketAPI
from src.models.market_history import MarketSnapshot
from src.utils.database import DatabaseManager


@pytest.fixture()
def mock_api_client():
    """Mock DMarket API client."""
    api = AsyncMock(spec=DMarketAPI)
    api.get_market_items = AsyncMock(
        return_value={
            "objects": [
                {
                    "itemId": "test_item_1",
                    "title": "Test Item 1",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1200"},
                    "inMarket": 5,
                },
                {
                    "itemId": "test_item_2",
                    "title": "Test Item 2",
                    "price": {"USD": "2000"},
                    "suggestedPrice": {"USD": "2500"},
                    "inMarket": 10,
                },
            ]
        }
    )
    return api


@pytest.fixture()
async def test_db():
    """Test database."""
    db = DatabaseManager("sqlite+Algoosqlite:///:memory:")
    await db.init_database()
    yield db
    await db.close()


@pytest.fixture()
def data_collector(mock_api_client, test_db):
    """Data collector instance."""
    return MarketDataCollector(
        api_client=mock_api_client,
        db_manager=test_db,
        collection_interval_minutes=1,  # Short interval for testing
        retention_days=30,
    )


class TestMarketDataCollectorInitialization:
    """Tests for collector initialization."""

    def test_collector_initializes_correctly(self, data_collector):
        """Test collector initialization."""
        assert data_collector is not None
        assert data_collector.collection_interval == 60  # 1 minute in seconds
        assert data_collector.retention_days == 30
        assert not data_collector._running

    def test_collector_custom_intervals(self, mock_api_client, test_db):
        """Test custom collection intervals."""
        collector = MarketDataCollector(
            api_client=mock_api_client,
            db_manager=test_db,
            collection_interval_minutes=30,
            retention_days=180,
        )
        assert collector.collection_interval == 1800  # 30 minutes
        assert collector.retention_days == 180


class TestDataCollection:
    """Tests for data collection functionality."""

    @pytest.mark.asyncio()
    async def test_collect_market_snapshot_success(self, data_collector, mock_api_client):
        """Test successful market snapshot collection."""
        stats = await data_collector.collect_market_snapshot()

        assert stats is not None
        assert "timestamp" in stats
        assert "games" in stats
        assert "total_items" in stats
        assert stats["total_items"] > 0

        # Verify API was called for each game
        assert mock_api_client.get_market_items.call_count == 4  # 4 games

    @pytest.mark.asyncio()
    async def test_collect_game_data_success(self, data_collector):
        """Test collecting data for a specific game."""
        game_data = await data_collector._collect_game_data("csgo")

        assert game_data is not None
        assert "items_count" in game_data
        assert "sales_count" in game_data
        assert "avg_price_cents" in game_data
        assert game_data["items_count"] == 2

    @pytest.mark.asyncio()
    async def test_collect_game_data_handles_empty_response(self, data_collector, mock_api_client):
        """Test handling empty API response."""
        mock_api_client.get_market_items.return_value = {"objects": []}

        game_data = await data_collector._collect_game_data("csgo")

        assert game_data["items_count"] == 0
        assert game_data["sales_count"] == 0
        assert game_data["avg_price_cents"] == 0

    @pytest.mark.asyncio()
    async def test_collect_game_data_handles_api_error(self, data_collector, mock_api_client):
        """Test handling API errors during collection."""
        mock_api_client.get_market_items.side_effect = Exception("API Error")

        game_data = await data_collector._collect_game_data("csgo")

        # Should return empty data on error
        assert game_data["items_count"] == 0

    @pytest.mark.asyncio()
    async def test_collect_respects_pagination(self, data_collector):
        """Test that collector handles pagination correctly."""
        # Create fresh mock for this test to avoid side_effect conflicts
        mock_api = AsyncMock(spec=DMarketAPI)
        mock_api.get_market_items.side_effect = [
            {"objects": [{"price": {"USD": "1000"}, "inMarket": 1}] * 100},
            {"objects": [{"price": {"USD": "1000"}, "inMarket": 1}] * 100},
            {"objects": [{"price": {"USD": "1000"}, "inMarket": 1}] * 50},  # Last page (< limit)
        ]

        # Temporarily replace api_client
        original_api = data_collector.api_client
        data_collector.api_client = mock_api

        game_data = await data_collector._collect_game_data("csgo")

        # Restore original
        data_collector.api_client = original_api

        assert game_data["items_count"] == 250
        # Should stop after 3rd call (50 < 100)
        assert mock_api.get_market_items.call_count == 3


class TestDatabaseStorage:
    """Tests for database storage functionality."""

    @pytest.mark.asyncio()
    async def test_store_snapshot_in_db(self, data_collector, test_db):
        """Test storing snapshot in database."""
        snapshot = {
            "timestamp": datetime.now(),
            "total_items": 100,
            "total_sales": 50,
            "games": {"csgo": {"items_count": 50}},
        }

        await data_collector._store_snapshot(snapshot)

        # Verify stored in DB
        async with test_db.async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(select(MarketSnapshot))
            db_snapshot = result.scalar_one()

            assert db_snapshot is not None
            assert db_snapshot.total_items == 100
            assert db_snapshot.total_sales == 50

    @pytest.mark.asyncio()
    async def test_cleanup_old_data(self, data_collector, test_db):
        """Test cleanup of old data."""
        # Insert old and new snapshots
        async with test_db.async_session_maker() as session:
            old_snapshot = MarketSnapshot(
                timestamp=datetime.now() - timedelta(days=200),
                total_items=10,
                total_sales=5,
                games_data={},
            )
            new_snapshot = MarketSnapshot(
                timestamp=datetime.now(),
                total_items=20,
                total_sales=10,
                games_data={},
            )
            session.add_all([old_snapshot, new_snapshot])
            await session.commit()

        # Run cleanup
        await data_collector._cleanup_old_data()

        # Verify old data deleted
        async with test_db.async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(select(MarketSnapshot))
            snapshots = result.scalars().all()

            assert len(snapshots) == 1
            assert snapshots[0].total_items == 20  # Only new snapshot remains


class TestBackgroundTask:
    """Tests for background collection task."""

    @pytest.mark.asyncio()
    async def test_start_collector(self, data_collector):
        """Test starting the collector."""
        await data_collector.start()

        assert data_collector._running
        assert data_collector._task is not None

        # Stop immediately
        await data_collector.stop()

    @pytest.mark.asyncio()
    async def test_stop_collector(self, data_collector):
        """Test stopping the collector."""
        await data_collector.start()
        await data_collector.stop()

        assert not data_collector._running

    @pytest.mark.asyncio()
    async def test_start_already_running_collector(self, data_collector):
        """Test starting already running collector."""
        await data_collector.start()

        # Try to start agAlgon
        await data_collector.start()

        assert data_collector._running

        await data_collector.stop()

    @pytest.mark.asyncio()
    async def test_collection_loop_runs(self, data_collector, mock_api_client):
        """Test that collection loop runs periodically."""
        # Use very short interval
        data_collector.collection_interval = 0.1  # 100ms

        await data_collector.start()

        # WAlgot for a few collections
        await asyncio.sleep(0.3)

        await data_collector.stop()

        # Should have collected data multiple times
        assert mock_api_client.get_market_items.call_count >= 8  # 2 collections * 4 games

    @pytest.mark.asyncio()
    async def test_collection_loop_handles_errors(self, data_collector, mock_api_client):
        """Test collection loop continues after errors."""
        mock_api_client.get_market_items.side_effect = [
            Exception("First error"),
            {"objects": [{"price": {"USD": "1000"}, "inMarket": 1}]},
        ]

        data_collector.collection_interval = 0.1

        await data_collector.start()
        await asyncio.sleep(0.3)
        await data_collector.stop()

        # Should have attempted multiple collections despite error
        assert mock_api_client.get_market_items.call_count >= 4


class TestDataExport:
    """Tests for data export functionality."""

    @pytest.mark.asyncio()
    async def test_export_to_csv(self, data_collector, test_db, tmp_path):
        """Test exporting data to CSV."""
        # Add test data
        async with test_db.async_session_maker() as session:
            snapshot = MarketSnapshot(
                timestamp=datetime.now(),
                total_items=100,
                total_sales=50,
                games_data={
                    "csgo": {"items_count": 50},
                    "dota2": {"items_count": 30},
                    "tf2": {"items_count": 15},
                    "rust": {"items_count": 5},
                },
            )
            session.add(snapshot)
            await session.commit()

        # Export to CSV
        csv_path = tmp_path / "export.csv"
        await data_collector.export_to_csv(str(csv_path))

        # Verify file created
        assert csv_path.exists()

        # Read and verify content
        import csv

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["total_items"] == "100"
            assert rows[0]["total_sales"] == "50"
            assert rows[0]["csgo_items"] == "50"

    @pytest.mark.asyncio()
    async def test_export_with_date_filter(self, data_collector, test_db, tmp_path):
        """Test exporting with date filters."""
        # Add snapshots on different dates
        async with test_db.async_session_maker() as session:
            old_snapshot = MarketSnapshot(
                timestamp=datetime.now() - timedelta(days=10),
                total_items=50,
                total_sales=25,
                games_data={},
            )
            new_snapshot = MarketSnapshot(
                timestamp=datetime.now(),
                total_items=100,
                total_sales=50,
                games_data={},
            )
            session.add_all([old_snapshot, new_snapshot])
            await session.commit()

        # Export only last 5 days
        csv_path = tmp_path / "filtered_export.csv"
        start_date = datetime.now() - timedelta(days=5)

        await data_collector.export_to_csv(str(csv_path), start_date=start_date)

        # Verify only new snapshot exported
        import csv

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["total_items"] == "100"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_collect_with_invalid_price_format(self, data_collector, mock_api_client):
        """Test handling invalid price formats."""
        mock_api_client.get_market_items.return_value = {
            "objects": [
                {"price": {"USD": "invalid"}, "inMarket": 1},
                {"price": {}, "inMarket": 1},
                {"inMarket": 1},  # Missing price
            ]
        }

        game_data = await data_collector._collect_game_data("csgo")

        # Should handle gracefully
        assert game_data["items_count"] == 3
        assert game_data["avg_price_cents"] == 0

    @pytest.mark.asyncio()
    async def test_collect_with_rate_limiting(self, data_collector, mock_api_client):
        """Test collection respects rate limiting."""
        # This is more of an integration test with rate limiter
        # For now, just verify it doesn't crash
        await data_collector.collect_market_snapshot()
        assert True

    @pytest.mark.asyncio()
    async def test_multiple_concurrent_collections(self, data_collector):
        """Test multiple concurrent collection calls."""
        # Should handle concurrent calls gracefully
        tasks = [data_collector.collect_market_snapshot() for _ in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)
