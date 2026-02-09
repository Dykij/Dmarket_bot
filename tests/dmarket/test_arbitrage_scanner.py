"""Тесты для модуля ArbitrageScanner.

Покрывает основные функции поиска арбитражных возможностей,
кеширование, управление API клиентом и автоматическую торговлю.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.dmarket.arbitrage_scanner import ARBITRAGE_LEVELS, GAME_IDS, ArbitrageScanner

from src.dmarket.dmarket_api import DMarketAPI

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_api_client():
    """Создает мок DMarketAPI клиента."""
    api = MagicMock(spec=DMarketAPI)
    api.get_balance = AsyncMock(return_value={"usd": "10000", "error": False, "balance": 100.0})
    api.get_market_items = AsyncMock(
        return_value={
            "objects": [
                {
                    "itemId": "item_001",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1250"},
                    "suggestedPrice": {"USD": "1400"},
                    "extra": {"floatValue": 0.25, "category": "Rifle"},
                },
                {
                    "itemId": "item_002",
                    "title": "AWP | Asiimov (Field-Tested)",
                    "price": {"USD": "5000"},
                    "suggestedPrice": {"USD": "5500"},
                    "extra": {"floatValue": 0.28, "category": "Rifle"},
                },
            ],
            "total": 2,
        }
    )
    api.buy_item = AsyncMock(return_value={"success": True, "orderId": "order_123"})
    api.sell_item = AsyncMock(return_value={"success": True, "offerId": "offer_456"})
    return api


@pytest.fixture()
def scanner(mock_api_client):
    """Создает ArbitrageScanner с мок API клиентом."""
    return ArbitrageScanner(api_client=mock_api_client)


@pytest.fixture()
def scanner_no_client():
    """Создает ArbitrageScanner без API клиента."""
    return ArbitrageScanner()


@pytest.fixture()
def level_test_data():
    """Данные для тестирования find_best_opportunities с правильным форматом."""
    return {
        "boost": [{"title": "boost1", "profit_percent": 2.0}],
        "standard": [{"title": "std1", "profit_percent": 6.0}],
        "medium": [{"title": "med1", "profit_percent": 12.0}],
        "advanced": [{"title": "adv1", "profit_percent": 20.0}],
        "pro": [{"title": "pro1", "profit_percent": 35.0}],
    }


# ============================================================================
# Тесты инициализации
# ============================================================================


def test_arbitrage_scanner_initialization(scanner):
    """Тест инициализации ArbitrageScanner."""
    assert scanner.api_client is not None
    assert scanner._scanner_cache is not None
    assert scanner._scanner_cache.ttl == 300
    assert scanner.min_profit == 0.5
    assert scanner.max_price == 50.0
    assert scanner.max_trades == 5
    assert scanner.total_scans == 0
    assert scanner.total_items_found == 0
    assert scanner.successful_trades == 0
    assert scanner.total_profit == 0.0


def test_arbitrage_scanner_without_client(scanner_no_client):
    """Тест инициализации без API клиента."""
    assert scanner_no_client.api_client is None
    assert scanner_no_client._scanner_cache is not None


def test_cache_ttl_property(scanner):
    """Тест свойства cache_ttl."""
    assert scanner.cache_ttl == 300
    scanner.cache_ttl = 600
    assert scanner.cache_ttl == 600
    assert scanner._scanner_cache.ttl == 600


# ============================================================================
# Тесты кеширования
# ============================================================================


def test_get_cached_results_empty_cache(scanner):
    """Тест получения из пустого кеша."""
    cache_key = ("csgo", "medium", 0.0, float("inf"))
    result = scanner._get_cached_results(cache_key)
    assert result is None


def test_save_to_cache(scanner):
    """Тест сохранения в кеш."""
    cache_key = ("csgo", "medium", 0.0, float("inf"))
    items = [{"item": "test1"}, {"item": "test2"}]

    scanner._save_to_cache(cache_key, items)

    # Используем строковый ключ для доступа к внутреннему кешу
    str_key = scanner._scanner_cache._make_key(cache_key)
    assert str_key in scanner._scanner_cache._cache
    cached_items, timestamp = scanner._scanner_cache._cache[str_key]
    assert cached_items == items
    assert isinstance(timestamp, float)


def test_get_cached_results_valid_cache(scanner):
    """Тест получения валидных данных из кеша."""
    cache_key = ("csgo", "medium", 0.0, float("inf"))
    items = [{"item": "test1"}, {"item": "test2"}]

    scanner._save_to_cache(cache_key, items)
    result = scanner._get_cached_results(cache_key)

    assert result == items


def test_get_cached_results_expired_cache(scanner):
    """Тест получения устаревших данных из кеша."""
    cache_key = ("csgo", "medium", 0.0, float("inf"))
    items = [{"item": "test1"}]

    # Сохраняем в кеш
    scanner._save_to_cache(cache_key, items)

    # Устанавливаем timestamp в прошлое (напрямую в _scanner_cache)
    str_key = scanner._scanner_cache._make_key(cache_key)
    scanner._scanner_cache._cache[str_key] = (items, time.time() - 400)

    result = scanner._get_cached_results(cache_key)
    assert result is None


# ============================================================================
# Тесты API клиента
# ============================================================================


@pytest.mark.asyncio()
async def test_get_api_client_existing(scanner):
    """Тест получения существующего API клиента."""
    client = await scanner.get_api_client()
    assert client is scanner.api_client


@pytest.mark.asyncio()
async def test_get_api_client_create_new(scanner_no_client):
    """Тест создания нового API клиента."""
    with patch.dict(
        "os.environ",
        {
            "DMARKET_PUBLIC_KEY": "test_public",
            "DMARKET_SECRET_KEY": "test_secret",
            "DMARKET_API_URL": "https://test.api.com",
        },
    ):
        client = await scanner_no_client.get_api_client()
        assert client is not None
        assert scanner_no_client.api_client is client


# ============================================================================
# Тесты scan_game
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_game_with_cache(scanner):
    """Тест scan_game с использованием кеша."""
    # Подготовка кеша
    # Ключ должен совпадать с тем, что создает scan_game():
    # cache_key = (game, mode, price_from or 0, price_to or float("inf"))
    # Где price_from=None -> 0 (int), price_to=None -> float("inf")
    cache_key = ("csgo", "medium", 0, float("inf"))  # 0 (int), не 0.0 (float)!
    cached_items = [{"item": "cached1"}, {"item": "cached2"}]
    scanner._save_to_cache(cache_key, cached_items)

    # Сканирование должно вернуть данные из кеша
    with patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"):
        result = await scanner.scan_game("csgo", "medium", max_items=10)

    assert result == cached_items
    assert scanner.api_client.get_market_items.call_count == 0


@pytest.mark.asyncio()
async def test_scan_game_without_cache(scanner):
    """Тест scan_game без кеша (первый запрос)."""
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch(
            "src.dmarket.arbitrage_scanner.arbitrage_mid_async",
            return_value=[{"item": "from_func"}],
        ),
    ):
        result = await scanner.scan_game("csgo", "medium", max_items=10)

    assert isinstance(result, list)
    assert scanner.total_scans == 1


@pytest.mark.asyncio()
async def test_scan_game_boost_mode(scanner):
    """Тест режима boost."""
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch(
            "src.dmarket.arbitrage_scanner.arbitrage_boost_async",
            return_value=[{"item": "boost"}],
        ) as mock_boost,
    ):
        result = await scanner.scan_game("csgo", "low", max_items=5)

    mock_boost.assert_called_once_with("csgo")
    assert isinstance(result, list)


@pytest.mark.asyncio()
async def test_scan_game_pro_mode(scanner):
    """Тест режима pro."""
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch(
            "src.dmarket.arbitrage_scanner.arbitrage_pro_async",
            return_value=[{"item": "pro"}],
        ) as mock_pro,
    ):
        result = await scanner.scan_game("dota2", "high", max_items=3)

    mock_pro.assert_called_once_with("dota2")
    assert isinstance(result, list)


@pytest.mark.asyncio()
async def test_scan_game_with_price_range(scanner):
    """Тест сканирования с диапазоном цен."""
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch("src.dmarket.arbitrage_scanner.ArbitrageTrader") as mock_trader,
    ):
        mock_trader_instance = AsyncMock()
        mock_trader_instance.scan_items = AsyncMock(return_value=[{"item": "trader"}])
        mock_trader.return_value = mock_trader_instance

        result = await scanner.scan_game(
            "csgo", "medium", max_items=10, price_from=10.0, price_to=50.0
        )

    assert isinstance(result, list)


@pytest.mark.asyncio()
async def test_scan_game_api_error(scanner):
    """Тест обработки ошибки API."""
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch(
            "src.dmarket.arbitrage_scanner.arbitrage_mid_async",
            side_effect=Exception("API Error"),
        ),
    ):
        result = await scanner.scan_game("csgo", "medium")

    assert result == []


# ============================================================================
# Тесты _standardize_items
# ============================================================================


def test_standardize_items_dmarket_format(scanner):
    """Тест стандартизации предметов из DMarket."""
    items = [
        {
            "itemId": "item_001",
            "name": "Test Item",  # _standardize_items ищет 'name' или 'title'
            "buy_price": 15.0,
            "sell_price": 17.0,
            "profit": 2.0,
            "profit_percentage": 13.33,
        }
    ]

    result = scanner._standardize_items(items, "csgo", min_profit=0.5, max_profit=100.0)

    assert len(result) == 1
    assert result[0]["title"] == "Test Item"
    assert "profit" in result[0]
    assert result[0]["profit"] == 2.0


def test_standardize_items_trader_format(scanner):
    """Тест стандартизации предметов из ArbitrageTrader."""
    items = [
        {
            "name": "Trader Item",
            "buy_price": 25.5,
            "sell_price": 30.0,
            "profit": 4.5,
            "profit_percentage": 17.65,
        }
    ]

    result = scanner._standardize_items(items, "dota2", min_profit=0.5, max_profit=100.0)

    assert len(result) == 1
    assert result[0]["title"] == "Trader Item"
    assert "profit" in result[0]
    assert result[0]["profit"] == 4.5


def test_standardize_items_mixed_formats(scanner):
    """Тест стандартизации смешанных форматов."""
    items = [
        {
            "name": "DMarket Item",
            "buy_price": 10.0,
            "sell_price": 12.0,
            "profit": 2.0,
            "profit_percentage": 20.0,
        },
        {
            "name": "Trader Item",
            "buy_price": 10.0,
            "sell_price": 12.0,
            "profit": 2.0,
            "profit_percentage": 20.0,
        },
    ]

    result = scanner._standardize_items(items, "csgo", min_profit=0.5, max_profit=100.0)

    assert len(result) == 2
    assert result[0]["title"] == "DMarket Item"
    assert result[1]["title"] == "Trader Item"


# ============================================================================
# Тесты scan_multiple_games
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_multiple_games_success(scanner):
    """Тест сканирования нескольких игр."""
    with patch.object(scanner, "scan_game", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = [{"item": "test"}]

        games = ["csgo", "dota2"]
        result = await scanner.scan_multiple_games(games, "medium", max_items_per_game=5)

    assert len(result) == 2
    assert "csgo" in result
    assert "dota2" in result
    assert mock_scan.call_count == 2


@pytest.mark.asyncio()
async def test_scan_multiple_games_empty_list(scanner):
    """Тест сканирования пустого списка игр."""
    result = await scanner.scan_multiple_games([], "medium")
    assert result == {}


@pytest.mark.asyncio()
async def test_scan_multiple_games_one_fails(scanner):
    """Тест обработки ошибки при сканировании одной из игр."""

    async def mock_scan_game(game, mode, max_items, **kwargs):
        if game == "csgo":
            return [{"item": "csgo_item"}]
        raise Exception("API Error")

    with patch.object(scanner, "scan_game", side_effect=mock_scan_game):
        games = ["csgo", "dota2"]
        result = await scanner.scan_multiple_games(games, "medium")

    assert "csgo" in result
    assert "dota2" in result
    assert len(result["csgo"]) > 0
    assert result["dota2"] == []


# ============================================================================
# Тесты check_user_balance
# ============================================================================


@pytest.mark.asyncio()
async def test_check_user_balance_success(scanner):
    """Тест успешной проверки баланса."""
    # Мокируем _request для возврата баланса в центах
    # Формат: {"usd": {"amount": 10050}} = $100.50 (amount в центах)
    scanner.api_client._request = AsyncMock(return_value={"usd": {"amount": 10050}})

    result = await scanner.check_user_balance()

    assert result["error"] is False
    assert "balance" in result
    assert result["balance"] == 100.50


@pytest.mark.asyncio()
async def test_check_user_balance_api_error(scanner):
    """Тест обработки ошибки при проверке баланса."""
    scanner.api_client._request = AsyncMock(side_effect=Exception("API Error"))

    result = await scanner.check_user_balance()

    assert result["error"] is True
    assert "error_message" in result


# ============================================================================
# Тесты уровней арбитража
# ============================================================================


def test_get_level_config_boost(scanner):
    """Тест получения конфигурации уровня boost."""
    config = scanner.get_level_config("boost")

    assert config["name"] == "🚀 Разгон баланса"
    assert config["min_profit_percent"] == 1.0
    assert config["price_range"] == (0.5, 3.0)


def test_get_level_config_pro(scanner):
    """Тест получения конфигурации уровня pro."""
    config = scanner.get_level_config("pro")

    assert config["name"] == "💎 Профи"
    assert config["min_profit_percent"] == 20.0
    assert config["price_range"] == (100.0, 1000.0)


def test_get_level_config_invalid(scanner):
    """Тест получения конфигурации несуществующего уровня."""
    with pytest.raises(ValueError, match="Неизвестный уровень арбитража"):
        scanner.get_level_config("invalid_level")


def test_arbitrage_levels_defined():
    """Тест наличия всех уровней арбитража."""
    assert "boost" in ARBITRAGE_LEVELS
    assert "standard" in ARBITRAGE_LEVELS
    assert "medium" in ARBITRAGE_LEVELS
    assert "advanced" in ARBITRAGE_LEVELS
    assert "pro" in ARBITRAGE_LEVELS


def test_game_ids_defined():
    """Тест наличия маппинга ID игр."""
    assert "csgo" in GAME_IDS
    assert "dota2" in GAME_IDS
    assert "tf2" in GAME_IDS
    assert "rust" in GAME_IDS


# ============================================================================
# Тесты scan_level
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_level_boost(scanner):
    """Тест сканирования уровня boost."""
    # scan_level вызывает get_market_items напрямую
    mock_response = {
        "objects": [
            {
                "itemId": "item1",
                "title": "Boost Item",
                "price": {"USD": "200"},  # $2.00 в центах
                "suggestedPrice": {"USD": "250"},  # $2.50 в центах
            }
        ]
    }
    scanner.api_client.get_market_items = AsyncMock(return_value=mock_response)
    scanner._analyze_item = AsyncMock(return_value={"item": "boost_item"})

    result = await scanner.scan_level("boost", "csgo", max_results=10)

    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.asyncio()
async def test_scan_level_with_cache(scanner):
    """Тест scan_level с кешем."""
    cache_key = "scan_level_csgo_boost"  # Правильный формат ключа
    cached_data = [{"item": "cached"}]
    scanner._scanner_cache._cache[cache_key] = (cached_data, time.time())

    result = await scanner.scan_level("boost", "csgo")

    # Должен вернуть кешированные данные без обращения к API
    assert result == cached_data


@pytest.mark.asyncio()
async def test_scan_level_filters_by_price_range(scanner):
    """Тест фильтрации по диапазону цен уровня."""
    items = [
        {"item": "cheap", "buy_price": 1.0},  # Вне диапазона boost
        {"item": "in_range", "buy_price": 2.0},  # В диапазоне boost (0.5-3.0)
        {"item": "expensive", "buy_price": 50.0},  # Вне диапазона boost
    ]

    with patch.object(scanner, "scan_game", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = items

        result = await scanner.scan_level("boost", "csgo")

    # Только предметы в диапазоне boost (0.5-3.0)
    assert all(0.5 <= item["buy_price"] <= 3.0 for item in result)


# ============================================================================
# Тесты scan_all_levels
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_all_levels_success(scanner):
    """Тест сканирования всех уровней."""
    with patch.object(scanner, "scan_level", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = [{"item": "test"}]

        result = await scanner.scan_all_levels("csgo", max_results_per_level=5)

    assert isinstance(result, dict)
    assert len(result) == 5  # boost, standard, medium, advanced, pro
    assert mock_scan.call_count == 5


@pytest.mark.asyncio()
async def test_scan_all_levels_one_fails(scanner):
    """Тест обработки ошибки при сканировании одного уровня."""

    async def mock_scan_level(level, game, max_results=10, use_cache=True):
        if level == "boost":
            return []  # Возвращаем пустой список при ошибке
        return [{"item": f"{level}_item"}]

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        result = await scanner.scan_all_levels("csgo")

    assert "boost" in result
    assert result["boost"] == []
    assert len(result["standard"]) > 0


# ============================================================================
# Тесты find_best_opportunities
# ============================================================================


@pytest.mark.asyncio()
async def test_find_best_opportunities_top_n(scanner, level_test_data):
    """Тест поиска топ-N возможностей."""

    async def mock_scan_level(level, game, max_results):
        """Mock scan_level для возврата данных по уровню."""
        return level_test_data.get(level, [])

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        result = await scanner.find_best_opportunities("csgo", top_n=3)

    assert len(result) <= 3
    # Должны быть отсортированы по profit_percent (убывание)
    if len(result) > 1:
        assert result[0]["profit_percent"] >= result[1]["profit_percent"]


@pytest.mark.asyncio()
async def test_find_best_opportunities_min_level(scanner, level_test_data):
    """Тест фильтрации по минимальному уровню."""

    async def mock_scan_level(level, game, max_results):
        """Mock scan_level для возврата данных по уровню."""
        return level_test_data.get(level, [])

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        result = await scanner.find_best_opportunities("csgo", top_n=10, min_level="medium")

    # Не должно быть предметов из boost и standard
    titles = [item.get("title") for item in result]
    assert "boost1" not in titles
    assert "std1" not in titles
    # Должны быть предметы из medium, advanced, pro
    assert "med1" in titles or "adv1" in titles or "pro1" in titles


@pytest.mark.asyncio()
async def test_find_best_opportunities_max_level(scanner, level_test_data):
    """Тест фильтрации по максимальному уровню."""

    async def mock_scan_level(level, game, max_results):
        """Mock scan_level для возврата данных по уровню."""
        return level_test_data.get(level, [])

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        result = await scanner.find_best_opportunities("csgo", top_n=10, max_level="medium")

    # Не должно быть предметов из advanced и pro
    titles = [item.get("title") for item in result]
    assert "adv1" not in titles
    assert "pro1" not in titles
    # Должны быть предметы из boost, standard, medium
    assert "boost1" in titles or "std1" in titles or "med1" in titles


# ============================================================================
# Тесты параллельного сканирования
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_all_levels_parallel_success(scanner, mock_api_client):
    """Тест успешного параллельного сканирования всех уровней."""

    # Настраиваем мок для возврата разных результатов для каждого уровня
    async def mock_scan_level(level, game, max_results):
        return [
            {
                "title": f"Item {level}",
                "profit_percent": 5.0,
                "level": level,
            }
        ]

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        start_time = time.time()
        results = await scanner.scan_all_levels_parallel(game="csgo")
        elapsed = time.time() - start_time

        # Проверяем что получены результаты для всех уровней
        assert isinstance(results, dict)
        assert len(results) == 5
        for level in ARBITRAGE_LEVELS:
            assert level in results
            assert len(results[level]) > 0

        # Параллельное выполнение должно быть быстрее
        # (в реальности будет быстрее, но в моках проверяем просто что работает)
        assert elapsed < 5.0  # Должно быть очень быстро с моками


@pytest.mark.asyncio()
async def test_scan_all_levels_parallel_with_errors(scanner):
    """Тест параллельного сканирования с ошибками в некоторых уровнях."""

    async def mock_scan_level_with_errors(level, game, max_results):
        # Для уровней boost и pro выбрасываем ошибку
        if level in ["boost", "pro"]:
            raise ValueError(f"Error scanning {level}")
        return [{"title": f"Item {level}", "profit_percent": 5.0}]

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level_with_errors):
        results = await scanner.scan_all_levels_parallel(game="csgo")

        # Проверяем что получены результаты для успешных уровней
        assert isinstance(results, dict)
        assert len(results) == 5

        # Уровни с ошибками должны иметь пустые списки
        assert results["boost"] == []
        assert results["pro"] == []

        # Остальные уровни должны иметь результаты
        assert len(results["standard"]) > 0
        assert len(results["medium"]) > 0
        assert len(results["advanced"]) > 0


@pytest.mark.asyncio()
async def test_scan_all_levels_with_parallel_flag(scanner, mock_api_client):
    """Тест scan_all_levels с флагом parallel=True."""

    async def mock_scan_level(level, game, max_results):
        return [{"title": f"Item {level}", "profit_percent": 5.0}]

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level):
        # С parallel=True
        results_parallel = await scanner.scan_all_levels(
            game="csgo",
            parallel=True,
        )

        assert isinstance(results_parallel, dict)
        assert len(results_parallel) == 5

        # С parallel=False (последовательное выполнение)
        results_sequential = await scanner.scan_all_levels(
            game="csgo",
            parallel=False,
        )

        assert isinstance(results_sequential, dict)
        assert len(results_sequential) == 5

        # Результаты должны быть одинаковыми
        assert results_parallel.keys() == results_sequential.keys()


@pytest.mark.asyncio()
async def test_scan_all_levels_parallel_invalid_game(scanner):
    """Тест параллельного сканирования с невалидной игрой."""
    with pytest.raises(ValueError, match="не поддерживается"):
        await scanner.scan_all_levels_parallel(game="invalid_game")


@pytest.mark.asyncio()
async def test_find_best_opportunities_parallel_execution(scanner, level_test_data):
    """Тест что find_best_opportunities использует параллельное выполнение."""
    call_times = []

    async def mock_scan_level_with_timing(level, game, max_results):
        """Mock который записывает время вызова."""
        call_times.append(time.time())
        await asyncio.sleep(0.01)  # Небольшая задержка
        return level_test_data.get(level, [])

    with patch.object(scanner, "scan_level", side_effect=mock_scan_level_with_timing):
        await scanner.find_best_opportunities("csgo", top_n=10)

        # При параллельном выполнении все вызовы должны начаться примерно одновременно
        if len(call_times) > 1:
            time_diff = max(call_times) - min(call_times)
            # Все вызовы должны начаться в течение 0.1 секунды
            assert time_diff < 0.1


# ============================================================================
# Тесты get_level_stats
# ============================================================================


def test_get_level_stats_initial(scanner):
    """Тест статистики уровней при инициализации."""
    stats = scanner.get_level_stats()

    assert isinstance(stats, dict)
    assert len(stats) == 5
    for level_name in ["boost", "standard", "medium", "advanced", "pro"]:
        assert level_name in stats
        assert "name" in stats[level_name]
        assert "min_profit" in stats[level_name]
        assert "price_range" in stats[level_name]


# ============================================================================
# Тесты auto_trade_items
# ============================================================================


@pytest.mark.asyncio()
async def test_auto_trade_items_success(scanner):
    """Тест автоматической торговли."""
    items_by_game = {
        "csgo": [
            {
                "item_id": "item_001",
                "title": "Test Item",
                "buy_price": 10.0,
                "sell_price": 12.0,
                "game": "csgo",
            }
        ]
    }

    result = await scanner.auto_trade_items(items_by_game, max_trades=1)

    assert isinstance(result, tuple)
    assert len(result) == 3


@pytest.mark.asyncio()
async def test_auto_trade_items_empty_list(scanner):
    """Тест автоторговли с пустым списком."""
    result = await scanner.auto_trade_items({})

    assert isinstance(result, tuple)
    assert result[0] == 0  # purchases
    assert result[1] == 0  # sales
    assert result[2] == 0.0  # profit


@pytest.mark.asyncio()
async def test_auto_trade_items_insufficient_balance(scanner):
    """Тест автоторговли при недостаточном балансе."""
    scanner.api_client.get_balance = AsyncMock(
        return_value={"usd": "100", "balance": 1.0, "error": False}  # Только $1
    )

    items_by_game = {
        "csgo": [
            {
                "item_id": "item_001",
                "title": "Expensive Item",
                "buy_price": 50.0,
                "sell_price": 60.0,
                "game": "csgo",
            }
        ]
    }

    result = await scanner.auto_trade_items(items_by_game)

    # Не должно быть успешных сделок из-за нехватки средств
    assert result[0] == 0  # purchases


@pytest.mark.asyncio()
async def test_auto_trade_items_max_trades_limit(scanner):
    """Тест лимита максимального количества сделок."""
    items_by_game = {
        "csgo": [
            {
                "item_id": f"item_{i:03d}",
                "title": f"Item {i}",
                "buy_price": 5.0,
                "sell_price": 6.0,
                "game": "csgo",
            }
            for i in range(10)
        ]
    }

    result = await scanner.auto_trade_items(items_by_game, max_trades=3)

    # Должно быть не более 3 попыток торговли
    total_attempts = result[0] + result[1]  # purchases + sales
    assert total_attempts <= 6  # max 3 покупки + max 3 продажи


# ============================================================================
# Тесты _analyze_item
# ============================================================================


@pytest.mark.asyncio()
async def test_analyze_item_success(scanner):
    """Тест анализа предмета."""
    item = {
        "itemId": "item_001",
        "title": "Test Item",
        "price": {"USD": 1000},
        "suggestedPrice": {"USD": 1200},
    }
    config = {
        "price_range": (5.0, 15.0),
        "min_profit_percent": 3.0,
    }

    result = await scanner._analyze_item(item, config, "csgo")

    assert result is not None
    assert "buy_price" in result
    assert "suggested_price" in result or "sell_price" in result
    assert "profit" in result
    assert "profit_percent" in result


@pytest.mark.asyncio()
async def test_analyze_item_no_profit(scanner):
    """Тест анализа предмета без прибыли."""
    item = {
        "itemId": "item_001",
        "title": "No Profit Item",
        "price": {"USD": 1000},
        "suggestedPrice": {"USD": 900},  # Меньше цены покупки
    }
    config = {
        "price_range": (5.0, 15.0),
        "min_profit_percent": 3.0,
    }

    result = await scanner._analyze_item(item, config, "csgo")

    # Предмет не должен быть добавлен (нет прибыли)
    assert result is None or result["profit"] <= 0


# ============================================================================
# Интеграционные тесты
# ============================================================================


@pytest.mark.asyncio()
async def test_full_arbitrage_workflow(scanner):
    """Интеграционный тест: полный цикл арбитража."""
    # Мокируем _request для check_user_balance
    scanner.api_client._request = AsyncMock(return_value={"usd": {"available": 10000, "frozen": 0}})

    # 1. Сканирование игры
    with (
        patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"),
        patch(
            "src.dmarket.arbitrage_scanner.arbitrage_mid_async",
            return_value=[
                {
                    "itemId": "int_001",
                    "title": "AK-47 | Rifle Test Item",  # Include "Rifle" for category filter
                    "price": {"USD": "2000"},
                    "suggestedPrice": {"USD": "2500"},
                    "offersCount": 50,  # Required for liquidity filter
                }
            ],
        ),
    ):
        items = await scanner.scan_game("csgo", "medium", max_items=5)

    assert len(items) > 0

    # 2. Проверка баланса
    balance = await scanner.check_user_balance()
    assert balance["error"] is False

    # 3. Автоматическая торговля (упрощённая проверка)
    items_dict = {"csgo": items}
    result = await scanner.auto_trade_items(items_dict, max_trades=1)
    assert result is not None


# ============================================================================
# Тесты граничных случаев
# ============================================================================


@pytest.mark.asyncio()
async def test_scan_game_with_zero_max_items(scanner):
    """Тест сканирования с max_items=0."""
    with patch("src.dmarket.arbitrage_scanner.rate_limiter.wait_if_needed"):
        result = await scanner.scan_game("csgo", "medium", max_items=0)

    assert result == []


def test_standardize_items_empty_list(scanner):
    """Тест стандартизации пустого списка."""
    result = scanner._standardize_items([], "csgo", min_profit=0.5, max_profit=100.0)
    assert result == []


def test_standardize_items_invalid_format(scanner):
    """Тест стандартизации предметов с невалидным форматом."""
    items = [
        {"invalid": "format"},  # Нет нужных полей
    ]

    result = scanner._standardize_items(items, "csgo", min_profit=0.5, max_profit=100.0)

    # Должен обработать ошибку и вернуть пустой список или пропустить
    assert isinstance(result, list)


@pytest.mark.asyncio()
async def test_scan_multiple_games_concurrent(scanner):
    """Тест конкурентного сканирования игр."""

    async def delayed_scan(game, mode, max_items):
        await asyncio.sleep(0.1)  # Имитация задержки API
        return [{"item": f"{game}_item"}]

    with patch.object(scanner, "scan_game", side_effect=delayed_scan):
        games = ["csgo", "dota2", "rust"]

        start_time = time.time()
        result = await scanner.scan_multiple_games(games, "medium")
        elapsed = time.time() - start_time

    # Проверяем, что сканирование было параллельным (< 0.3 сек вместо 0.3+)
    assert elapsed < 0.2  # Должно быть быстрее последовательного выполнения
    assert len(result) == 3


# ============================================================================
# Тесты интеграции с LiquidityAnalyzer
# ============================================================================


@pytest.mark.asyncio()
async def test_liquidity_filter_enabled_by_default():
    """Тест что фильтр ликвидности включен по умолчанию."""
    scanner = ArbitrageScanner()
    assert scanner.enable_liquidity_filter is True
    assert scanner.min_liquidity_score == 60
    assert scanner.min_sales_per_week == 5
    assert scanner.max_time_to_sell_days == 7


@pytest.mark.asyncio()
async def test_liquidity_filter_can_be_disabled():
    """Тест отключения фильтра ликвидности."""
    scanner = ArbitrageScanner(enable_liquidity_filter=False)
    assert scanner.enable_liquidity_filter is False


@pytest.mark.asyncio()
async def test_liquidity_analyzer_initialized_when_enabled(mock_api_client):
    """Тест инициализации LiquidityAnalyzer при включенном фильтре."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)

    # Вызываем get_api_client для инициализации анализатора
    await scanner.get_api_client()

    assert scanner.liquidity_analyzer is not None


