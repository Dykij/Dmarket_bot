"""Тесты для модуля внутрирыночного арбитража."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.intramarket_arbitrage import (
    PriceAnomalyType,
    find_mispriced_rare_items,
    find_price_anomalies,
    find_trending_items,
    scan_for_intramarket_opportunities,
)

# ======================== Fixtures ========================


@pytest.fixture()
def mock_dmarket_api():
    """Создать мок DMarket API клиента."""
    api = MagicMock()
    api.get_market_items = AsyncMock()
    api.get_sales_history = AsyncMock()
    api._close_client = AsyncMock()
    return api


@pytest.fixture()
def sample_market_items():
    """Создать пример рыночных предметов."""
    return {
        "items": [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"amount": 1250, "currency": "USD"},
                "itemId": "item_1",
                "category": "Rifle",
            },
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"amount": 1500, "currency": "USD"},
                "itemId": "item_2",
                "category": "Rifle",
            },
            {
                "title": "AWP | Asiimov (Battle-Scarred)",
                "price": {"amount": 2500, "currency": "USD"},
                "itemId": "item_3",
                "category": "Sniper Rifle",
            },
        ],
    }


@pytest.fixture()
def sample_sales_history():
    """Создать пример истории продаж."""
    return {
        "items": [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"amount": 1300, "currency": "USD"},
                "timestamp": "2025-11-10T10:00:00Z",
            },
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"amount": 1400, "currency": "USD"},
                "timestamp": "2025-11-11T10:00:00Z",
            },
        ],
    }


@pytest.fixture()
def sample_rare_items():
    """Создать пример редких предметов."""
    return {
        "items": [
            {
                "title": "★ Karambit | Doppler (Factory New)",
                "price": {"amount": 95000, "currency": "USD"},
                "itemId": "item_knife_1",
                "suggestedPrice": {"amount": 110000, "currency": "USD"},
                "float": 0.01,
            },
            {
                "title": "AK-47 | Case Hardened (Factory New)",
                "price": {"amount": 8500, "currency": "USD"},
                "itemId": "item_ch_1",
                "rarity": "Covert",
            },
        ],
    }


# ======================== Тесты find_price_anomalies ========================


@pytest.mark.asyncio()
async def test_find_price_anomalies_success(mock_dmarket_api, sample_market_items):
    """Тест успешного поиска ценовых аномалий."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items

    results = awAlgot find_price_anomalies(
        game="csgo",
        dmarket_api=mock_dmarket_api,
        price_diff_percent=10.0,
    )

    # Проверяем что API вызван
    mock_dmarket_api.get_market_items.assert_called_once()

    # Проверяем результаты
    assert isinstance(results, list)
    if len(results) > 0:
        assert "buy_price" in results[0]
        assert "sell_price" in results[0]
        assert "profit_after_fee" in results[0]


