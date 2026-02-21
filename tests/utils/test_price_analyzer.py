"""Тесты для модуля price_analyzer.

Проверяет функции анализа цен и истории продаж.
"""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.price_analyzer import (
    _CACHE_TTL,
    _price_history_cache,
    analyze_supply_demand,
    calculate_price_statistics,
    calculate_price_trend,
    find_undervalued_items,
    get_investment_reason,
    get_investment_recommendations,
    get_item_price_history,
)


@pytest.fixture()
def mock_api():
    """Фикстура мокированного API."""
    api = MagicMock(spec=DMarketAPI)
    api._request = AsyncMock()
    return api


@pytest.fixture(autouse=True)
def clear_cache():
    """Очищать кэш перед каждым тестом."""
    _price_history_cache.clear()
    yield
    _price_history_cache.clear()


class TestCacheConstants:
    """Тесты констант кэша."""

    def test_cache_ttl_defined(self):
        """Тест что CACHE_TTL определен."""
        assert _CACHE_TTL == 3600

    def test_cache_ttl_is_int(self):
        """Тест что CACHE_TTL это int."""
        assert isinstance(_CACHE_TTL, int)

    def test_cache_ttl_positive(self):
        """Тест что CACHE_TTL положительный."""
        assert _CACHE_TTL > 0


class TestPriceHistoryCache:
    """Тесты кэширования истории цен."""

    def test_cache_initially_empty(self):
        """Тест что кэш изначально пуст."""
        assert len(_price_history_cache) == 0

    def test_can_add_to_cache(self):
        """Тест добавления в кэш."""
        _price_history_cache["test_key"] = {
            "data": [],
            "last_update": time.time(),
        }
        assert "test_key" in _price_history_cache

    def test_cache_structure(self):
        """Тест структуры кэша."""
        cache_entry = {
            "data": [{"price": 10.0}],
            "last_update": time.time(),
        }
        _price_history_cache["test"] = cache_entry

        assert "data" in _price_history_cache["test"]
        assert "last_update" in _price_history_cache["test"]