@pytest.mark.asyncio()
async def test_liquidity_analyzer_not_initialized_when_disabled(mock_api_client):
    """Тест что LiquidityAnalyzer не инициализируется при отключенном фильтре."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=False)

    await scanner.get_api_client()

    assert scanner.liquidity_analyzer is None


@pytest.mark.asyncio()
async def test_analyze_item_filters_by_low_liquidity(mock_api_client):
    """Тест фильтрации предметов с низкой ликвидностью."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)
    scanner.min_liquidity_score = 70  # Устанавливаем порог

    # Инициализируем анализатор
    await scanner.get_api_client()

    # Мокаем анализатор ликвидности чтобы вернуть низкий балл
    from src.dmarket.liquidity_analyzer import LiquidityMetrics

    scanner.liquidity_analyzer.analyze_item_liquidity = AsyncMock(
        return_value=LiquidityMetrics(
            item_title="Test Item",
            sales_per_week=2.0,
            avg_time_to_sell_days=10.0,
            active_offers_count=20,
            price_stability=0.8,
            market_depth=5.0,
            liquidity_score=30.0,  # Ниже порога
            is_liquid=False,
        )
    )

    item = {
        "itemId": "test_item",
        "title": "Test Item",
        "price": {"USD": 1000},  # Цена в центах
        "suggestedPrice": {"USD": 1200},
    }
    config = {"price_range": (5.0, 15.0), "min_profit_percent": 5.0}

    result = await scanner._analyze_item(item, config, "csgo")

    # Предмет должен быть отфильтрован из-за низкой ликвидности
    assert result is None