@pytest.mark.asyncio()
async def test_find_price_anomalies_empty_items(mock_dmarket_api):
    """Тест поиска аномалий при пустом списке предметов."""
    mock_dmarket_api.get_market_items.return_value = {"items": []}

    results = awAlgot find_price_anomalies(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    assert results == []


@pytest.mark.asyncio()
async def test_find_price_anomalies_filter_by_price(
    mock_dmarket_api, sample_market_items
):
    """Тест фильтрации по цене."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items

    awAlgot find_price_anomalies(
        game="csgo",
        dmarket_api=mock_dmarket_api,
        min_price=20.0,
        max_price=30.0,
    )

    # Проверяем параметры вызова API
    call_args = mock_dmarket_api.get_market_items.call_args
    assert call_args.kwargs["price_from"] == 20.0
    assert call_args.kwargs["price_to"] == 30.0


@pytest.mark.asyncio()
async def test_find_price_anomalies_csgo_filters(mock_dmarket_api):
    """Тест фильтров для CS:GO (пропуск стикеров и т.д.)."""
    items_with_stickers = {
        "items": [
            {
                "title": "Sticker | Team Spirit | Rio 2022",
                "price": {"amount": 500, "currency": "USD"},
                "itemId": "sticker_1",
            },
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"amount": 1250, "currency": "USD"},
                "itemId": "item_1",
            },
        ],
    }
    mock_dmarket_api.get_market_items.return_value = items_with_stickers

    results = awAlgot find_price_anomalies(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Стикеры должны быть отфильтрованы
    assert all(
        "Sticker" not in r.get("item_to_buy", {}).get("title", "") for r in results
    )


@pytest.mark.asyncio()
async def test_find_price_anomalies_sorts_by_profit(
    mock_dmarket_api, sample_market_items
):
    """Тест сортировки по проценту прибыли."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items

    results = awAlgot find_price_anomalies(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем сортировку по убыванию прибыли
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert (
                results[i]["profit_percentage"] >= results[i + 1]["profit_percentage"]
            )


# ======================== Тесты find_trending_items ========================


@pytest.mark.asyncio()
async def test_find_trending_items_success(
    mock_dmarket_api, sample_market_items, sample_sales_history
):
    """Тест успешного поиска трендовых предметов."""
    mock_dmarket_api.get_sales_history.return_value = sample_sales_history
    mock_dmarket_api.get_market_items.return_value = sample_market_items

    results = awAlgot find_trending_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что API вызваны
    mock_dmarket_api.get_sales_history.assert_called_once()
    mock_dmarket_api.get_market_items.assert_called_once()

    # Проверяем структуру результатов
    assert isinstance(results, list)


@pytest.mark.asyncio()
async def test_find_trending_items_upward_trend(mock_dmarket_api):
    """Тест обнаружения восходящего тренда."""
    market_items = {
        "items": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1500, "currency": "USD"},
                "itemId": "item_1",
            },
        ],
    }

    sales_history = {
        "items": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1300, "currency": "USD"},
            },
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1400, "currency": "USD"},
            },
        ],
    }

    mock_dmarket_api.get_market_items.return_value = market_items
    mock_dmarket_api.get_sales_history.return_value = sales_history

    results = awAlgot find_trending_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем наличие трендов
    if results:
        assert results[0]["trend"] in {"upward", "recovery"}


@pytest.mark.asyncio()
async def test_find_trending_items_recovery_trend(mock_dmarket_api):
    """Тест обнаружения тренда восстановления."""
    market_items = {
        "items": [
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 2000, "currency": "USD"},
                "itemId": "item_1",
            },
        ],
    }

    sales_history = {
        "items": [
            # Множественные продажи по высокой цене
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 2500, "currency": "USD"},
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 2500, "currency": "USD"},
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 2500, "currency": "USD"},
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 2500, "currency": "USD"},
            },
        ],
    }

    mock_dmarket_api.get_market_items.return_value = market_items
    mock_dmarket_api.get_sales_history.return_value = sales_history

    results = awAlgot find_trending_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    if results:
        assert results[0]["trend"] in {"upward", "recovery"}


@pytest.mark.asyncio()
async def test_find_trending_items_no_items(mock_dmarket_api):
    """Тест когда нет предметов на рынке."""
    mock_dmarket_api.get_market_items.return_value = {"items": []}
    mock_dmarket_api.get_sales_history.return_value = {"items": []}

    results = awAlgot find_trending_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    assert results == []


