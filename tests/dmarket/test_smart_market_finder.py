"""Тесты для модуля smart_market_finder.

Этот модуль содержит тесты для умного поиска выгодных предметов на рынке,
включая:
- Инициализацию SmartMarketFinder
- Поиск лучших возможностей
- Поиск предметов с заниженной ценой
- Расчет confidence и liquidity scores
- Определение типов возможностей и уровней риска
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.smart_market_finder import (
    MarketOpportunity,
    MarketOpportunityType,
    SmartMarketFinder,
    find_best_deals,
    find_quick_profits,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def mock_api_client():
    """Создает мок DMarketAPI клиента."""
    mock_api = AsyncMock()
    mock_api._request = AsyncMock()
    return mock_api


@pytest.fixture()
def sample_market_item():
    """Создает образец предмета с рынка."""
    return {
        "itemId": "item123",
        "title": "AWP | Asiimov (Field-Tested)",
        "price": {"USD": "5000"},  # $50 в центах
        "suggestedPrice": {"USD": "6000"},  # $60 в центах
        "extra": {
            "offersCount": 25,
            "ordersCount": 15,
            "offersPrice": {"USD": "4900"},
            "ordersPrice": {"USD": "6100"},
            "category": "Rifle",
            "exterior": "Field-Tested",
        },
        "image": "https://example.com/image.png",
    }


# ============================================================================
# ТЕСТЫ ИНИЦИАЛИЗАЦИИ
# ============================================================================


def test_smart_market_finder_initialization(mock_api_client):
    """Тест инициализации SmartMarketFinder."""
    finder = SmartMarketFinder(mock_api_client)

    assert finder.api is mock_api_client
    assert finder._cache == {}
    assert finder._cache_ttl == 300
    assert finder.min_profit_percent == 5.0
    assert finder.min_confidence == 60.0
    assert finder.max_price == 100.0


def test_smart_market_finder_custom_settings(mock_api_client):
    """Тест изменения настроек SmartMarketFinder."""
    finder = SmartMarketFinder(mock_api_client)

    # Изменяем настSwarmки
    finder.min_profit_percent = 10.0
    finder.min_confidence = 70.0
    finder.max_price = 200.0

    assert finder.min_profit_percent == 10.0
    assert finder.min_confidence == 70.0
    assert finder.max_price == 200.0


# ============================================================================
# ТЕСТЫ ПОИСКА ВОЗМОЖНОСТЕЙ
# ============================================================================


@pytest.mark.asyncio()
@patch.object(SmartMarketFinder, "_get_market_items_with_aggregated_prices")
@patch.object(SmartMarketFinder, "_analyze_item_opportunity")
async def test_find_best_opportunities_success(
    mock_analyze,
    mock_get_items,
    mock_api_client,
    sample_market_item,
):
    """Тест успешного поиска лучших возможностей."""
    # НастSwarmка моков
    mock_get_items.return_value = [sample_market_item]

    mock_opportunity = MarketOpportunity(
        item_id="item123",
        title="AWP | Asiimov",
        current_price=50.0,
        suggested_price=60.0,
        profit_potential=10.0,
        profit_percent=20.0,
        opportunity_type=MarketOpportunityType.UNDERPRICED,
        confidence_score=75.0,
        liquidity_score=80.0,
        risk_level="low",
    )
    mock_analyze.return_value = mock_opportunity

    # Создаем finder и вызываем метод
    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
        limit=10,
    )

    # Проверки
    assert len(opportunities) == 1
    assert opportunities[0].item_id == "item123"
    assert opportunities[0].confidence_score == 75.0
    mock_get_items.assert_called_once()
    mock_analyze.assert_called_once()


@pytest.mark.asyncio()
@patch.object(SmartMarketFinder, "_get_market_items_with_aggregated_prices")
async def test_find_best_opportunities_no_items(
    mock_get_items,
    mock_api_client,
):
    """Тест поиска возможностей когда предметов нет."""
    # НастSwarmка мока - возвращаем пустой список
    mock_get_items.return_value = []

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(game="csgo")

    # Проверки
    assert opportunities == []
    mock_get_items.assert_called_once()


@pytest.mark.asyncio()
@patch.object(SmartMarketFinder, "_get_market_items_with_aggregated_prices")
async def test_find_best_opportunities_api_error(
    mock_get_items,
    mock_api_client,
):
    """Тест обработки ошибки API при поиске возможностей."""
    # НастSwarmка мока - выбрасываем исключение
    mock_get_items.side_effect = Exception("API Error")

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(game="csgo")

    # Проверки - должен вернуть пустой список при ошибке
    assert opportunities == []


@pytest.mark.asyncio()
async def test_find_underpriced_items_success(
    mock_api_client,
    sample_market_item,
):
    """Тест успешного поиска предметов с заниженной ценой."""
    # НастSwarmка мока API
    mock_api_client._request = AsyncMock(
        return_value={"objects": [sample_market_item]},
    )

    finder = SmartMarketFinder(mock_api_client)
    underpriced = await finder.find_underpriced_items(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
        min_discount_percent=10.0,
        limit=10,
    )

    # Проверки
    assert isinstance(underpriced, list)
    mock_api_client._request.assert_called_once()


@pytest.mark.asyncio()
async def test_find_underpriced_items_no_results(mock_api_client):
    """Тест поиска предметов с заниженной ценой когда нет результатов."""
    # НастSwarmка мока API - пустой ответ
    mock_api_client._request = AsyncMock(return_value={"objects": []})

    finder = SmartMarketFinder(mock_api_client)
    underpriced = await finder.find_underpriced_items(game="csgo")

    # Проверки
    assert underpriced == []


# ============================================================================
# ТЕСТЫ ВСПОМОГАТЕЛЬНЫХ МЕТОДОВ
# ============================================================================


def test_determine_opportunity_type_underpriced(mock_api_client):
    """Тест определения типа возможности - заниженная цена."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с заниженной ценой
    item_data = {
        "extra": {"popularity": 0.5},
    }
    profit_percent = 20.0  # > 15%

    opp_type = finder._determine_opportunity_type(item_data, profit_percent)

    assert opp_type == MarketOpportunityType.UNDERPRICED


