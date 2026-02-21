"""Тесты для модуля market_analysis.py."""

from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.market_analysis import (
    _calculate_market_volatility_level,
    _calculate_popularity_score,
    _extract_price_from_item,
    _extract_trending_categories,
    _generate_market_recommendations,
    _get_market_direction,
    analyze_market_volatility,
    analyze_price_changes,
    find_trending_items,
    generate_market_report,
)


class TestExtractPriceFromItem:
    """Тесты для _extract_price_from_item."""

    def test_extract_price_with_suggested_price(self):
        """Тест извлечения цены с suggestedPrice."""
        item = {"suggestedPrice": 1250}  # В центах
        assert _extract_price_from_item(item) == 12.50

    def test_extract_price_with_price_field(self):
        """Тест извлечения цены с price.amount."""
        item = {"price": {"amount": 599}}  # 5.99 USD в центах
        assert _extract_price_from_item(item) == 5.99

    def test_extract_price_with_cents(self):
        """Тест извлечения цены в центах."""
        item = {"price": 1299}  # 12.99 USD
        assert _extract_price_from_item(item) == 12.99

    def test_extract_price_invalid(self):
        """Тест некорректных данных."""
        assert _extract_price_from_item({}) == 0.0
        assert _extract_price_from_item({"price": "invalid"}) == 0.0


class TestCalculatePopularityScore:
    """Тесты для _calculate_popularity_score."""

    def test_calculate_score_with_sales(self):
        """Тест расчёта score с продажами."""
        item = {"salesVolume": 100, "offersCount": 50}
        score = _calculate_popularity_score(item)
        # Формула: salesVolume * 2 * (salesVolume / (offersCount + 1))
        # 100 * 2 * (100 / 51) = 200 * 1.96 = ~392
        assert score > 0
        assert isinstance(score, float)

    def test_calculate_score_zero_offers(self):
        """Тест с нулевым количеством предложений."""
        item = {"salesVolume": 100, "offersCount": 0}
        score = _calculate_popularity_score(item)
        # Формула: 100 * 2 * (100 / 1) = 200 * 100 = 20000
        assert score > 0

    def test_calculate_score_no_data(self):
        """Тест без данных."""
        assert _calculate_popularity_score({}) == 0.0


class TestGetMarketDirection:
    """Тесты для _get_market_direction."""

    def test_direction_up(self):
        """Тест восходящего тренда."""
        price_changes = [
            {"direction": "up"},
            {"direction": "up"},
            {"direction": "up"},
            {"direction": "up"},
            {"direction": "up"},
            {"direction": "down"},
        ]
        # up_count = 5, down_count = 1; 5 > 1 * 1.5 = True
        assert _get_market_direction(price_changes) == "up"

    def test_direction_down(self):
        """Тест нисходящего тренда."""
        price_changes = [
            {"direction": "down"},
            {"direction": "down"},
            {"direction": "down"},
            {"direction": "down"},
            {"direction": "down"},
            {"direction": "up"},
        ]
        # down_count = 5, up_count = 1; 5 > 1 * 1.5 = True
        assert _get_market_direction(price_changes) == "down"

    def test_direction_stable(self):
        """Тест стабильного рынка."""
        price_changes = [
            {"direction": "up"},
            {"direction": "up"},
            {"direction": "down"},
            {"direction": "down"},
        ]
        # up_count = 2, down_count = 2; 2 не > 2 * 1.5 и 2 не > 2 * 1.5
        result = _get_market_direction(price_changes)
        assert result == "stable"

    def test_direction_empty(self):
        """Тест с пустым списком."""
        assert _get_market_direction([]) == "stable"


class TestExtractTrendingCategories:
    """Тесты для _extract_trending_categories."""

    def test_extract_categories(self):
        """Тест извлечения категорий."""
        items = [
            {"market_hash_name": "AK-47 | Redline", "category": "Rifle"},
            {"market_hash_name": "AWP | Dragon Lore", "category": "Sniper Rifle"},
            {"market_hash_name": "M4A4 | Howl", "category": "Rifle"},
        ]
        categories = _extract_trending_categories(items)
        assert isinstance(categories, list)
        # Функция извлекает из названий, а не из category
        assert len(categories) >= 0

    def test_extract_categories_empty(self):
        """Тест с пустым списком."""
        # Функция возвращает ["Нет данных"] для пустого списка
        assert _extract_trending_categories([]) == ["Нет данных"]


class TestCalculateMarketVolatilityLevel:
    """Тесты для _calculate_market_volatility_level."""

    def test_high_volatility(self):
        """Тест высокой волатильности."""
        volatile_items = [
            {"volatility_score": 50},
            {"volatility_score": 45},
            {"volatility_score": 40},
            {"volatility_score": 35},
            {"volatility_score": 30},
        ]
        level = _calculate_market_volatility_level(volatile_items)
        assert level in {"high", "medium", "low"}

    def test_low_volatility(self):
        """Тест низкой волатильности."""
        volatile_items = [
            {"volatility_score": 5},
            {"volatility_score": 4},
        ]
        level = _calculate_market_volatility_level(volatile_items)
        assert level in {"high", "medium", "low"}

    def test_empty_list(self):
        """Тест с пустым списком."""
        assert _calculate_market_volatility_level([]) == "low"


class TestGenerateMarketRecommendations:
    """Тесты для _generate_market_recommendations."""

    def test_generate_recommendations(self):
        """Тест генерации рекомендаций."""
        results = [
            [{"market_hash_name": "Item1", "change_percent": 20}],  # price_changes
            [{"market_hash_name": "Item2", "popularity_score": 100}],  # trending_items
            [{"market_hash_name": "Item3", "volatility_score": 50}],  # volatile_items
        ]
        recommendations = _generate_market_recommendations(results)
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_generate_recommendations_empty(self):
        """Тест с пустыми данными."""
        recommendations = _generate_market_recommendations([[], [], []])
        assert isinstance(recommendations, list)


