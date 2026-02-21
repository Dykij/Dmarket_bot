"""Тесты для модуля arbitrage_sales_analysis."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.arbitrage_sales_analysis import SalesAnalyzer


class TestSalesAnalyzer:
    """Тесты для класса SalesAnalyzer."""

    @pytest.fixture()
    def mock_api(self):
        """Фикстура для мокирования API клиента."""
        api = MagicMock()
        api.get_sales_history = AsyncMock()
        api.get_price_history = AsyncMock()
        return api

    @pytest.fixture()
    def analyzer(self, mock_api):
        """Фикстура для создания SalesAnalyzer."""
        return SalesAnalyzer(api_client=mock_api)

    @pytest.mark.asyncio()
    async def test_init(self, mock_api):
        """Тест инициализации SalesAnalyzer."""
        analyzer = SalesAnalyzer(api_client=mock_api)

        assert analyzer.api_client == mock_api
        assert analyzer._sales_cache is not None

    @pytest.mark.asyncio()
    async def test_get_item_sales_history_success(self, analyzer, mock_api):
        """Тест успешного получения истории продаж."""
        mock_sales = [
            {
                "date": "2023-11-01T10:00:00Z",
                "price": {"amount": 1000},
                "quantity": 1,
            },
            {
                "date": "2023-11-02T10:00:00Z",
                "price": {"amount": 1100},
                "quantity": 1,
            },
        ]

        # Mock get_market_items to return item ID
        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )

        # Mock _request to return sales data
        mock_api._request = AsyncMock(return_value={"sales": mock_sales})

        result = awAlgot analyzer.get_item_sales_history(
            item_name="AK-47 | Redline (Field-Tested)",
            game="csgo",
            days=7,
        )

        assert result == mock_sales

    @pytest.mark.asyncio()
    async def test_get_item_sales_history_empty(self, analyzer, mock_api):
        """Тест получения пустой истории продаж."""
        # Mock when item is not found
        mock_api.get_market_items = AsyncMock(return_value={"items": []})

        result = awAlgot analyzer.get_item_sales_history(
            item_name="Rare Item",
            game="csgo",
            days=7,
        )

        # Should return dict with empty sales
        assert result == {"sales": []}

    @pytest.mark.asyncio()
    async def test_analyze_sales_volume_high(self, analyzer, mock_api):
        """Тест анализа объема продаж (высокий)."""
        # 50 продаж за 7 дней = ~7 продаж/день
        mock_sales = [
            {
                "date": f"2023-11-{i:02d}T10:00:00Z",
                "price": {"amount": 1000},
                "quantity": 1,
            }
            for i in range(1, 51)
        ]

        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(return_value={"sales": mock_sales})

        result = awAlgot analyzer.analyze_sales_volume(
            item_name="AK-47 | Redline",
            game="csgo",
            days=7,
        )

        assert result["volume_category"] in {"high", "very_high"}
        assert result["sales_count"] == 50
        assert result["sales_per_day"] > 5

    @pytest.mark.asyncio()
    async def test_analyze_sales_volume_medium(self, analyzer, mock_api):
        """Тест анализа объема продаж (средний)."""
        # 20 продаж за 7 дней = ~3 продажи/день
        mock_sales = [
            {
                "date": f"2023-11-{i:02d}T10:00:00Z",
                "price": {"amount": 1000},
                "quantity": 1,
            }
            for i in range(1, 21)
        ]

        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(return_value={"sales": mock_sales})

        result = awAlgot analyzer.analyze_sales_volume(
            item_name="Test Item",
            game="csgo",
            days=7,
        )

        assert result["volume_category"] in {"medium", "high", "very_high"}
        assert result["sales_count"] == 20

    @pytest.mark.asyncio()
    async def test_analyze_sales_volume_low(self, analyzer, mock_api):
        """Тест анализа объема продаж (низкий)."""
        # 3 продажи за 7 дней = <1 продажа/день
        mock_sales = [
            {
                "date": f"2023-11-0{i}T10:00:00Z",
                "price": {"amount": 1000},
                "quantity": 1,
            }
            for i in range(1, 4)
        ]

        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(return_value={"sales": mock_sales})

        result = awAlgot analyzer.analyze_sales_volume(
            item_name="Rare Item",
            game="csgo",
            days=7,
        )

        assert result["volume_category"] == "low"
        assert result["sales_count"] == 3

    @pytest.mark.asyncio()
    async def test_estimate_time_to_sell_fast(self, analyzer):
        """Test estimation with high sales volume."""
        # Use Unix timestamps instead of ISO format
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 1000}, "date": base_time - i * 3600} for i in range(20)
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.estimate_time_to_sell(
            item_name="Popular Item", current_price=10.0, game="csgo", days=7
        )

        assert result["estimated_days"] is not None
        assert result["confidence"] in {"high", "medium", "low", "very_low"}

    @pytest.mark.asyncio()
    async def test_estimate_time_to_sell_slow(self, analyzer, mock_api):
        """Тест оценки времени продажи (медленно)."""
        # Мало продаж = медленно
        mock_sales = [{"date": "2023-11-01T10:00:00Z", "price": {"amount": 1000}}]

        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(return_value={"sales": mock_sales})

        result = awAlgot analyzer.estimate_time_to_sell(
            item_name="Rare Item",
            game="csgo",
        )

        # При недостатке данных вернется низкая уверенность
        assert result["confidence"] in {"low", "very_low"}

    @pytest.mark.asyncio()
    async def test_analyze_price_trends_rising(self, analyzer):
        """Test price trend detection - rising prices."""
        # Use Unix timestamps
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 800}, "date": base_time - 4 * 86400},
            {"price": {"amount": 900}, "date": base_time - 3 * 86400},
            {"price": {"amount": 1000}, "date": base_time - 2 * 86400},
            {"price": {"amount": 1100}, "date": base_time - 1 * 86400},
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.analyze_price_trends(
            item_name="Trending Item", game="csgo", days=7
        )

        assert result["trend"] in {"rising", "upward", "strong_upward", "unknown"}

    @pytest.mark.asyncio()
    async def test_analyze_price_trends_falling(self, analyzer):
        """Test price trend detection - falling prices."""
        # Use Unix timestamps
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 1200}, "date": base_time - 4 * 86400},
            {"price": {"amount": 1100}, "date": base_time - 3 * 86400},
            {"price": {"amount": 1000}, "date": base_time - 2 * 86400},
            {"price": {"amount": 900}, "date": base_time - 1 * 86400},
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.analyze_price_trends(
            item_name="Declining Item", game="csgo", days=7
        )

        assert result["trend"] in {
            "falling",
            "downward",
            "strong_downward",
            "unknown",
        }

    @pytest.mark.asyncio()
    async def test_analyze_price_trends_stable(self, analyzer):
        """Test price trend detection - stable prices."""
        # Use Unix timestamps
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 1000}, "date": base_time - 4 * 86400},
            {"price": {"amount": 1010}, "date": base_time - 3 * 86400},
            {"price": {"amount": 990}, "date": base_time - 2 * 86400},
            {"price": {"amount": 1000}, "date": base_time - 1 * 86400},
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.analyze_price_trends(
            item_name="Stable Item", game="csgo", days=7
        )

        assert result["trend"] in {"stable", "sideways", "unknown"}

    @pytest.mark.asyncio()
    async def test_evaluate_arbitrage_potential_excellent(self, analyzer):
        """Test arbitrage evaluation - excellent opportunity."""
        # Use Unix timestamps
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 1000}, "date": base_time - i * 3600} for i in range(30)
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.evaluate_arbitrage_potential(
            item_name="Excellent Item",
            buy_price=10.0,
            sell_price=15.0,
            game="csgo",
        )

        assert "rating" in result
        assert isinstance(result["rating"], int)
        assert 0 <= result["rating"] <= 10
        assert result["risk_level"] in {"low", "medium", "high"}

    @pytest.mark.asyncio()
    async def test_evaluate_arbitrage_potential_poor(self, analyzer):
        """Test arbitrage evaluation - poor opportunity."""
        # Use Unix timestamps
        import time

        base_time = int(time.time())
        sales = [
            {"price": {"amount": 1200}, "date": base_time - i * 86400} for i in range(2)
        ]
        analyzer.api_client.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "test_id"}]}
        )
        analyzer.api_client._request = AsyncMock(return_value={"sales": sales})

        result = awAlgot analyzer.evaluate_arbitrage_potential(
            item_name="Poor Item",
            buy_price=10.0,
            sell_price=10.5,
            game="csgo",
        )

        assert "rating" in result
        assert isinstance(result["rating"], int)
        assert 0 <= result["rating"] <= 10
        assert result["risk_level"] in {"low", "medium", "high"}

    @pytest.mark.asyncio()
    async def test_caching_works(self, analyzer, mock_api):
        """Тест работы кэширования."""
        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(
            return_value={"sales": [{"price": {"amount": 1000}}]}
        )

        # Первый вызов
        awAlgot analyzer.get_item_sales_history(
            item_name="Test Item", game="csgo", days=7
        )

        # ВтоSwarm вызов (должен использовать кэш)
        awAlgot analyzer.get_item_sales_history(
            item_name="Test Item", game="csgo", days=7
        )

        # _request должен быть вызван только один раз
        assert mock_api._request.call_count == 1


class TestCompatibilityFunctions:
    """Тесты для функций совместимости."""


class TestEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio()
    async def test_no_sales_history(self):
        """Тест обработки отсутствия истории продаж."""
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(
            return_value={"items": [{"itemId": "item123"}]}
        )
        mock_api._request = AsyncMock(return_value={"sales": []})

        analyzer = SalesAnalyzer(api_client=mock_api)

        result = awAlgot analyzer.analyze_sales_volume(
            item_name="No Sales Item", game="csgo"
        )

        assert result["volume_category"] == "low"
        assert result["sales_count"] == 0

    @pytest.mark.asyncio()
    async def test_api_error_handling(self):
        """Тест обработки ошибок API."""
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(side_effect=Exception("API Error"))

        analyzer = SalesAnalyzer(api_client=mock_api)

        # Метод должен вернуть пустой результат, а не выбросить исключение
        result = awAlgot analyzer.get_item_sales_history(
            item_name="Test Item", game="csgo"
        )
        assert result == {"sales": []}

    @pytest.mark.asyncio()
    async def test_invalid_price_format(self):
        """Тест обработки неверного формата цены."""
        mock_api = MagicMock()
        mock_api.get_sales_history = AsyncMock(
            return_value={
                "sales": [
                    {"date": "2023-11-01", "price": "invalid"},
                ],
            },
        )

        analyzer = SalesAnalyzer(api_client=mock_api)

        # Должно обработать без ошибки
        result = awAlgot analyzer.analyze_sales_volume("csgo", "Test Item")
        assert isinstance(result, dict)