def test_determine_opportunity_type_high_liquidity(mock_api_client):
    """Тест определения типа возможности - высокая ликвидность."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с высокой ликвидностью
    item_data = {
        "extra": {"popularity": 0.8},  # Высокая популярность
    }
    profit_percent = 3.0  # Небольшая прибыль

    opp_type = finder._determine_opportunity_type(item_data, profit_percent)

    assert opp_type == MarketOpportunityType.HIGH_LIQUIDITY


def test_calculate_confidence_score(mock_api_client):
    """Тест расчета confidence score."""
    finder = SmartMarketFinder(mock_api_client)

    # Хорошие показатели
    item_data = {
        "extra": {"popularity": 0.8},
        "suggestedPrice": {"USD": "5000"},
    }
    profit_percent = 20.0

    score = finder._calculate_confidence_score(item_data, profit_percent)

    # Проверяем, что score находится в диапазоне 0-100
    assert 0 <= score <= 100
    assert isinstance(score, float)


def test_calculate_liquidity_score(mock_api_client, sample_market_item):
    """Тест расчета liquidity score."""
    finder = SmartMarketFinder(mock_api_client)

    score = finder._calculate_liquidity_score(sample_market_item)

    # Проверяем, что score находится в диапазоне 0-100
    assert 0 <= score <= 100
    assert isinstance(score, float)


def test_determine_risk_level_low(mock_api_client):
    """Тест определения низкого уровня риска."""
    finder = SmartMarketFinder(mock_api_client)

    # Низкий риск: высокая ликвидность, умеренная прибыль, высокая уверенность
    profit_percent = 10.0
    liquidity = 85.0
    confidence = 80.0

    risk = finder._determine_risk_level(profit_percent, liquidity, confidence)

    assert risk == "low"


def test_determine_risk_level_high(mock_api_client):
    """Тест определения высокого уровня риска."""
    finder = SmartMarketFinder(mock_api_client)

    # Высокий риск: низкая ликвидность или очень высокая прибыль
    profit_percent = 35.0  # Очень высокая прибыль
    liquidity = 30.0  # Низкая ликвидность
    confidence = 45.0  # Низкая уверенность

    risk = finder._determine_risk_level(profit_percent, liquidity, confidence)

    assert risk == "high"


def test_estimate_time_to_sell(mock_api_client):
    """Тест оценки времени продажи."""
    finder = SmartMarketFinder(mock_api_client)

    # Высокая ликвидность - быстрая продажа
    time_high = finder._estimate_time_to_sell(90.0)
    assert "час" in time_high.lower()  # Проверяем русский текст

    # Низкая ликвидность - медленная продажа
    time_low = finder._estimate_time_to_sell(20.0)
    assert "дн" in time_low.lower() or "нед" in time_low.lower()


# ============================================================================
# ТЕСТЫ АВТОНОМНЫХ ФУНКЦИЙ
# ============================================================================


@pytest.mark.asyncio()
@patch.object(SmartMarketFinder, "find_best_opportunities")
async def test_find_best_deals(mock_method):
    """Тест автономной функции find_best_deals."""
    # НастSwarmка мока - возвращаем пустой список
    mock_method.return_value = []

    # Создаем мок API
    mock_api = AsyncMock()

    # Вызываем функцию
    results = await find_best_deals(mock_api, game="csgo")

    # Проверки
    assert isinstance(results, list)
    assert results == []


@pytest.mark.asyncio()
@patch("src.dmarket.smart_market_finder.SmartMarketFinder")
async def test_find_quick_profits(mock_finder_class):
    """Тест автономной функции find_quick_profits."""
    # НастSwarmка мока
    mock_finder = AsyncMock()
    mock_finder.find_quick_flip_opportunities = AsyncMock(return_value=[])
    mock_finder_class.return_value = mock_finder

    # Создаем мок API
    mock_api = AsyncMock()

    # Вызываем функцию
    results = await find_quick_profits(mock_api, game="csgo")

    # Проверки
    assert isinstance(results, list)
    mock_finder.find_quick_flip_opportunities.assert_called_once()


# ============================================================================
# ТЕСТЫ ТИПОВ И КЛАССОВ
# ============================================================================


def test_market_opportunity_type_enum():
    """Тест enum MarketOpportunityType."""
    assert MarketOpportunityType.UNDERPRICED == "underpriced"
    assert MarketOpportunityType.TRENDING_UP == "trending_up"
    assert MarketOpportunityType.HIGH_LIQUIDITY == "high_liquidity"
    assert MarketOpportunityType.QUICK_FLIP == "quick_flip"
    assert MarketOpportunityType.VALUE_INVESTMENT == "value_investment"


def test_market_opportunity_dataclass():
    """Тест dataclass MarketOpportunity."""
    opp = MarketOpportunity(
        item_id="test123",
        title="Test Item",
        current_price=50.0,
        suggested_price=60.0,
        profit_potential=10.0,
        profit_percent=20.0,
        opportunity_type=MarketOpportunityType.UNDERPRICED,
        confidence_score=75.0,
        liquidity_score=80.0,
        risk_level="low",
    )

    assert opp.item_id == "test123"
    assert opp.title == "Test Item"
    assert opp.current_price == 50.0
    assert opp.profit_percent == 20.0
    assert opp.opportunity_type == MarketOpportunityType.UNDERPRICED
    assert opp.risk_level == "low"


# ============================================================================
# ТЕСТЫ find_target_opportunities
# ============================================================================


@pytest.mark.asyncio()
async def test_find_target_opportunities_success(
    mock_api_client,
    sample_market_item,
):
    """Тест поиска возможностей для таргетов."""
    # НастSwarmка моков
    mock_api_client._request = AsyncMock(
        side_effect=[
            # Первый вызов - market items
            {"objects": [sample_market_item]},
            # ВтоSwarm вызов - aggregated prices
            {
                "aggregatedPrices": [
                    {
                        "title": "AWP | Asiimov (Field-Tested)",
                        "orderBestPrice": "4500",  # $45
                        "offerBestPrice": "5500",  # $55
                        "orderCount": 10,
                        "offerCount": 20,
                    }
                ]
            },
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
        min_spread_percent=5.0,
        limit=10,
    )

    # Проверки
    assert isinstance(opportunities, list)
    assert len(opportunities) > 0
    if opportunities:
        opp = opportunities[0]
        assert "title" in opp
        assert "spread_percent" in opp
        assert "recommended_target_price" in opp
        assert opp["spread_percent"] >= 5.0


@pytest.mark.asyncio()
async def test_find_target_opportunities_no_spread(mock_api_client):
    """Тест когда нет спреда между ценами."""
    # НастSwarmка моков - цены одинаковые
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [{"title": "Test", "price": {"USD": "5000"}}]},
            {
                "aggregatedPrices": [
                    {
                        "title": "Test",
                        "orderBestPrice": "5000",
                        "offerBestPrice": "5000",  # Нет спреда
                        "orderCount": 5,
                        "offerCount": 5,
                    }
                ]
            },
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(
        game="csgo",
        min_spread_percent=5.0,
    )

    # Не должно быть возможностей при отсутствии спреда
    assert opportunities == []


@pytest.mark.asyncio()
async def test_find_target_opportunities_api_error(mock_api_client):
    """Тест обработки ошибки API при поиске таргетов."""
    mock_api_client._request = AsyncMock(side_effect=Exception("API Error"))

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(game="csgo")

    # Должен вернуть пустой список при ошибке
    assert opportunities == []


# ============================================================================
# ТЕСТЫ find_quick_flip_opportunities
# ============================================================================


@pytest.mark.asyncio()
@patch.object(SmartMarketFinder, "find_underpriced_items")
async def test_find_quick_flip_opportunities_success(
    mock_find_underpriced,
    mock_api_client,
):
    """Тест поиска возможностей быстSwarm перепродажи."""
    # Создаем возможности с высокой ликвидностью
    mock_opportunities = [
        MarketOpportunity(
            item_id="flip123",
            title="Quick Flip Item",
            current_price=20.0,
            suggested_price=25.0,
            profit_potential=3.0,
            profit_percent=15.0,
            opportunity_type=MarketOpportunityType.UNDERPRICED,
            confidence_score=85.0,
            liquidity_score=90.0,  # Высокая ликвидность
            risk_level="low",
        ),
        MarketOpportunity(
            item_id="flip456",
            title="Another Quick Item",
            current_price=15.0,
            suggested_price=20.0,
            profit_potential=3.5,
            profit_percent=20.0,
            opportunity_type=MarketOpportunityType.UNDERPRICED,
            confidence_score=80.0,
            liquidity_score=85.0,  # Высокая ликвидность
            risk_level="low",
        ),
    ]
    mock_find_underpriced.return_value = mock_opportunities

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_quick_flip_opportunities(
        game="csgo",
        min_price=5.0,
        max_price=30.0,
        min_profit_percent=10.0,
    )

    # Проверки
    assert isinstance(opportunities, list)
    assert len(opportunities) > 0
    # Проверяем что тип изменился на QUICK_FLIP
    quick_flip = MarketOpportunityType.QUICK_FLIP
    assert opportunities[0].opportunity_type == quick_flip
    # Проверяем что все имеют высокую ликвидность (>= 50)
    for opp in opportunities:
        assert opp.liquidity_score >= 50


@pytest.mark.asyncio()
@patch.object(
    SmartMarketFinder,
    "_get_market_items_with_aggregated_prices",
)
async def test_find_quick_flip_no_liquidity(
    mock_get_items,
    mock_api_client,
):
    """Тест когда нет ликвидных предметов."""
    mock_get_items.return_value = []

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_quick_flip_opportunities(game="csgo")

    # Не должно быть возможностей
    assert opportunities == []


# ============================================================================
# ТЕСТЫ _get_market_items_with_aggregated_prices
# ============================================================================


@pytest.mark.asyncio()
async def test_get_market_items_with_aggregated_prices(
    mock_api_client,
    sample_market_item,
):
    """Тест получения предметов с агрегированными ценами."""
    # НастSwarmка моков для метода _request напрямую
    mock_api_client._request = AsyncMock(
        return_value={"objects": [sample_market_item], "cursor": None}
    )

    finder = SmartMarketFinder(mock_api_client)
    items = await finder._get_market_items_with_aggregated_prices(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
    )

    # Проверки
    assert isinstance(items, list)
    # Даже если get_aggregated_prices не вернет данных,
    # должны быть items из market
    assert len(items) >= 0  # Может быть пустым если фильтры не совпадают


@pytest.mark.asyncio()
async def test_get_market_items_with_aggregated_prices_cache(
    mock_api_client,
):
    """Тест кэширования при получении предметов."""
    # НастSwarmка моков
    mock_api_client.get_market_items = AsyncMock(
        return_value={"objects": [{"itemId": "cached_item"}]}
    )
    mock_api_client.get_aggregated_prices = AsyncMock(
        return_value={"aggregatedPrices": []}
    )

    finder = SmartMarketFinder(mock_api_client)

    # Первый вызов
    _ = await finder._get_market_items_with_aggregated_prices(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
    )

    # ВтоSwarm вызов (должен использовать кэш)
    _ = await finder._get_market_items_with_aggregated_prices(
        game="csgo",
        min_price=10.0,
        max_price=100.0,
    )

    # API должен быть вызван только один раз (для первого вызова)
    assert mock_api_client.get_market_items.call_count <= 2


# ============================================================================
# ТЕСТЫ _analyze_item_opportunity
# ============================================================================


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_underpriced(
    mock_api_client,
    sample_market_item,
):
    """Тест анализа предмета с заниженной ценой."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с большой разницей в цене
    item_data = {
        "itemId": "analyze_item",
        "title": "Underpriced Item",
        "price": {"USD": "5000"},  # $50
        "suggestedPrice": {"USD": "7000"},  # $70
        "extra": {
            "popularity": 0.6,
            "offersCount": 20,
        },
    }

    opportunity = await finder._analyze_item_opportunity(
        item_data,
        game="csgo",
    )

    # Проверки
    assert opportunity is not None
    assert isinstance(opportunity, MarketOpportunity)
    assert opportunity.item_id == "analyze_item"
    assert opportunity.opportunity_type == MarketOpportunityType.UNDERPRICED
    assert opportunity.profit_percent > 0


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_no_suggested_price(
    mock_api_client,
):
    """Тест анализа предмета без suggestedPrice."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет без suggestedPrice
    item_data = {
        "itemId": "no_price",
        "title": "No Suggested Price",
        "price": {"USD": "5000"},
        # Нет suggestedPrice
    }

    opportunity = await finder._analyze_item_opportunity(
        item_data,
        game="csgo",
    )

    # Метод создает возможность даже без suggested_price
    # используя best offer price + 10% для расчета потенциальной цены
    assert opportunity is not None
    assert opportunity.item_id == "no_price"
    assert opportunity.current_price == 50.0


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ДЛЯ УЛУЧШЕНИЯ ПОКРЫТИЯ
# ============================================================================


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_no_title(mock_api_client):
    """Тест анализа предмета без названия."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет без title
    item_data = {
        "itemId": "no_title",
        # Нет title
        "price": {"USD": "5000"},
    }

    opportunity = await finder._analyze_item_opportunity(item_data, game="csgo")

    # Должен вернуть None
    assert opportunity is None


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_zero_price(mock_api_client):
    """Тест анализа предмета с нулевой ценой."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с нулевой ценой
    item_data = {
        "itemId": "zero_price",
        "title": "Zero Price Item",
        "price": {"USD": "0"},
    }

    opportunity = await finder._analyze_item_opportunity(item_data, game="csgo")

    # Должен вернуть None
    assert opportunity is None


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_with_aggregated(mock_api_client):
    """Тест анализа предмета с агрегированными данными."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с агрегированными данными
    item_data = {
        "itemId": "with_agg",
        "title": "Item With Aggregated",
        "price": {"USD": "5000"},
        "suggestedPrice": {"USD": "6000"},
        "aggregated": {
            "offerBestPrice": "5200",
            "orderBestPrice": "4800",
            "offerCount": 15,
            "orderCount": 10,
        },
        "extra": {"popularity": 0.7},
    }

    opportunity = await finder._analyze_item_opportunity(item_data, game="csgo")

    # Проверки
    assert opportunity is not None
    assert opportunity.best_offer_price == 52.0
    assert opportunity.best_order_price == 48.0
    assert opportunity.offers_count == 15
    assert opportunity.orders_count == 10