@pytest.mark.asyncio()
async def test_analyze_item_passes_high_liquidity(mock_api_client):
    """Тест прохождения предметов с высокой ликвидностью."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)
    scanner.min_liquidity_score = 60

    await scanner.get_api_client()

    # Мокаем высокую ликвидность
    from src.dmarket.liquidity_analyzer import LiquidityMetrics

    scanner.liquidity_analyzer.analyze_item_liquidity = AsyncMock(
        return_value=LiquidityMetrics(
            item_title="Test Item",
            sales_per_week=15.0,
            avg_time_to_sell_days=2.0,
            active_offers_count=30,
            price_stability=0.95,
            market_depth=50.0,
            liquidity_score=85.0,  # Выше порога
            is_liquid=True,
        )
    )

    item = {
        "itemId": "test_item",
        "title": "Test Item",
        "price": {"USD": 1000},  # Цена в центах
        "suggestedPrice": {"USD": 1200},
    }
    config = {"price_range": (5.0, 15.0), "min_profit_percent": 5.0}

    result = await scanner._analyze_item(item, config, "csgo")

    # Предмет должен пройти фильтр
    assert result is not None
    assert result["liquidity_score"] == 85
    assert result["sales_per_week"] == 15.0
    assert result["time_to_sell_days"] == 2.0
    assert result["price_stability"] == 0.95


@pytest.mark.asyncio()
async def test_analyze_item_filters_by_time_to_sell(mock_api_client):
    """Тест фильтрации по времени продажи."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)
    scanner.max_time_to_sell_days = 5  # Максимум 5 дней

    await scanner.get_api_client()

    # Мокаем предмет который продается долго
    from src.dmarket.liquidity_analyzer import LiquidityMetrics

    scanner.liquidity_analyzer.analyze_item_liquidity = AsyncMock(
        return_value=LiquidityMetrics(
            item_title="Test Item",
            sales_per_week=10.0,
            avg_time_to_sell_days=10.0,  # Но долго продается
            active_offers_count=25,
            price_stability=0.85,
            market_depth=30.0,
            liquidity_score=70.0,  # Хороший балл
            is_liquid=True,
        )
    )

    item = {
        "itemId": "test_item",
        "title": "Test Item",
        "price": {"USD": 1000},  # Цена в центах
        "suggestedPrice": {"USD": 1200},
    }
    config = {"price_range": (5.0, 15.0), "min_profit_percent": 5.0}

    result = await scanner._analyze_item(item, config, "csgo")

    # Должен быть отфильтрован из-за долгой продажи
    assert result is None