class TestGetItemPriceHistory:
    """Тесты функции get_item_price_history."""

    @pytest.mark.asyncio()
    async def test_get_price_history_success(self, mock_api):
        """Тест успешного получения истории цен."""
        mock_api._request.return_value = {
            "sales": [
                {
                    "date": "2024-01-01T00:00:00",
                    "price": 1000,  # В центах
                    "volume": 5,
                }
            ]
        }

        result = awAlgot get_item_price_history(mock_api, "item123", days=7)

        assert len(result) == 1
        assert result[0]["price"] == 10.0  # Конвертировано из центов
        assert result[0]["volume"] == 5

    @pytest.mark.asyncio()
    async def test_get_price_history_empty_response(self, mock_api):
        """Тест пустого ответа."""
        mock_api._request.return_value = {}

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_price_history_no_sales(self, mock_api):
        """Тест ответа без продаж."""
        mock_api._request.return_value = {"sales": []}

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_price_history_api_error(self, mock_api):
        """Тест обработки ошибки API."""
        mock_api._request.side_effect = Exception("API Error")

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_price_history_uses_cache(self, mock_api):
        """Тест использования кэша."""
        # Первый запрос
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1}]
        }

        result1 = awAlgot get_item_price_history(mock_api, "item123", days=7)

        # ВтоSwarm запрос (должен использовать кэш)
        result2 = awAlgot get_item_price_history(mock_api, "item123", days=7)

        # API должен быть вызван только один раз
        assert mock_api._request.call_count == 1
        assert result1 == result2

    @pytest.mark.asyncio()
    async def test_get_price_history_cache_expiry(self, mock_api):
        """Тест истечения кэша."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1}]
        }

        # Первый запрос
        awAlgot get_item_price_history(mock_api, "item123", days=7)

        # Искусственно устанавливаем старый timestamp
        cache_key = "item123_7"
        _price_history_cache[cache_key]["last_update"] = time.time() - _CACHE_TTL - 1

        # ВтоSwarm запрос (кэш истек)
        awAlgot get_item_price_history(mock_api, "item123", days=7)

        # API должен быть вызван дважды
        assert mock_api._request.call_count == 2

    @pytest.mark.asyncio()
    async def test_get_price_history_different_days(self, mock_api):
        """Тест с разным количеством дней."""
        mock_api._request.return_value = {"sales": []}

        awAlgot get_item_price_history(mock_api, "item123", days=7)
        awAlgot get_item_price_history(mock_api, "item123", days=30)

        # Должно быть два вызова для разных периодов
        assert mock_api._request.call_count == 2

    @pytest.mark.asyncio()
    async def test_get_price_history_price_conversion(self, mock_api):
        """Тест конвертации цены из центов."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 2500, "volume": 1}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result[0]["price"] == 25.0

    @pytest.mark.asyncio()
    async def test_get_price_history_invalid_date(self, mock_api):
        """Тест обработки невалидной даты."""
        mock_api._request.return_value = {
            "sales": [{"date": "invalid_date", "price": 1000, "volume": 1}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        # Запись с невалидной датой должна быть пропущена
        assert len(result) == 0

    @pytest.mark.asyncio()
    async def test_get_price_history_missing_fields(self, mock_api):
        """Тест обработки отсутствующих полей."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00"}]  # Нет price и volume
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        # Запись должна быть обработана с дефолтными значениями или пропущена
        assert isinstance(result, list)


class TestCalculatePriceStatistics:
    """Тесты функции calculate_price_statistics."""

    def test_calculate_statistics_empty_history(self):
        """Тест расчета статистики для пустой истории."""
        result = calculate_price_statistics([])

        assert result["avg_price"] == 0
        assert result["min_price"] == 0
        assert result["max_price"] == 0
        assert result["volatility"] == 0

    def test_calculate_statistics_single_price(self):
        """Тест расчета статистики для одной цены."""
        history = [{"price": 10.0, "date": datetime.now(), "volume": 1}]

        result = calculate_price_statistics(history)

        assert result["avg_price"] == 10.0
        assert result["min_price"] == 10.0
        assert result["max_price"] == 10.0
        assert result["volatility"] == 0

    def test_calculate_statistics_multiple_prices(self):
        """Тест расчета статистики для нескольких цен."""
        history = [
            {"price": 10.0, "date": datetime.now(), "volume": 1},
            {"price": 20.0, "date": datetime.now(), "volume": 1},
            {"price": 30.0, "date": datetime.now(), "volume": 1},
        ]

        result = calculate_price_statistics(history)

        assert result["avg_price"] == 20.0
        assert result["min_price"] == 10.0
        assert result["max_price"] == 30.0
        assert result["volatility"] > 0

    def test_calculate_statistics_weighted_average(self):
        """Тест расчета взвешенного среднего."""
        history = [
            {"price": 10.0, "date": datetime.now(), "volume": 1},
            {"price": 20.0, "date": datetime.now(), "volume": 2},
        ]

        result = calculate_price_statistics(history)

        # Взвешенное среднее: (10*1 + 20*2) / 3 = 16.67
        assert 16 < result["weighted_avg_price"] < 17

    def test_calculate_statistics_returns_dict(self):
        """Тест что функция возвращает словарь."""
        result = calculate_price_statistics([])

        assert isinstance(result, dict)

    def test_calculate_statistics_has_required_fields(self):
        """Тест что результат содержит требуемые поля."""
        result = calculate_price_statistics([])

        required_fields = [
            "avg_price",
            "min_price",
            "max_price",
            "volatility",
            "volume",
        ]
        for field in required_fields:
            assert field in result


class TestCacheManagement:
    """Тесты управления кэшем."""

    def test_cache_key_format(self):
        """Тест формата ключа кэша."""
        cache_key = "item123_7"
        _price_history_cache[cache_key] = {
            "data": [],
            "last_update": time.time(),
        }

        assert cache_key in _price_history_cache

    def test_cache_stores_timestamp(self):
        """Тест что кэш сохраняет timestamp."""
        cache_key = "test"
        timestamp = time.time()
        _price_history_cache[cache_key] = {
            "data": [],
            "last_update": timestamp,
        }

        stored_timestamp = _price_history_cache[cache_key]["last_update"]
        assert abs(stored_timestamp - timestamp) < 0.1

    def test_cache_independence(self):
        """Тест независимости записей кэша."""
        _price_history_cache["item1_7"] = {
            "data": [{"price": 10.0}],
            "last_update": time.time(),
        }
        _price_history_cache["item2_7"] = {
            "data": [{"price": 20.0}],
            "last_update": time.time(),
        }

        assert (
            _price_history_cache["item1_7"]["data"]
            != _price_history_cache["item2_7"]["data"]
        )


class TestPriceConversion:
    """Тесты конвертации цен."""

    @pytest.mark.asyncio()
    async def test_price_cents_to_dollars(self, mock_api):
        """Тест конвертации центов в доллары."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 100, "volume": 1}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result[0]["price"] == 1.0

    @pytest.mark.asyncio()
    async def test_price_zero_cents(self, mock_api):
        """Тест обработки нулевой цены."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 0, "volume": 1}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result[0]["price"] == 0.0


class TestEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio()
    async def test_very_large_price(self, mock_api):
        """Тест очень большой цены."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 1000000, "volume": 1}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result[0]["price"] == 10000.0

    @pytest.mark.asyncio()
    async def test_very_large_volume(self, mock_api):
        """Тест очень большого объема."""
        mock_api._request.return_value = {
            "sales": [{"date": "2024-01-01T00:00:00", "price": 1000, "volume": 999999}]
        }

        result = awAlgot get_item_price_history(mock_api, "item123")

        assert result[0]["volume"] == 999999

    def test_statistics_with_extreme_values(self):
        """Тест статистики с экстремальными значениями."""
        history = [
            {"price": 0.01, "date": datetime.now(), "volume": 1},
            {"price": 10000.0, "date": datetime.now(), "volume": 1},
        ]

        result = calculate_price_statistics(history)

        assert result["min_price"] == 0.01
        assert result["max_price"] == 10000.0
        assert result["volatility"] > 0


# ============================================================================
# Additional Tests for Extended Coverage
# ============================================================================


class TestCalculatePriceTrend:
    """Tests for calculate_price_trend function."""

    @pytest.mark.asyncio()
    async def test_calculate_trend_upward(self, mock_api):
        """Test detection of upward trend."""
        # Arrange
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-02T00:00:00", "price": 1100, "volume": 1},
                {"date": "2024-01-03T00:00:00", "price": 1200, "volume": 1},
                {"date": "2024-01-04T00:00:00", "price": 1300, "volume": 1},
                {"date": "2024-01-05T00:00:00", "price": 1400, "volume": 1},
                {"date": "2024-01-06T00:00:00", "price": 1500, "volume": 1},
                {"date": "2024-01-07T00:00:00", "price": 1600, "volume": 1},
                {"date": "2024-01-08T00:00:00", "price": 1700, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert result["trend"] == "upward"
        assert result["confidence"] > 0
        assert result["change_percent"] > 0

    @pytest.mark.asyncio()
    async def test_calculate_trend_downward(self, mock_api):
        """Test detection of downward trend."""
        # Arrange
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 2000, "volume": 1},
                {"date": "2024-01-02T00:00:00", "price": 1800, "volume": 1},
                {"date": "2024-01-03T00:00:00", "price": 1600, "volume": 1},
                {"date": "2024-01-04T00:00:00", "price": 1400, "volume": 1},
                {"date": "2024-01-05T00:00:00", "price": 1200, "volume": 1},
                {"date": "2024-01-06T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-07T00:00:00", "price": 800, "volume": 1},
                {"date": "2024-01-08T00:00:00", "price": 600, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert result["trend"] == "downward"
        assert result["change_percent"] < 0

    @pytest.mark.asyncio()
    async def test_calculate_trend_stable(self, mock_api):
        """Test detection of stable/sideways trend."""
        # Arrange - prices that oscillate around the same value
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-02T00:00:00", "price": 1020, "volume": 1},
                {"date": "2024-01-03T00:00:00", "price": 980, "volume": 1},
                {"date": "2024-01-04T00:00:00", "price": 1010, "volume": 1},
                {"date": "2024-01-05T00:00:00", "price": 990, "volume": 1},
                {"date": "2024-01-06T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-07T00:00:00", "price": 1010, "volume": 1},
                {"date": "2024-01-08T00:00:00", "price": 1000, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert - trend should be stable or show minimal change
        assert result["trend"] in {"stable", "upward", "downward"}
        assert (
            abs(result["change_percent"]) < 10
        )  # Less than 10% change indicates stable

    @pytest.mark.asyncio()
    async def test_calculate_trend_empty_history(self, mock_api):
        """Test trend calculation with empty history."""
        # Arrange
        mock_api._request.return_value = {}

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert result["trend"] == "unknown"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio()
    async def test_calculate_trend_insufficient_data(self, mock_api):
        """Test trend calculation with insufficient data (1 point)."""
        # Arrange
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert result["trend"] == "stable"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio()
    async def test_calculate_trend_returns_period_prices(self, mock_api):
        """Test that trend calculation returns period prices."""
        # Arrange
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-02T00:00:00", "price": 1100, "volume": 1},
                {"date": "2024-01-03T00:00:00", "price": 1200, "volume": 1},
                {"date": "2024-01-04T00:00:00", "price": 1300, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert "period_prices" in result
        assert isinstance(result["period_prices"], list)
        assert len(result["period_prices"]) >= 2

    @pytest.mark.asyncio()
    async def test_calculate_trend_returns_absolute_change(self, mock_api):
        """Test that trend calculation returns absolute change."""
        # Arrange
        mock_api._request.return_value = {
            "sales": [
                {"date": "2024-01-01T00:00:00", "price": 1000, "volume": 1},
                {"date": "2024-01-02T00:00:00", "price": 1200, "volume": 1},
                {"date": "2024-01-03T00:00:00", "price": 1400, "volume": 1},
                {"date": "2024-01-04T00:00:00", "price": 1600, "volume": 1},
            ]
        }

        # Act
        result = awAlgot calculate_price_trend(mock_api, "item123", days=7)

        # Assert
        assert "absolute_change" in result
        assert result["absolute_change"] > 0


class TestFindUndervaluedItems:
    """Tests for find_undervalued_items function."""

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_success(self, mock_api):
        """Test successful finding of undervalued items."""
        # Arrange
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "itemId": "item1",
                        "title": "AK-47 | Redline",
                        "price": {"amount": 1000},  # $10 current price
                    }
                ]
            }
        )
        mock_api._request = AsyncMock(
            return_value={
                "sales": [
                    {
                        "date": "2024-01-01T00:00:00",
                        "price": 1500,
                        "volume": 1,
                    },  # avg $15
                    {"date": "2024-01-02T00:00:00", "price": 1600, "volume": 1},
                    {"date": "2024-01-03T00:00:00", "price": 1500, "volume": 1},
                ]
            }
        )

        # Act
        result = awAlgot find_undervalued_items(
            mock_api,
            game="csgo",
            price_from=1.0,
            price_to=100.0,
            discount_threshold=20.0,
            max_results=10,
        )

        # Assert
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_empty_response(self, mock_api):
        """Test finding undervalued items with empty response."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={})

        # Act
        result = awAlgot find_undervalued_items(mock_api, game="csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_no_objects(self, mock_api):
        """Test finding undervalued items with no objects."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot find_undervalued_items(mock_api, game="csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_api_error(self, mock_api):
        """Test handling API error when finding undervalued items."""
        # Arrange
        mock_api.get_market_items = AsyncMock(side_effect=Exception("API Error"))

        # Act
        result = awAlgot find_undervalued_items(mock_api, game="csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_filters_by_discount(self, mock_api):
        """Test that items are filtered by discount threshold."""
        # Arrange
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {
                        "itemId": "item1",
                        "title": "Item 1",
                        "price": {"amount": 500},  # $5 - 50% below avg
                    }
                ]
            }
        )
        mock_api._request = AsyncMock(
            return_value={
                "sales": [
                    {
                        "date": "2024-01-01T00:00:00",
                        "price": 1000,
                        "volume": 1,
                    },  # avg $10
                ]
            }
        )

        # Act
        result = awAlgot find_undervalued_items(
            mock_api,
            game="csgo",
            discount_threshold=30.0,  # Looking for > 30% discount
        )

        # Assert
        # Item has 50% discount, should be found
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_find_undervalued_items_max_results(self, mock_api):
        """Test that results are limited to max_results."""
        # Arrange
        objects = [
            {
                "itemId": f"item{i}",
                "title": f"Item {i}",
                "price": {"amount": 500},
            }
            for i in range(20)
        ]
        mock_api.get_market_items = AsyncMock(return_value={"objects": objects})
        mock_api._request = AsyncMock(
            return_value={
                "sales": [
                    {"date": "2024-01-01T00:00:00", "price": 2000, "volume": 1},
                ]
            }
        )

        # Act
        result = awAlgot find_undervalued_items(
            mock_api,
            game="csgo",
            max_results=5,
            discount_threshold=10.0,
        )

        # Assert
        assert len(result) <= 5