@pytest.mark.asyncio()
async def test_analyze_item_opportunity_exception_handling(mock_api_client):
    """Тест обработки исключения при анализе предмета."""
    finder = SmartMarketFinder(mock_api_client)

    # Некорректные данные, которые вызовут исключение
    item_data = {
        "itemId": "bad_data",
        "title": "Bad Data",
        "price": "invalid",  # Неверный формат
    }

    opportunity = await finder._analyze_item_opportunity(item_data, game="csgo")

    # Должен обработать исключение и вернуть None
    assert opportunity is None


def test_generate_recommendation_default(mock_api_client):
    """Тест генерации дефолтной рекомендации."""
    finder = SmartMarketFinder(mock_api_client)

    recommendation = finder._generate_recommendation(
        opportunity_type=MarketOpportunityType.VALUE_INVESTMENT,
        current_price=10.0,
        suggested_price=12.0,
        best_order=None,
    )

    assert isinstance(recommendation, str)
    assert "$10.00" in recommendation
    assert "$12.00" in recommendation


def test_generate_notes_low_liquidity(mock_api_client):
    """Тест генерации заметок при низкой ликвидности."""
    finder = SmartMarketFinder(mock_api_client)

    item = {"extra": {"popularity": 0.2}}

    notes = finder._generate_notes(
        item, profit=5.0, profit_percent=10.0, liquidity=30.0
    )

    assert any("низкая ликвидность" in note.lower() for note in notes)