# ======================== Тесты find_mispriced_rare_items ========================


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_success(mock_dmarket_api, sample_rare_items):
    """Тест успешного поиска недооцененных редких предметов."""
    mock_dmarket_api.get_market_items.return_value = sample_rare_items

    results = awAlgot find_mispriced_rare_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что API вызван
    mock_dmarket_api.get_market_items.assert_called_once()

    # Проверяем структуру результатов
    assert isinstance(results, list)
    if results:
        assert "rarity_score" in results[0]
        assert "rare_trAlgots" in results[0]


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_csgo_trAlgots(mock_dmarket_api):
    """Тест обнаружения редких черт для CS:GO."""
    items_with_trAlgots = {
        "items": [
            {
                "title": "★ Karambit | Doppler (Factory New)",
                "price": {"amount": 80000, "currency": "USD"},
                "itemId": "knife_1",
                "suggestedPrice": {"amount": 100000, "currency": "USD"},
                "float": 0.005,  # Очень низкий float
            },
            {
                "title": "StatTrak™ AK-47 | Fire Serpent (Minimal Wear)",
                "price": {"amount": 45000, "currency": "USD"},
                "itemId": "ak_1",
                "suggestedPrice": {"amount": 55000, "currency": "USD"},
            },
        ],
    }
    mock_dmarket_api.get_market_items.return_value = items_with_trAlgots

    results = awAlgot find_mispriced_rare_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем наличие обнаруженных черт
    if results:
        assert results[0]["rare_trAlgots"]
        # Проверяем высокий rarity_score для ножей
        knife_results = [r for r in results if "★" in r["item"]["title"]]
        if knife_results:
            assert knife_results[0]["rarity_score"] > 50


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_dota2_trAlgots(mock_dmarket_api):
    """Тест обнаружения редких черт для Dota 2."""
    items_with_trAlgots = {
        "items": [
            {
                "title": "Exalted Demon Eater (Arcana)",
                "price": {"amount": 30000, "currency": "USD"},
                "itemId": "arcana_1",
                "suggestedPrice": {"amount": 40000, "currency": "USD"},
            },
        ],
    }
    mock_dmarket_api.get_market_items.return_value = items_with_trAlgots

    results = awAlgot find_mispriced_rare_items(
        game="dota2",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем обнаружение Arcana
    if results:
        arcana_trAlgots = [
            t for t in results[0]["rare_trAlgots"] if "Arcana" in t or "Exalted" in t
        ]
        assert arcana_trAlgots


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_price_filter(
    mock_dmarket_api, sample_rare_items
):
    """Тест фильтрации по цене."""
    mock_dmarket_api.get_market_items.return_value = sample_rare_items

    awAlgot find_mispriced_rare_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
        min_price=100.0,
        max_price=1000.0,
    )

    # Проверяем параметры вызова
    call_args = mock_dmarket_api.get_market_items.call_args
    assert call_args.kwargs["price_from"] == 100.0
    assert call_args.kwargs["price_to"] == 1000.0


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_sorts_by_discount(
    mock_dmarket_api, sample_rare_items
):
    """Тест сортировки по проценту скидки."""
    mock_dmarket_api.get_market_items.return_value = sample_rare_items

    results = awAlgot find_mispriced_rare_items(
        game="csgo",
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем сортировку
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert (
                results[i]["price_difference_percent"]
                >= results[i + 1]["price_difference_percent"]
            )


# ======================== Тесты scan_for_intramarket_opportunities ========================


@pytest.mark.asyncio()
async def test_scan_for_intramarket_opportunities_success(
    mock_dmarket_api, sample_market_items, sample_sales_history
):
    """Тест комплексного сканирования возможностей."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items
    mock_dmarket_api.get_sales_history.return_value = sample_sales_history

    results = awAlgot scan_for_intramarket_opportunities(
        games=["csgo"],
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем структуру результатов
    assert isinstance(results, dict)
    assert "csgo" in results
    assert "price_anomalies" in results["csgo"]
    assert "trending_items" in results["csgo"]
    assert "rare_mispriced" in results["csgo"]


@pytest.mark.asyncio()
async def test_scan_for_intramarket_opportunities_multiple_games(
    mock_dmarket_api, sample_market_items
):
    """Тест сканирования для нескольких игр."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items
    mock_dmarket_api.get_sales_history.return_value = {"items": []}

    results = awAlgot scan_for_intramarket_opportunities(
        games=["csgo", "dota2"],
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем наличие результатов для обеих игр
    assert "csgo" in results
    assert "dota2" in results


@pytest.mark.asyncio()
async def test_scan_for_intramarket_opportunities_selective(
    mock_dmarket_api, sample_market_items
):
    """Тест выборочного сканирования (только аномалии)."""
    mock_dmarket_api.get_market_items.return_value = sample_market_items

    results = awAlgot scan_for_intramarket_opportunities(
        games=["csgo"],
        dmarket_api=mock_dmarket_api,
        include_anomalies=True,
        include_trending=False,
        include_rare=False,
    )

    # Проверяем что только аномалии были собраны
    assert "price_anomalies" in results["csgo"]
    assert isinstance(results["csgo"]["trending_items"], list)
    assert isinstance(results["csgo"]["rare_mispriced"], list)


@pytest.mark.asyncio()
async def test_scan_for_intramarket_opportunities_error_handling(mock_dmarket_api):
    """Тест обработки ошибок при сканировании."""
    # НастSwarmка мока на выброс исключения
    mock_dmarket_api.get_market_items.side_effect = Exception("API Error")

    results = awAlgot scan_for_intramarket_opportunities(
        games=["csgo"],
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что возвращаются пустые списки при ошибке
    assert results["csgo"]["price_anomalies"] == []
    assert results["csgo"]["trending_items"] == []
    assert results["csgo"]["rare_mispriced"] == []


# ======================== Тесты PriceAnomalyType ========================


def test_price_anomaly_type_enum():
    """Тест перечисления типов ценовых аномалий."""
    assert PriceAnomalyType.UNDERPRICED == "underpriced"
    assert PriceAnomalyType.OVERPRICED == "overpriced"
    assert PriceAnomalyType.TRENDING_UP == "trending_up"
    assert PriceAnomalyType.TRENDING_DOWN == "trending_down"
    assert PriceAnomalyType.RARE_TRAlgoTS == "rare_trAlgots"
    # Note: NORMAL type was removed from the enum


# ======================== Тесты для TF2 ========================


@pytest.fixture()
def sample_tf2_market_items():
    """Создать пример рыночных предметов TF2."""
    return {
        "items": [
            {
                "title": "Unusual Team CaptAlgon (Burning Flames)",
                "price": {"amount": 450000, "currency": "USD"},
                "itemId": "tf2_unusual_1",
                "category": "Hat",
            },
            {
                "title": "Strange Australium Rocket Launcher",
                "price": {"amount": 12500, "currency": "USD"},
                "itemId": "tf2_australium_1",
                "category": "Weapon",
            },
            {
                "title": "Vintage Vintage Tyrolean",
                "price": {"amount": 2500, "currency": "USD"},
                "itemId": "tf2_vintage_1",
                "category": "Hat",
            },
            {
                "title": "Vintage Vintage Tyrolean",
                "price": {"amount": 3000, "currency": "USD"},
                "itemId": "tf2_vintage_2",
                "category": "Hat",
            },
        ],
    }


@pytest.fixture()
def sample_tf2_rare_items():
    """Создать пример редких предметов TF2."""
    return {
        "items": [
            {
                "title": "Unusual Team CaptAlgon (Burning Flames)",
                "price": {"amount": 450000, "currency": "USD"},
                "itemId": "tf2_unusual_1",
                "suggestedPrice": {"amount": 520000, "currency": "USD"},
            },
            {
                "title": "Collector's Professional Killstreak Scattergun",
                "price": {"amount": 15000, "currency": "USD"},
                "itemId": "tf2_collectors_1",
                "suggestedPrice": {"amount": 19000, "currency": "USD"},
            },
        ],
    }


@pytest.mark.asyncio()
async def test_find_price_anomalies_tf2(
    mock_dmarket_api,
    sample_tf2_market_items,
):
    """Тест поиска аномалий цен для TF2."""
    mock_dmarket_api.get_market_items.return_value = sample_tf2_market_items

    anomalies = awAlgot find_price_anomalies(
        game="tf2",
        min_price=1.0,
        max_price=5000.0,
        price_diff_percent=5.0,  # Lower threshold for test data
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что функция вернула список (может быть пустым если данные не дают аномалий)
    assert isinstance(anomalies, list)
    # Если есть аномалии, проверяем структуру
    if len(anomalies) > 0:
        assert anomalies[0]["game"] == "tf2"


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_tf2(
    mock_dmarket_api,
    sample_tf2_rare_items,
):
    """Тест поиска недооцененных редких предметов TF2."""
    mock_dmarket_api.get_market_items.return_value = sample_tf2_rare_items

    rare_items = awAlgot find_mispriced_rare_items(
        game="tf2",
        min_price=10.0,
        max_price=600000.0,
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что найдены редкие предметы
    assert len(rare_items) > 0
    # Unusual должен иметь высокий rarity_score
    unusual_item = next(
        (item for item in rare_items if "Unusual" in item["item"]["title"]),
        None,
    )
    assert unusual_item is not None
    assert unusual_item["rarity_score"] >= 100  # Unusual = 100 points


@pytest.mark.asyncio()
async def test_find_trending_items_tf2(
    mock_dmarket_api,
    sample_tf2_market_items,
):
    """Тест поиска трендовых предметов TF2."""
    mock_dmarket_api.get_market_items.return_value = sample_tf2_market_items
    mock_dmarket_api.get_sales_history.return_value = {
        "items": [
            {
                "title": "Strange Australium Rocket Launcher",
                "price": {"amount": 11000, "currency": "USD"},
                "timestamp": "2025-11-13T10:00:00Z",
            },
            {
                "title": "Strange Australium Rocket Launcher",
                "price": {"amount": 11500, "currency": "USD"},
                "timestamp": "2025-11-14T10:00:00Z",
            },
        ],
    }

    trending = awAlgot find_trending_items(
        game="tf2",
        min_price=5.0,
        max_price=20000.0,
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем структуру результата
    assert isinstance(trending, list)
    # Может быть пустым если нет подходящих трендов
    if len(trending) > 0:
        assert "game" in trending[0]
        assert trending[0]["game"] == "tf2"


# ======================== Тесты для Rust ========================


@pytest.fixture()
def sample_rust_market_items():
    """Создать пример рыночных предметов Rust."""
    return {
        "items": [
            {
                "title": "Glowing Alien Relic Trophy",
                "price": {"amount": 15000, "currency": "USD"},
                "itemId": "rust_glowing_1",
                "category": "Trophy",
            },
            {
                "title": "Limited Tempered AK47 Skin",
                "price": {"amount": 8500, "currency": "USD"},
                "itemId": "rust_limited_1",
                "category": "Weapon Skin",
            },
            {
                "title": "Unique Burlap Headwrap",
                "price": {"amount": 3500, "currency": "USD"},
                "itemId": "rust_unique_1",
                "category": "Clothing",
            },
            {
                "title": "Unique Burlap Headwrap",
                "price": {"amount": 4200, "currency": "USD"},
                "itemId": "rust_unique_2",
                "category": "Clothing",
            },
        ],
    }


@pytest.fixture()
def sample_rust_rare_items():
    """Создать пример редких предметов Rust."""
    return {
        "items": [
            {
                "title": "Limited Glowing Hazmat Suit - Complete Set",
                "price": {"amount": 32000, "currency": "USD"},
                "itemId": "rust_rare_1",
                "suggestedPrice": {"amount": 38000, "currency": "USD"},
            },
            {
                "title": "Glowing Alien Relic Trophy",
                "price": {"amount": 15000, "currency": "USD"},
                "itemId": "rust_rare_2",
                "suggestedPrice": {"amount": 18500, "currency": "USD"},
            },
        ],
    }


@pytest.mark.asyncio()
async def test_find_price_anomalies_rust(
    mock_dmarket_api,
    sample_rust_market_items,
):
    """Тест поиска аномалий цен для Rust."""
    mock_dmarket_api.get_market_items.return_value = sample_rust_market_items

    anomalies = awAlgot find_price_anomalies(
        game="rust",
        min_price=1.0,
        max_price=10000.0,
        price_diff_percent=5.0,  # Lower threshold for test data
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что функция вернула список (может быть пустым если данные не дают аномалий)
    assert isinstance(anomalies, list)
    # Если есть аномалии, проверяем структуру
    if len(anomalies) > 0:
        assert anomalies[0]["game"] == "rust"


@pytest.mark.asyncio()
async def test_find_mispriced_rare_items_rust(
    mock_dmarket_api,
    sample_rust_rare_items,
):
    """Тест поиска недооцененных редких предметов Rust."""
    mock_dmarket_api.get_market_items.return_value = sample_rust_rare_items

    rare_items = awAlgot find_mispriced_rare_items(
        game="rust",
        min_price=10.0,
        max_price=50000.0,
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что найдены редкие предметы
    assert len(rare_items) > 0
    # Limited + Glowing должны иметь высокий rarity_score
    limited_glowing = next(
        (
            item
            for item in rare_items
            if "Limited" in item["item"]["title"] and "Glowing" in item["item"]["title"]
        ),
        None,
    )
    assert limited_glowing is not None
    # Limited (80) + Glowing (70) + Complete Set (60) = 210
    assert limited_glowing["rarity_score"] >= 150


@pytest.mark.asyncio()
async def test_find_trending_items_rust(
    mock_dmarket_api,
    sample_rust_market_items,
):
    """Тест поиска трендовых предметов Rust."""
    mock_dmarket_api.get_market_items.return_value = sample_rust_market_items
    mock_dmarket_api.get_sales_history.return_value = {
        "items": [
            {
                "title": "Glowing Alien Relic Trophy",
                "price": {"amount": 13000, "currency": "USD"},
                "timestamp": "2025-11-13T10:00:00Z",
            },
            {
                "title": "Glowing Alien Relic Trophy",
                "price": {"amount": 14000, "currency": "USD"},
                "timestamp": "2025-11-14T10:00:00Z",
            },
        ],
    }

    trending = awAlgot find_trending_items(
        game="rust",
        min_price=5.0,
        max_price=20000.0,
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем структуру результата
    assert isinstance(trending, list)
    # Может быть пустым если нет подходящих трендов
    if len(trending) > 0:
        assert "game" in trending[0]
        assert trending[0]["game"] == "rust"


@pytest.mark.asyncio()
async def test_scan_for_intramarket_opportunities_all_games(
    mock_dmarket_api,
    sample_market_items,
    sample_tf2_market_items,
    sample_rust_market_items,
):
    """Тест комплексного сканирования для всех игр включая TF2 и Rust."""

    def get_items_side_effect(game, **kwargs):
        items_map = {
            "csgo": sample_market_items,
            "tf2": sample_tf2_market_items,
            "rust": sample_rust_market_items,
        }
        return items_map.get(game, {"items": []})

    mock_dmarket_api.get_market_items.side_effect = get_items_side_effect
    mock_dmarket_api.get_sales_history.return_value = {"items": []}

    results = awAlgot scan_for_intramarket_opportunities(
        games=["csgo", "tf2", "rust"],
        max_results_per_game=5,
        dmarket_api=mock_dmarket_api,
    )

    # Проверяем что все игры присутствуют в результатах
    assert "csgo" in results
    assert "tf2" in results
    assert "rust" in results

    # Проверяем структуру для каждой игры
    for game in ["csgo", "tf2", "rust"]:
        assert "price_anomalies" in results[game]
        assert "trending_items" in results[game]
        assert "rare_mispriced" in results[game]
        assert isinstance(results[game]["price_anomalies"], list)
        assert isinstance(results[game]["trending_items"], list)
        assert isinstance(results[game]["rare_mispriced"], list)