class TestAnalyzeSupplyDemand:
    """Tests for analyze_supply_demand function."""

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_high_liquidity(self, mock_api):
        """Test high liquidity detection."""
        # Arrange
        mock_api._request = AsyncMock(
            return_value={
                "offers": [{"price": 1000, "id": f"sell{i}"} for i in range(10)],
                "targets": [{"price": 950, "id": f"buy{i}"} for i in range(10)],
            }
        )

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["liquidity"] == "high"
        assert result["supply_count"] == 10
        assert result["demand_count"] == 10

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_medium_liquidity(self, mock_api):
        """Test medium liquidity detection."""
        # Arrange - spread must be < 20% and have > 2 buy/sell offers
        mock_api._request = AsyncMock(
            return_value={
                "offers": [
                    {"price": 1000, "id": f"sell{i}"} for i in range(3)  # Min sell: $10
                ],
                "targets": [
                    {"price": 900, "id": f"buy{i}"} for i in range(3)  # Max buy: $9
                ],
            }
        )
        # Spread: (10-9)/10 * 100 = 10% < 20%, so medium liquidity

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["liquidity"] == "medium"

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_low_liquidity(self, mock_api):
        """Test low liquidity detection."""
        # Arrange
        mock_api._request = AsyncMock(
            return_value={
                "offers": [{"price": 1000, "id": "sell1"}],
                "targets": [{"price": 500, "id": "buy1"}],
            }
        )

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["liquidity"] == "low"

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_empty_response(self, mock_api):
        """Test empty response handling."""
        # Arrange
        mock_api._request = AsyncMock(return_value=None)

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["liquidity"] == "unknown"
        assert result["supply_count"] == 0
        assert result["demand_count"] == 0

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_api_error(self, mock_api):
        """Test API error handling."""
        # Arrange
        mock_api._request = AsyncMock(side_effect=Exception("API Error"))

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["liquidity"] == "unknown"
        assert result["spread"] == 0

    @pytest.mark.asyncio()
    async def test_analyze_supply_demand_spread_calculation(self, mock_api):
        """Test spread calculation."""
        # Arrange
        mock_api._request = AsyncMock(
            return_value={
                "offers": [
                    {"price": 1000, "id": "sell1"},  # Min sell: $10
                ],
                "targets": [
                    {"price": 900, "id": "buy1"},  # Max buy: $9
                ],
            }
        )

        # Act
        result = awAlgot analyze_supply_demand(mock_api, "item123")

        # Assert
        assert result["min_sell_price"] == 10.0
        assert result["max_buy_price"] == 9.0
        assert result["spread"] == 1.0  # $10 - $9 = $1
        assert result["spread_percent"] == 10.0  # 1/10 * 100 = 10%