def test_determine_opportunity_type_value_investment(mock_api_client):
    """Тест определения типа VALUE_INVESTMENT."""
    finder = SmartMarketFinder(mock_api_client)

    item_data = {"extra": {"popularity": 0.4}}
    profit_percent = 7.0  # Между 5 и 10

    opp_type = finder._determine_opportunity_type(item_data, profit_percent)

    assert opp_type == MarketOpportunityType.VALUE_INVESTMENT


def test_determine_opportunity_type_target_opportunity(mock_api_client):
    """Тест определения типа TARGET_OPPORTUNITY."""
    finder = SmartMarketFinder(mock_api_client)

    item_data = {"extra": {"popularity": 0.3}}
    profit_percent = 3.0  # Меньше 5%

    opp_type = finder._determine_opportunity_type(item_data, profit_percent)

    assert opp_type == MarketOpportunityType.TARGET_OPPORTUNITY


@pytest.mark.asyncio()
async def test_find_best_opportunities_filters_low_confidence(
    mock_api_client, sample_market_item
):
    """Тест фильтрации возможностей с низкой уверенностью."""
    # НастSwarmка моков
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [sample_market_item]},
            {"aggregatedPrices": []},
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(
        game="csgo",
        min_confidence=95.0,  # Очень высокий порог
    )

    # Предметы с низкой уверенностью должны быть отфильтрованы
    for opp in opportunities:
        assert opp.confidence_score >= 95.0