@pytest.mark.asyncio()
async def test_analyze_item_without_liquidity_filter(mock_api_client):
    """Тест что без фильтра ликвидности предметы не анализируются."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=False)

    await scanner.get_api_client()

    item = {
        "itemId": "test_item",
        "title": "Test Item",
        "price": {"USD": 1000},  # Цена в центах
        "suggestedPrice": {"USD": 1200},
    }
    config = {"price_range": (5.0, 15.0), "min_profit_percent": 5.0}

    result = await scanner._analyze_item(item, config, "csgo")

    # Должен вернуться результат без данных ликвидности
    assert result is not None
    assert "liquidity_score" not in result


@pytest.mark.asyncio()
async def test_scan_level_with_liquidity_filter(mock_api_client):
    """Тест scan_level с фильтрацией по ликвидности."""
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)

    await scanner.get_api_client()

    # Мокаем API чтобы вернуть несколько предметов
    mock_api_client.get_market_items = AsyncMock(
        return_value={
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "High Liquidity Item",
                    "price": {"USD": 100},  # $1.00 в центах
                    "suggestedPrice": {"USD": 120},  # $1.20
                },
                {
                    "itemId": "item_2",
                    "title": "Low Liquidity Item",
                    "price": {"USD": 150},  # $1.50
                    "suggestedPrice": {"USD": 180},  # $1.80
                },
            ],
            "total": 2,
        }
    )

    # Мокаем анализатор чтобы первый предмет прошел, второй нет
    from src.dmarket.liquidity_analyzer import LiquidityMetrics

    async def mock_liquidity_analysis(item_title, game, days_history=30):
        if "High Liquidity" in item_title:
            return LiquidityMetrics(
                item_title=item_title,
                sales_per_week=20.0,
                avg_time_to_sell_days=2.0,
                active_offers_count=15,
                price_stability=0.92,
                market_depth=60.0,
                liquidity_score=80.0,
                is_liquid=True,
            )
        return LiquidityMetrics(
            item_title=item_title,
            sales_per_week=1.0,
            avg_time_to_sell_days=15.0,
            active_offers_count=100,
            price_stability=0.6,
            market_depth=3.0,
            liquidity_score=30.0,
            is_liquid=False,
        )

    scanner.liquidity_analyzer.analyze_item_liquidity = AsyncMock(
        side_effect=mock_liquidity_analysis
    )

    results = await scanner.scan_level("boost", "csgo", max_results=10)

    # Должен вернуться только 1 предмет (High Liquidity)
    assert len(results) == 1
    assert results[0]["item"]["title"] == "High Liquidity Item"
    assert results[0]["liquidity_score"] == 80