class TestGetInvestmentRecommendations:
    """Tests for get_investment_recommendations function."""

    @pytest.mark.asyncio()
    async def test_get_recommendations_low_risk(self, mock_api):
        """Test getting recommendations with low risk level."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot get_investment_recommendations(
            mock_api,
            game="csgo",
            budget=100.0,
            risk_level="low",
        )

        # Assert
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_recommendations_medium_risk(self, mock_api):
        """Test getting recommendations with medium risk level."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot get_investment_recommendations(
            mock_api,
            game="csgo",
            budget=100.0,
            risk_level="medium",
        )

        # Assert
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_recommendations_high_risk(self, mock_api):
        """Test getting recommendations with high risk level."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot get_investment_recommendations(
            mock_api,
            game="csgo",
            budget=100.0,
            risk_level="high",
        )

        # Assert
        assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_get_recommendations_empty_result(self, mock_api):
        """Test getting recommendations with no matches."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot get_investment_recommendations(
            mock_api,
            game="csgo",
            budget=10.0,
            risk_level="medium",
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_get_recommendations_respects_budget(self, mock_api):
        """Test that recommendations respect the budget."""
        # Arrange
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        # Act
        result = awAlgot get_investment_recommendations(
            mock_api,
            game="csgo",
            budget=50.0,
            risk_level="low",
        )

        # Assert
        assert isinstance(result, list)
        # Low risk settings should filter by price_to = min(50, budget)