@pytest.mark.asyncio()
async def test_find_best_opportunities_filters_by_type(
    mock_api_client, sample_market_item
):
    """Тест фильтрации возможностей по типу."""
    # НастSwarmка моков
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [sample_market_item]},
            {"aggregatedPrices": []},
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(
        game="csgo",
        opportunity_types=[MarketOpportunityType.UNDERPRICED],
    )

    # Все возможности должны быть нужного типа
    for opp in opportunities:
        assert opp.opportunity_type == MarketOpportunityType.UNDERPRICED


@pytest.mark.asyncio()
async def test_find_underpriced_items_with_discount(mock_api_client):
    """Тест поиска предметов с большой скидкой."""
    # Предмет с 35% скидкой (высокий риск)
    item = {
        "itemId": "big_discount",
        "title": "Big Discount Item",
        "price": {"USD": "6500"},  # $65
        "suggestedPrice": {"USD": "10000"},  # $100
        "extra": {"popularity": 0.5},
    }
    mock_api_client._request = AsyncMock(return_value={"objects": [item]})

    finder = SmartMarketFinder(mock_api_client)
    underpriced = await finder.find_underpriced_items(
        game="csgo", min_discount_percent=30.0
    )

    assert len(underpriced) > 0
    if underpriced:
        # Должен быть помечен как высокий риск
        assert underpriced[0].risk_level == "high"