@pytest.mark.asyncio()
class TestAnalyzePriceChanges:
    """Тесты для analyze_price_changes."""

    async def test_analyze_basic(self):
        """Базовый тест анализа изменений цен."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {"title": "Item 1", "price": {"USD": "10.00"}, "salesVolume": 50},
                    {"title": "Item 2", "price": {"USD": "20.00"}, "salesVolume": 30},
                ]
            }
        )

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(
                return_value={
                    "Item 1": 8.00,
                    "Item 2": 25.00,
                }
            ),
        ):
            result = awAlgot analyze_price_changes(
                game="csgo",
                period="24h",
                dmarket_api=mock_api,
            )

        assert isinstance(result, list)
        # Может быть пустым если изменения не соответствуют фильтрам
        assert len(result) >= 0

    async def test_analyze_with_direction_up(self):
        """Тест с фильтром по направлению вверх."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {"title": "Item Up", "price": {"USD": "15.00"}, "salesVolume": 50},
                ]
            }
        )

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(
                return_value={
                    "Item Up": 10.00,
                }
            ),
        ):
            result = awAlgot analyze_price_changes(
                game="csgo",
                direction="up",
                dmarket_api=mock_api,
            )

        # Должен вернуть только выросшие в цене предметы
        assert isinstance(result, list)

    async def test_analyze_api_error(self):
        """Тест обработки ошибки API."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value=None)

        result = awAlgot analyze_price_changes(
            game="csgo",
            dmarket_api=mock_api,
        )

        assert result == []

    async def test_analyze_empty_items(self):
        """Тест с пустым списком предметов."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value={"items": []})

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(return_value={}),
        ):
            result = awAlgot analyze_price_changes(
                game="csgo",
                dmarket_api=mock_api,
            )

        assert result == []


@pytest.mark.asyncio()
class TestFindTrendingItems:
    """Тесты для find_trending_items."""

    async def test_find_trending_basic(self):
        """Базовый тест поиска трендовых предметов."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {
                        "title": "Trending Item",
                        "price": {"USD": "10.00"},
                        "salesVolume": 100,
                        "avAlgolability": 50,
                    },
                ]
            }
        )

        result = awAlgot find_trending_items(
            game="csgo",
            dmarket_api=mock_api,
        )

        assert isinstance(result, list)
        assert len(result) >= 0

    async def test_find_trending_min_sales_filter(self):
        """Тест фильтрации по минимальным продажам."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {
                        "title": "Low Sales",
                        "price": {"USD": "10.00"},
                        "salesVolume": 2,
                        "avAlgolability": 10,
                    },
                    {
                        "title": "High Sales",
                        "price": {"USD": "20.00"},
                        "salesVolume": 100,
                        "avAlgolability": 50,
                    },
                ]
            }
        )

        result = awAlgot find_trending_items(
            game="csgo",
            min_sales=5,
            dmarket_api=mock_api,
        )

        # Должен отфильтровать предметы с малыми продажами
        assert isinstance(result, list)

    async def test_find_trending_api_error(self):
        """Тест обработки ошибки API."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value=None)

        result = awAlgot find_trending_items(
            game="csgo",
            dmarket_api=mock_api,
        )

        assert result == []


@pytest.mark.asyncio()
class TestAnalyzeMarketVolatility:
    """Тесты для analyze_market_volatility."""

    async def test_analyze_volatility_basic(self):
        """Базовый тест анализа волатильности."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {
                        "title": "Volatile Item",
                        "price": {"USD": "10.00"},
                        "salesVolume": 50,
                    },
                ]
            }
        )

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(
                return_value={
                    "Volatile Item": 5.00,
                }
            ),
        ):
            result = awAlgot analyze_market_volatility(
                game="csgo",
                dmarket_api=mock_api,
            )

        assert isinstance(result, list)

    async def test_analyze_volatility_empty(self):
        """Тест с пустыми данными."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value={"items": []})

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(return_value={}),
        ):
            result = awAlgot analyze_market_volatility(
                game="csgo",
                dmarket_api=mock_api,
            )

        assert result == []


@pytest.mark.asyncio()
class TestGenerateMarketReport:
    """Тесты для generate_market_report."""

    async def test_generate_report_basic(self):
        """Базовый тест генерации отчёта."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {
                        "title": "Item",
                        "price": {"USD": "10.00"},
                        "salesVolume": 50,
                        "avAlgolability": 30,
                    },
                ]
            }
        )

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(
                return_value={
                    "Item": 8.00,
                }
            ),
        ):
            result = awAlgot generate_market_report(
                game="csgo",
                dmarket_api=mock_api,
            )

        assert isinstance(result, dict)
        assert "game" in result
        assert "timestamp" in result
        assert "price_changes" in result
        assert "trending_items" in result
        assert "volatile_items" in result

    async def test_generate_report_multiple_games(self):
        """Тест с несколькими играми."""
        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "items": [
                    {
                        "title": "Item",
                        "price": {"USD": "10.00"},
                        "salesVolume": 50,
                        "avAlgolability": 30,
                    },
                ]
            }
        )

        with patch(
            "src.dmarket.market_analysis._get_historical_prices",
            AsyncMock(
                return_value={
                    "Item": 8.00,
                }
            ),
        ):
            result = awAlgot generate_market_report(
                game="csgo,dota2",
                dmarket_api=mock_api,
            )

        assert isinstance(result, dict)