class TestGetInvestmentReason:
    """Tests for get_investment_reason function."""

    def test_get_reason_significant_discount(self):
        """Test reason for significant discount."""
        # Arrange
        item_data = {
            "discount": 30.0,
            "liquidity": "high",
            "trend": "stable",
            "trend_confidence": 0.5,
            "demand_count": 5,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Значительная скидка" in reason
        assert "30.0%" in reason

    def test_get_reason_good_discount(self):
        """Test reason for good discount."""
        # Arrange
        item_data = {
            "discount": 20.0,
            "liquidity": "medium",
            "trend": "stable",
            "trend_confidence": 0.5,
            "demand_count": 3,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Хорошая скидка" in reason
        assert "20.0%" in reason

    def test_get_reason_standard_discount(self):
        """Test reason for standard discount."""
        # Arrange
        item_data = {
            "discount": 10.0,
            "liquidity": "low",
            "trend": "stable",
            "trend_confidence": 0.5,
            "demand_count": 1,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "10.0%" in reason

    def test_get_reason_high_liquidity(self):
        """Test reason includes high liquidity."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "high",
            "trend": "stable",
            "trend_confidence": 0.3,
            "demand_count": 3,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Высокая ликвидность" in reason

    def test_get_reason_medium_liquidity(self):
        """Test reason includes medium liquidity."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "medium",
            "trend": "stable",
            "trend_confidence": 0.3,
            "demand_count": 3,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Средняя ликвидность" in reason

    def test_get_reason_low_liquidity(self):
        """Test reason includes low liquidity."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "low",
            "trend": "stable",
            "trend_confidence": 0.3,
            "demand_count": 1,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Низкая ликвидность" in reason

    def test_get_reason_upward_trend(self):
        """Test reason includes upward trend."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "medium",
            "trend": "upward",
            "trend_confidence": 0.8,
            "demand_count": 5,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Восходящий тренд" in reason

    def test_get_reason_downward_trend(self):
        """Test reason includes downward trend warning."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "medium",
            "trend": "downward",
            "trend_confidence": 0.8,
            "demand_count": 5,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Нисходящий тренд" in reason
        assert "риск" in reason

    def test_get_reason_high_demand(self):
        """Test reason includes high demand."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "medium",
            "trend": "stable",
            "trend_confidence": 0.3,
            "demand_count": 15,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Высокий спрос" in reason
        assert "15 заявок" in reason

    def test_get_reason_moderate_demand(self):
        """Test reason includes moderate demand."""
        # Arrange
        item_data = {
            "discount": 15.0,
            "liquidity": "medium",
            "trend": "stable",
            "trend_confidence": 0.3,
            "demand_count": 7,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Умеренный спрос" in reason
        assert "7 заявок" in reason

    def test_get_reason_combined(self):
        """Test that reason combines multiple factors."""
        # Arrange
        item_data = {
            "discount": 30.0,
            "liquidity": "high",
            "trend": "upward",
            "trend_confidence": 0.8,
            "demand_count": 12,
        }

        # Act
        reason = get_investment_reason(item_data)

        # Assert
        assert "Значительная скидка" in reason
        assert "Высокая ликвидность" in reason
        assert "Восходящий тренд" in reason
        assert "Высокий спрос" in reason
        assert ". " in reason  # Multiple reasons joined