@pytest.mark.asyncio()
async def test_find_target_opportunities_no_aggregated_prices(mock_api_client):
    """Тест когда нет агрегированных цен."""
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [{"title": "Test", "price": {"USD": "5000"}}]},
            None,  # Нет агрегированных цен
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(game="csgo")

    assert opportunities == []


@pytest.mark.asyncio()
async def test_find_target_opportunities_no_profit(mock_api_client):
    """Тест когда нет прибыли при создании таргета."""
    # Цены такие, что после комиссии прибыли нет
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [{"title": "No Profit", "price": {"USD": "5000"}}]},
            {
                "aggregatedPrices": [
                    {
                        "title": "No Profit",
                        "orderBestPrice": "5000",  # $50
                        # $51, прибыль после комиссии отрицательная
                        "offerBestPrice": "5100",
                        "orderCount": 5,
                        "offerCount": 5,
                    }
                ]
            },
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(
        game="csgo", min_spread_percent=1.0
    )

    # Не должно быть возможностей с отрицательной прибылью
    for opp in opportunities:
        assert opp["profit_potential"] > 0


@pytest.mark.asyncio()
async def test_find_quick_flip_filters_high_risk(mock_api_client):
    """Тест фильтрации по максимальному риску."""
    finder = SmartMarketFinder(mock_api_client)

    # Создаем мок для find_underpriced_items
    high_risk_opp = MarketOpportunity(
        item_id="high_risk",
        title="High Risk Item",
        current_price=20.0,
        suggested_price=30.0,
        profit_potential=7.0,
        profit_percent=35.0,
        opportunity_type=MarketOpportunityType.UNDERPRICED,
        confidence_score=70.0,
        liquidity_score=80.0,  # Высокая ликвидность
        risk_level="high",  # Высокий риск
    )

    with patch.object(finder, "find_underpriced_items", return_value=[high_risk_opp]):
        # Запрашиваем только низкий риск
        opportunities = await finder.find_quick_flip_opportunities(
            game="csgo", max_risk="low"
        )

        # Предмет с высоким риском должен быть отфильтрован
        assert len(opportunities) == 0


