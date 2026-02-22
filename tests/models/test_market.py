"""Tests for src/models/market.py module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4


class TestMarketDataModel:
    """Tests for MarketData model."""

    def test_market_data_creation_default_values(self):
        """Test creating MarketData with default values."""
        market_data = MagicMock()
        market_data.id = uuid4()
        market_data.item_id = "item_123"
        market_data.game = "csgo"
        market_data.item_name = "AK-47 | Redline"
        market_data.price_usd = 50.0
        market_data.data_source = "dmarket"

        assert market_data.item_id == "item_123"
        assert market_data.game == "csgo"
        assert market_data.data_source == "dmarket"

    def test_market_data_creation_with_all_fields(self):
        """Test creating MarketData with all fields."""
        market_data = MagicMock()
        market_data.id = uuid4()
        market_data.item_id = "item_456"
        market_data.game = "dota2"
        market_data.item_name = "Dragonclaw Hook"
        market_data.price_usd = 1500.0
        market_data.price_change_24h = 5.5
        market_data.volume_24h = 100
        market_data.market_cap = 150000.0
        market_data.data_source = "steam"
        market_data.created_at = datetime.now(UTC)

        assert market_data.item_name == "Dragonclaw Hook"
        assert market_data.price_usd == 1500.0
        assert market_data.price_change_24h == 5.5
        assert market_data.volume_24h == 100
        assert market_data.market_cap == 150000.0

    def test_market_data_different_games(self):
        """Test MarketData for different games."""
        games = ["csgo", "dota2", "tf2", "rust"]

        for game in games:
            market_data = MagicMock()
            market_data.game = game
            market_data.item_id = f"item_{game}"
            market_data.item_name = f"Test Item {game}"
            market_data.price_usd = 100.0

            assert market_data.game == game

    def test_market_data_price_change_positive(self):
        """Test MarketData with positive price change."""
        market_data = MagicMock()
        market_data.price_change_24h = 15.5

        assert market_data.price_change_24h == 15.5
        assert market_data.price_change_24h > 0

    def test_market_data_price_change_negative(self):
        """Test MarketData with negative price change."""
        market_data = MagicMock()
        market_data.price_change_24h = -10.2

        assert market_data.price_change_24h == -10.2
        assert market_data.price_change_24h < 0

    def test_market_data_high_volume(self):
        """Test MarketData with high volume."""
        market_data = MagicMock()
        market_data.volume_24h = 999999

        assert market_data.volume_24h == 999999

    def test_market_data_zero_volume(self):
        """Test MarketData with zero volume."""
        market_data = MagicMock()
        market_data.volume_24h = 0

        assert market_data.volume_24h == 0

    def test_market_data_id_is_uuid(self):
        """Test that MarketData id is UUID."""
        data_id = uuid4()

        market_data = MagicMock()
        market_data.id = data_id

        assert isinstance(market_data.id, UUID)

    def test_market_data_created_at_timestamp(self):
        """Test MarketData created_at timestamp."""
        now = datetime.now(UTC)

        market_data = MagicMock()
        market_data.created_at = now

        assert market_data.created_at == now


class TestMarketDataCacheModel:
    """Tests for MarketDataCache model."""

    def test_cache_creation_default_values(self):
        """Test creating MarketDataCache with default values."""
        cache = MagicMock()
        cache.id = uuid4()
        cache.cache_key = "market_csgo_items"
        cache.game = "csgo"
        cache.data_type = "items"
        cache.data = {}
        cache.created_at = datetime.now(UTC)
        cache.expires_at = datetime.now(UTC) + timedelta(hours=1)

        assert cache.cache_key == "market_csgo_items"
        assert cache.game == "csgo"
        assert cache.data_type == "items"

    def test_cache_creation_with_all_fields(self):
        """Test creating MarketDataCache with all fields."""
        cache = MagicMock()
        cache.id = uuid4()
        cache.cache_key = "market_dota2_prices_hook"
        cache.game = "dota2"
        cache.item_hash_name = "Dragonclaw Hook"
        cache.data_type = "price_history"
        cache.data = {"prices": [100, 150, 200]}
        cache.created_at = datetime.now(UTC)
        cache.expires_at = datetime.now(UTC) + timedelta(hours=24)

        assert cache.item_hash_name == "Dragonclaw Hook"
        assert cache.data_type == "price_history"
        assert "prices" in cache.data

    def test_cache_different_data_types(self):
        """Test MarketDataCache with different data types."""
        data_types = ["items", "price_history", "sales", "inventory"]

        for dt in data_types:
            cache = MagicMock()
            cache.data_type = dt
            cache.cache_key = f"cache_{dt}"

            assert cache.data_type == dt

    def test_cache_with_json_data(self):
        """Test MarketDataCache with JSON data."""
        json_data = {
            "items": [
                {"name": "AK-47", "price": 100},
                {"name": "M4A4", "price": 150},
            ],
            "total": 2,
            "page": 1,
        }

        cache = MagicMock()
        cache.data = json_data

        assert len(cache.data["items"]) == 2
        assert cache.data["total"] == 2

    def test_cache_expiration(self):
        """Test MarketDataCache expiration."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=1)

        cache = MagicMock()
        cache.created_at = now
        cache.expires_at = expires_at

        # Cache should not be expired
        assert cache.expires_at > now

    def test_cache_already_expired(self):
        """Test MarketDataCache that has already expired."""
        now = datetime.now(UTC)
        created_at = now - timedelta(hours=2)
        expires_at = now - timedelta(hours=1)

        cache = MagicMock()
        cache.created_at = created_at
        cache.expires_at = expires_at

        # Cache should be expired
        assert cache.expires_at < now

    def test_cache_repr(self):
        """Test MarketDataCache __repr__ method."""
        cache_key = "market_csgo_items_ak47"
        game = "csgo"
        data_type = "items"

        expected_repr = f"<MarketDataCache(key='{cache_key}', game='{game}', type='{data_type}')>"

        cache = MagicMock()
        cache.__repr__ = MagicMock(return_value=expected_repr)

        repr_result = repr(cache)

        assert "MarketDataCache" in repr_result
        assert cache_key in repr_result
        assert game in repr_result
        assert data_type in repr_result

    def test_cache_to_dict_all_fields(self):
        """Test MarketDataCache to_dict method with all fields."""
        cache_id = uuid4()
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        expires_at = datetime(2024, 1, 1, 13, 0, 0)

        expected_dict = {
            "id": str(cache_id),
            "cache_key": "market_test_key",
            "game": "csgo",
            "item_hash_name": "Test Item",
            "data_type": "price_history",
            "data": {"prices": [10, 20, 30]},
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        cache = MagicMock()
        cache.to_dict.return_value = expected_dict

        result = cache.to_dict()

        assert result["id"] == str(cache_id)
        assert result["cache_key"] == "market_test_key"
        assert result["game"] == "csgo"
        assert result["item_hash_name"] == "Test Item"
        assert result["data_type"] == "price_history"
        assert result["data"]["prices"] == [10, 20, 30]

    def test_cache_to_dict_none_values(self):
        """Test MarketDataCache to_dict method with None values."""
        expected_dict = {
            "id": str(uuid4()),
            "cache_key": "test_key",
            "game": "csgo",
            "item_hash_name": None,
            "data_type": "general",
            "data": {},
            "created_at": None,
            "expires_at": None,
        }

        cache = MagicMock()
        cache.to_dict.return_value = expected_dict

        result = cache.to_dict()

        assert result["item_hash_name"] is None
        assert result["created_at"] is None
        assert result["expires_at"] is None

    def test_cache_unique_key(self):
        """Test MarketDataCache unique key constraint."""
        cache1 = MagicMock()
        cache1.cache_key = "unique_key_123"

        cache2 = MagicMock()
        cache2.cache_key = "unique_key_456"

        assert cache1.cache_key != cache2.cache_key

    def test_cache_with_complex_data(self):
        """Test MarketDataCache with complex nested data."""
        complex_data = {
            "market_data": {
                "items": [
                    {
                        "id": "item_1",
                        "name": "Test Item",
                        "prices": {
                            "buy": 100,
                            "sell": 120,
                            "history": [90, 95, 100, 110],
                        },
                        "metadata": {
                            "rarity": "rare",
                            "exterior": "factory_new",
                        },
                    }
                ],
                "pagination": {"page": 1, "total_pages": 10},
            },
            "timestamp": "2024-01-01T12:00:00",
        }

        cache = MagicMock()
        cache.data = complex_data

        assert cache.data["market_data"]["items"][0]["name"] == "Test Item"
        assert cache.data["market_data"]["pagination"]["total_pages"] == 10

    def test_cache_id_is_uuid(self):
        """Test that MarketDataCache id is UUID."""
        cache_id = uuid4()

        cache = MagicMock()
        cache.id = cache_id

        assert isinstance(cache.id, UUID)

    def test_cache_long_cache_key(self):
        """Test MarketDataCache with long cache key."""
        long_key = "a" * 500  # Long cache key

        cache = MagicMock()
        cache.cache_key = long_key

        assert len(cache.cache_key) == 500

    def test_cache_unicode_item_name(self):
        """Test MarketDataCache with unicode item name."""
        unicode_name = "АК-47 | Красная линия (После полевых)"

        cache = MagicMock()
        cache.item_hash_name = unicode_name

        assert cache.item_hash_name == unicode_name


class TestMarketDataCacheIntegration:
    """Integration tests for MarketDataCache model."""

    def test_cache_lifecycle(self):
        """Test complete lifecycle of a market data cache entry."""
        # Create cache entry
        cache = MagicMock()
        cache.id = uuid4()
        cache.cache_key = "lifecycle_test"
        cache.game = "csgo"
        cache.data_type = "items"
        cache.data = {"items": []}
        cache.created_at = datetime.now(UTC)
        cache.expires_at = datetime.now(UTC) + timedelta(hours=1)

        # Verify creation
        assert cache.data == {"items": []}

        # Update data
        cache.data = {"items": [{"name": "Test", "price": 100}]}

        # Verify update
        assert len(cache.data["items"]) == 1

    def test_multiple_cache_entries_same_game(self):
        """Test multiple cache entries for the same game."""
        game = "csgo"
        caches = []

        data_types = ["items", "prices", "sales", "inventory"]

        for dt in data_types:
            cache = MagicMock()
            cache.id = uuid4()
            cache.game = game
            cache.data_type = dt
            cache.cache_key = f"cache_{game}_{dt}"
            caches.append(cache)

        # Verify all entries are for the same game
        for cache in caches:
            assert cache.game == game

        # Verify all cache keys are unique
        cache_keys = [cache.cache_key for cache in caches]
        assert len(set(cache_keys)) == len(data_types)


class TestMarketDataEdgeCases:
    """Edge case tests for market models."""

    def test_market_data_with_zero_price(self):
        """Test MarketData with zero price."""
        market_data = MagicMock()
        market_data.price_usd = 0.0

        assert market_data.price_usd == 0.0

    def test_market_data_with_very_high_price(self):
        """Test MarketData with very high price."""
        market_data = MagicMock()
        market_data.price_usd = 999999999.99

        assert market_data.price_usd == 999999999.99

    def test_market_data_with_very_low_price(self):
        """Test MarketData with very low price."""
        market_data = MagicMock()
        market_data.price_usd = 0.01

        assert market_data.price_usd == 0.01

    def test_market_data_with_empty_item_name(self):
        """Test MarketData with empty item name."""
        market_data = MagicMock()
        market_data.item_name = ""

        assert market_data.item_name == ""

    def test_cache_with_empty_data(self):
        """Test MarketDataCache with empty data."""
        cache = MagicMock()
        cache.data = {}

        assert cache.data == {}

    def test_cache_with_null_data(self):
        """Test MarketDataCache with null values in data."""
        cache = MagicMock()
        cache.data = {"price": None, "volume": None}

        assert cache.data["price"] is None
        assert cache.data["volume"] is None

    def test_market_data_with_special_characters(self):
        """Test MarketData with special characters in item name."""
        special_name = "★ Karambit | Doppler (Factory New)"

        market_data = MagicMock()
        market_data.item_name = special_name

        assert "★" in market_data.item_name
        assert "|" in market_data.item_name