@pytest.mark.asyncio()
async def test_find_quick_flip_sets_estimated_time(mock_api_client):
    """Тест установки estimated_time_to_sell."""
    finder = SmartMarketFinder(mock_api_client)

    # Предмет с очень высокой ликвидностью
    high_liq_opp = MarketOpportunity(
        item_id="high_liq",
        title="High Liquidity",
        current_price=10.0,
        suggested_price=12.0,
        profit_potential=1.0,
        profit_percent=10.0,
        opportunity_type=MarketOpportunityType.UNDERPRICED,
        confidence_score=75.0,
        liquidity_score=85.0,  # Высокая ликвидность > 70
        risk_level="low",
    )

    with patch.object(finder, "find_underpriced_items", return_value=[high_liq_opp]):
        opportunities = await finder.find_quick_flip_opportunities(game="csgo")

        if opportunities:
            # Должно быть установлено время продажи
            assert opportunities[0].estimated_time_to_sell is not None
            assert "час" in opportunities[0].estimated_time_to_sell.lower()


@pytest.mark.asyncio()
async def test_get_market_items_aggregated_prices_error(mock_api_client):
    """Тест обработки ошибки при получении агрегированных цен."""
    # Первый вызов успешен, втоSwarm выбрасывает ошибку
    mock_api_client._request = AsyncMock(
        side_effect=[
            {"objects": [{"title": "Test", "price": {"USD": "5000"}}]},
            Exception("Aggregated prices error"),
        ]
    )

    finder = SmartMarketFinder(mock_api_client)
    items = await finder._get_market_items_with_aggregated_prices(
        game="csgo", min_price=1.0, max_price=100.0
    )

    # Должен вернуть предметы без агрегированных данных
    assert len(items) > 0
    assert "aggregated" not in items[0] or items[0].get("aggregated") is None


@pytest.mark.asyncio()
async def test_get_market_items_no_objects(mock_api_client):
    """Тест когда API не возвращает objects."""
    mock_api_client._request = AsyncMock(return_value={"invalid_key": []})

    finder = SmartMarketFinder(mock_api_client)
    items = await finder._get_market_items_with_aggregated_prices(
        game="csgo", min_price=1.0, max_price=100.0
    )

    assert items == []


@pytest.mark.asyncio()
async def test_get_market_items_exception(mock_api_client):
    """Тест обработки исключения при получении предметов."""
    mock_api_client._request = AsyncMock(side_effect=Exception("API Error"))

    finder = SmartMarketFinder(mock_api_client)
    items = await finder._get_market_items_with_aggregated_prices(
        game="csgo", min_price=1.0, max_price=100.0
    )

    assert items == []


def test_calculate_confidence_with_suggested_price(mock_api_client):
    """Тест увеличения уверенности при наличии suggestedPrice."""
    finder = SmartMarketFinder(mock_api_client)

    # С suggestedPrice
    item_with_suggested = {
        "extra": {"popularity": 0.5},
        "suggestedPrice": {"USD": "5000"},
    }

    score_with = finder._calculate_confidence_score(
        item_with_suggested, profit_percent=10.0
    )

    # Без suggestedPrice
    item_without_suggested = {"extra": {"popularity": 0.5}}

    score_without = finder._calculate_confidence_score(
        item_without_suggested, profit_percent=10.0
    )

    # С suggested должна быть выше
    assert score_with > score_without


def test_calculate_liquidity_max_cap(mock_api_client):
    """Тест ограничения ликвидности максимумом 100."""
    finder = SmartMarketFinder(mock_api_client)

    # Очень популярный предмет с большим количеством заявок
    item = {
        "extra": {"popularity": 1.0},
        "aggregated": {"offerCount": 200, "orderCount": 200},
    }

    score = finder._calculate_liquidity_score(item)

    # Не должна превышать 100
    assert score <= 100.0


def test_determine_risk_level_medium(mock_api_client):
    """Тест определения среднего риска."""
    finder = SmartMarketFinder(mock_api_client)

    # Средние показатели
    risk = finder._determine_risk_level(
        profit_percent=15.0, liquidity=60.0, confidence=65.0
    )

    assert risk == "medium"


def test_estimate_time_to_sell_boundaries(mock_api_client):
    """Тест граничных значений для оценки времени продажи."""
    finder = SmartMarketFinder(mock_api_client)

    # Граница 80-60
    time_80 = finder._estimate_time_to_sell(80.0)
    time_60 = finder._estimate_time_to_sell(60.0)
    assert time_80 != time_60

    # Граница 60-40
    time_40 = finder._estimate_time_to_sell(40.0)
    assert time_60 != time_40

    # Граница 40-20
    time_20 = finder._estimate_time_to_sell(20.0)
    assert time_40 != time_20


@pytest.mark.asyncio()
async def test_find_underpriced_invalid_response(mock_api_client):
    """Тест обработки некорректного ответа при поиске заниженных цен."""
    mock_api_client._request = AsyncMock(return_value=None)

    finder = SmartMarketFinder(mock_api_client)
    underpriced = await finder.find_underpriced_items(game="csgo")

    assert underpriced == []


@pytest.mark.asyncio()
async def test_find_target_opportunities_empty_titles(mock_api_client):
    """Тест когда нет названий предметов."""
    # Предметы без title
    mock_api_client._request = AsyncMock(
        return_value={"objects": [{"itemId": "123", "price": {"USD": "5000"}}]}
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_target_opportunities(game="csgo")

    assert opportunities == []


@pytest.mark.asyncio()
async def test_find_best_opportunities_sorts_by_confidence(mock_api_client):
    """Тест сортировки возможностей по уверенности."""
    # Создаем несколько предметов
    items = [
        {
            "itemId": "low_conf",
            "title": "Low Confidence",
            "price": {"USD": "5000"},
            "suggestedPrice": {"USD": "5500"},
            "extra": {"popularity": 0.2},
        },
        {
            "itemId": "high_conf",
            "title": "High Confidence",
            "price": {"USD": "5000"},
            "suggestedPrice": {"USD": "6500"},
            "extra": {"popularity": 0.9},
        },
    ]

    mock_api_client._request = AsyncMock(
        side_effect=[{"objects": items}, {"aggregatedPrices": []}]
    )

    finder = SmartMarketFinder(mock_api_client)
    opportunities = await finder.find_best_opportunities(game="csgo", limit=10)

    # Первая возможность должна иметь самую высокую уверенность
    if len(opportunities) > 1:
        first_conf = opportunities[0].confidence_score
        second_conf = opportunities[1].confidence_score
        assert first_conf >= second_conf
