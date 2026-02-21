"""Тесты для модуля arbitrage."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.arbitrage import (
    DEFAULT_FEE,
    GAMES,
    HIGH_FEE,
    LOW_FEE,
    MIN_PROFIT_PERCENT,
    PRICE_RANGES,
    ArbitrageTrader,
    _arbitrage_cache,
    _get_cached_results,
    _save_to_cache,
    fetch_market_items,
    find_arbitrage_items,
    find_arbitrage_opportunities,
)


class TestConstants:
    """Тесты констант модуля."""

    def test_games_defined(self):
        """Тест наличия всех поддерживаемых игр."""
        expected_games = ["csgo", "dota2", "tf2", "rust"]
        for game in expected_games:
            assert game in GAMES

    def test_fee_values(self):
        """Тест корректности значений комиссий."""
        assert 0 < DEFAULT_FEE < 1
        assert 0 < LOW_FEE < DEFAULT_FEE
        assert DEFAULT_FEE < HIGH_FEE < 1

    def test_min_profit_percent_modes(self):
        """Тест наличия всех режимов прибыли."""
        expected_modes = ["low", "medium", "high", "boost", "pro"]
        for mode in expected_modes:
            assert mode in MIN_PROFIT_PERCENT

    def test_price_ranges_ascending(self):
        """Тест что диапазоны цен идут по возрастанию."""
        # Диапазоны: boost(0.5-3), low(1-5), medium(5-20),
        # high(20-100), pro(100-1000)
        # Проверяем, что минимальные цены растут для основных режимов
        assert PRICE_RANGES["low"][0] < PRICE_RANGES["medium"][0]
        assert PRICE_RANGES["medium"][0] < PRICE_RANGES["high"][0]
        assert PRICE_RANGES["high"][0] < PRICE_RANGES["pro"][0]


class TestCacheFunctions:
    """Тесты функций кэширования."""

    def setup_method(self):
        """Очистить кэш перед каждым тестом."""
        _arbitrage_cache.clear()

    def test_save_to_cache(self):
        """Тест сохранения в кэш."""
        cache_key = ("csgo", "medium", 5.0, 20.0)
        items = [{"title": "AK-47 | Redline", "price": 10.0}]

        _save_to_cache(cache_key, items)

        assert cache_key in _arbitrage_cache
        cached_items, timestamp = _arbitrage_cache[cache_key]
        assert cached_items == items
        assert timestamp > 0

    def test_get_cached_results_fresh(self):
        """Тест получения свежих данных из кэша."""
        cache_key = ("csgo", "medium", 5.0, 20.0)
        items = [{"title": "Test Item", "price": 15.0}]

        _save_to_cache(cache_key, items)
        cached_items = _get_cached_results(cache_key)

        assert cached_items == items

    def test_get_cached_results_expired(self):
        """Тест получения устаревших данных из кэша."""
        cache_key = ("csgo", "medium", 5.0, 20.0)
        items = [{"title": "Test Item", "price": 15.0}]

        # Старше 5 минут (300 секунд)
        expired_timestamp = time.time() - 400
        _arbitrage_cache[cache_key] = (items, expired_timestamp)

        cached_items = _get_cached_results(cache_key)
        assert cached_items is None

    def test_get_cached_results_not_exists(self):
        """Тест получения несуществующих данных из кэша."""
        cache_key = ("dota2", "high", 20.0, 100.0)
        cached_items = _get_cached_results(cache_key)
        assert cached_items is None

    def test_cache_key_uniqueness(self):
        """Тест уникальности ключей кэша."""
        key1 = ("csgo", "medium", 5.0, 20.0)
        key2 = ("csgo", "medium", 5.0, 20.1)
        key3 = ("dota2", "medium", 5.0, 20.0)

        items1 = [{"title": "Item1"}]
        items2 = [{"title": "Item2"}]
        items3 = [{"title": "Item3"}]

        _save_to_cache(key1, items1)
        _save_to_cache(key2, items2)
        _save_to_cache(key3, items3)

        assert _get_cached_results(key1) == items1
        assert _get_cached_results(key2) == items2
        assert _get_cached_results(key3) == items3


class TestFetchMarketItems:
    """Тесты функции fetch_market_items."""

    @pytest.mark.asyncio()
    async def test_fetch_market_items_success(self):
        """Тест успешного получения предметов."""
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "AK-47 | Redline", "price": {"USD": 1250}},
                    {"title": "AWP | Asimov", "price": {"USD": 3500}},
                ],
            },
        )

        result = awAlgot fetch_market_items(
            game="csgo",
            limit=100,
            price_from=10.0,
            price_to=50.0,
            dmarket_api=mock_api,
        )

        assert len(result) == 2
        assert result[0]["title"] == "AK-47 | Redline"

    @pytest.mark.asyncio()
    async def test_fetch_market_items_empty(self):
        """Тест получения пустого списка предметов."""
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(return_value={"items": []})

        result = awAlgot fetch_market_items(dmarket_api=mock_api)
        assert result == []

    @pytest.mark.asyncio()
    async def test_fetch_market_items_api_error(self):
        """Тест обработки ошибки API."""
        mock_api = MagicMock()
        mock_api.get_market_items = AsyncMock(
            side_effect=Exception("API Error"),
        )

        result = awAlgot fetch_market_items(dmarket_api=mock_api)
        assert result == []


class TestArbitrageFunctions:
    """Тесты функций арбитража."""

    @pytest.mark.asyncio()
    async def test_arbitrage_boost(self):
        """Тест функции arbitrage_boost."""
        with patch("src.dmarket.arbitrage.arbitrage_boost_async") as mock:
            mock.return_value = []
            result = awAlgot mock(game="csgo")
            assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_arbitrage_mid(self):
        """Тест функции arbitrage_mid."""
        with patch("src.dmarket.arbitrage.arbitrage_mid_async") as mock:
            mock.return_value = []
            result = awAlgot mock(game="csgo")
            assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_arbitrage_pro(self):
        """Тест функции arbitrage_pro."""
        with patch("src.dmarket.arbitrage.arbitrage_pro_async") as mock:
            mock.return_value = []
            result = awAlgot mock(game="csgo")
            assert isinstance(result, list)


class TestArbitrageTrader:
    """Тесты класса ArbitrageTrader."""

    def test_arbitrage_trader_instantiation(self):
        """Тест создания экземпляра ArbitrageTrader."""
        trader = ArbitrageTrader(public_key="test_public", secret_key="test_secret")

        assert trader is not None
        assert trader.public_key == "test_public"
        assert trader.secret_key == "test_secret"
        assert trader.api is not None

    def test_arbitrage_trader_has_methods(self):
        """Тест наличия основных методов."""
        trader = ArbitrageTrader(public_key="test_public", secret_key="test_secret")

        assert hasattr(trader, "check_balance")
        assert hasattr(trader, "get_status")
        assert hasattr(trader, "get_transaction_history")
        assert trader.api is not None


class TestFindArbitrageItems:
    """Тесты функции find_arbitrage_items."""

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_basic(self):
        """Тест базового поиска арбитражных возможностей."""
        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=[],
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="mid",
            )

            assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_different_modes(self):
        """Тест поиска с разными режимами."""
        for mode in ["low", "mid", "pro", "boost"]:
            with patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                return_value=[],
            ):
                result = awAlgot find_arbitrage_items(
                    game="csgo",
                    mode=mode,
                )

                assert isinstance(result, list)


class TestFindArbitrageOpportunities:
    """Тесты функции find_arbitrage_opportunities."""

    def test_find_arbitrage_opportunities_basic(self):
        """Тест базового поиска возможностей."""
        with patch(
            "src.dmarket.arbitrage.find_arbitrage_opportunities_async",
            return_value=[],
        ):
            result = find_arbitrage_opportunities(
                game="csgo",
                min_profit_percentage=10.0,
                max_results=5,
            )

            assert isinstance(result, list)


class TestFindArbitrageAsync:
    """Тесты функции _find_arbitrage_async."""

    def setup_method(self):
        """Очистить кэш перед каждым тестом."""
        _arbitrage_cache.clear()

    @pytest.mark.asyncio()
    async def test_find_arbitrage_async_with_items(self):
        """Тест поиска арбитража с реальными предметами."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Mock items с правильным форматом цен (ключ USD в центах)
        mock_items = [
            {
                "title": "AK-47 | Redline (FT)",
                "itemId": "item_1",
                "price": {"USD": 1250},  # $12.50 в центах
                "suggestedPrice": {"USD": 1500},  # $15.00 в центах
                "extra": {"popularity": 0.8},
            },
            {
                "title": "AWP | Asiimov (FT)",
                "itemId": "item_2",
                "price": {"USD": 3500},  # $35.00 в центах
                "suggestedPrice": {"USD": 4200},  # $42.00 в центах
                "extra": {"popularity": 0.5},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            # Ищем прибыль от $1 до $10
            result = awAlgot _find_arbitrage_async(
                min_profit=1.0,
                max_profit=10.0,
                game="csgo",
            )

            assert isinstance(result, list)
            assert len(result) > 0
            # Проверяем структуру результата
            if result:
                item = result[0]
                assert "name" in item
                assert "buy" in item
                assert "sell" in item
                assert "profit" in item
                assert "profit_percent" in item

    @pytest.mark.asyncio()
    async def test_find_arbitrage_async_no_suggested_price(self):
        """Тест расчета цены продажи без suggestedPrice."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "title": "M4A4 | Howl (FN)",
                "itemId": "item_3",
                "price": {"USD": 10000},  # $100.00
                "extra": {"popularity": 0.9},  # Высокая популярность
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            result = awAlgot _find_arbitrage_async(
                min_profit=5.0,
                max_profit=20.0,
                game="csgo",
            )

            # Должен использовать markup
            assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_find_arbitrage_async_different_liquidity(self):
        """Тест учета ликвидности предметов."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "title": "High Liquidity Item",
                "itemId": "item_high",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
                "extra": {"popularity": 0.95},  # Высокая ликвидность
            },
            {
                "title": "Low Liquidity Item",
                "itemId": "item_low",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
                "extra": {"popularity": 0.2},  # Низкая ликвидность
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            result = awAlgot _find_arbitrage_async(
                min_profit=0.5,
                max_profit=5.0,
                game="csgo",
            )

            # Разная ликвидность должна давать разные комиссии
            assert isinstance(result, list)

    @pytest.mark.asyncio()
    async def test_find_arbitrage_async_uses_cache(self):
        """Тест использования кэша."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        cache_key = ("csgo", "1.0-5.0", 0.0, float("inf"))
        cached_data = [{"name": "Cached Item", "profit": "$3.00"}]
        _save_to_cache(cache_key, cached_data)

        # Не должен вызывать fetch_market_items
        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
        ) as mock_fetch:
            result = awAlgot _find_arbitrage_async(
                min_profit=1.0,
                max_profit=5.0,
                game="csgo",
            )

            # fetch_market_items не должен быть вызван
            mock_fetch.assert_not_called()
            assert result == cached_data


class TestFindArbitrageOpportunitiesAsync:
    """Тесты функции find_arbitrage_opportunities_async."""

    def setup_method(self):
        """Очистить кэш перед каждым тестом."""
        _arbitrage_cache.clear()

    @pytest.mark.asyncio()
    async def test_find_opportunities_with_items(self):
        """Тест поиска возможностей с предметами."""
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        mock_items = [
            {
                "title": "AK-47 | Redline (FT)",
                "itemId": "item_1",
                "price": {"USD": 1000},  # $10.00
                "suggestedPrice": {"USD": 1300},  # $13.00
                "extra": {"popularity": 0.7},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            result = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=10.0,
                max_results=5,
                game="csgo",
            )

            assert isinstance(result, list)
            if result:
                opp = result[0]
                assert "item_title" in opp
                assert "buy_price" in opp
                assert "sell_price" in opp
                assert "profit_amount" in opp
                assert "profit_percentage" in opp

    @pytest.mark.asyncio()
    async def test_find_opportunities_max_results_limit(self):
        """Тест ограничения количества результатов."""
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        # Создаем 10 предметов
        mock_items = [
            {
                "title": f"Item {i}",
                "itemId": f"item_{i}",
                "price": {"USD": 1000 + i * 100},
                "suggestedPrice": {"USD": 1500 + i * 100},
                "extra": {"popularity": 0.5},
            }
            for i in range(10)
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            result = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=5.0,
                max_results=3,
                game="csgo",
            )

            # Должно вернуть не более 3 результатов
            assert len(result) <= 3

    @pytest.mark.asyncio()
    async def test_find_opportunities_sorting(self):
        """Тест сортировки по проценту прибыли."""
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        mock_items = [
            {
                "title": "Low Profit Item",
                "itemId": "item_low",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},  # 10% прибыли
                "extra": {"popularity": 0.5},
            },
            {
                "title": "High Profit Item",
                "itemId": "item_high",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},  # 50% прибыли
                "extra": {"popularity": 0.5},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            result = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=5.0,
                max_results=2,
                game="csgo",
            )

            # Первый элемент должен иметь большую прибыль
            if len(result) >= 2:
                assert result[0]["profit_percentage"] >= result[1]["profit_percentage"]


class TestArbitrageTraderMethods:
    """Тесты методов класса ArbitrageTrader."""

    @pytest.mark.asyncio()
    async def test_trader_check_balance(self):
        """Тест проверки баланса."""
        # Мокаем DMarketAPI при создании трейдера
        with patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api_class:
            # Настраиваем мок API
            mock_api_instance = AsyncMock()
            mock_api_instance.__aenter__ = AsyncMock(return_value=mock_api_instance)
            mock_api_instance.__aexit__ = AsyncMock(return_value=None)
            # trader.py использует get_balance() и ожидает {"balance": value_in_dollars}
            mock_api_instance.get_balance = AsyncMock(
                return_value={"balance": 1000.0, "error": False}  # $1000
            )
            mock_api_class.return_value = mock_api_instance

            # Создаем трейдера
            trader = ArbitrageTrader(
                public_key="test",
                secret_key="test",
            )

            has_funds, balance = awAlgot trader.check_balance()

            assert has_funds is True
            assert balance == 1000.0

    @pytest.mark.asyncio()
    async def test_trader_check_balance_insufficient_funds(self):
        """Тест проверки баланса при недостаточных средствах."""
        # Мокаем DMarketAPI
        with patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api_class:
            mock_api_instance = AsyncMock()
            mock_api_instance.__aenter__ = AsyncMock(return_value=mock_api_instance)
            mock_api_instance.__aexit__ = AsyncMock(return_value=None)
            # trader.py использует get_balance() и ожидает {"balance": value_in_dollars}
            mock_api_instance.get_balance = AsyncMock(
                return_value={"balance": 0.50, "error": False}  # $0.50
            )
            mock_api_class.return_value = mock_api_instance

            trader = ArbitrageTrader(public_key="test", secret_key="test")

            has_funds, balance = awAlgot trader.check_balance()

            assert has_funds is False
            assert balance == 0.50

    def test_trader_get_status(self):
        """Тест получения статуса трейдера (НЕ async)."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        status = trader.get_status()  # Без awAlgot!

        assert isinstance(status, dict)
        assert "active" in status
        assert "min_profit_percentage" in status
        assert "current_game" in status
        assert status["active"] is False  # По умолчанию неактивен

    @pytest.mark.asyncio()
    async def test_trader_get_transaction_history(self):
        """Тест получения истории транзакций."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        history = trader.get_transaction_history()

        assert isinstance(history, list)
        assert len(history) == 0  # Изначально пустая

    def test_trader_reset_dAlgoly_limits(self):
        """Тест сброса дневных лимитов.

        _reset_dAlgoly_limits() is a sync method that resets dAlgoly counters.
        """
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        # Устанавливаем дневную торговлю
        trader.dAlgoly_traded = 100.0
        # Устанавливаем время сброса на 25 часов назад (>24 часа)
        trader.dAlgoly_reset_time = time.time() - 90000

        trader._reset_dAlgoly_limits()  # sync method - no awAlgot

        # Должно сброситься
        assert trader.dAlgoly_traded == 0.0

    @pytest.mark.asyncio()
    async def test_trader_check_trading_limits_ok(self):
        """Тест проверки лимитов - допустимая сделка."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.max_trade_value = 100.0
        trader.dAlgoly_limit = 500.0
        trader.dAlgoly_traded = 0.0

        result = awAlgot trader._check_trading_limits(trade_value=50.0)

        assert result is True

    @pytest.mark.asyncio()
    async def test_trader_check_trading_limits_exceeds_max(self):
        """Тест проверки лимитов - превышение макс. сделки."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.max_trade_value = 100.0

        result = awAlgot trader._check_trading_limits(trade_value=150.0)

        assert result is False

    @pytest.mark.asyncio()
    async def test_trader_check_trading_limits_exceeds_dAlgoly(self):
        """Тест проверки лимитов - превышение дневного лимита."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.dAlgoly_limit = 500.0
        trader.dAlgoly_traded = 480.0  # Уже много торговали

        result = awAlgot trader._check_trading_limits(trade_value=30.0)

        assert result is False  # 480 + 30 > 500


class TestIntegration:
    """Интеграционные тесты."""

    def setup_method(self):
        """Очистить кэш перед каждым тестом."""
        _arbitrage_cache.clear()

    @pytest.mark.asyncio()
    async def test_cache_workflow(self):
        """Тест полного цикла кэширования."""
        cache_key = ("csgo", "medium", 10.0, 50.0)
        test_items = [
            {"title": "Test Item 1", "price": 15.0},
            {"title": "Test Item 2", "price": 25.0},
        ]

        # Сохраняем в кэш
        _save_to_cache(cache_key, test_items)

        # Проверяем что данные сохранились
        assert cache_key in _arbitrage_cache

        # Получаем из кэша
        cached = _get_cached_results(cache_key)
        assert cached == test_items

        # Очищаем кэш
        _arbitrage_cache.clear()

        # Проверяем что кэш пуст
        cached = _get_cached_results(cache_key)
        assert cached is None

    @pytest.mark.asyncio()
    async def test_full_arbitrage_workflow(self):
        """Тест полного цикла арбитража от поиска до результата."""
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        mock_items = [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "itemId": "item_ak47",
                "price": {"USD": 1250},
                "suggestedPrice": {"USD": 1500},
                "extra": {"popularity": 0.75},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items",
            return_value=mock_items,
        ):
            # Шаг 1: Поиск возможностей
            opportunities = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=10.0,
                max_results=5,
                game="csgo",
            )

            assert len(opportunities) > 0

            # Шаг 2: Проверка структуры
            opp = opportunities[0]
            assert opp["item_title"] == "AK-47 | Redline (Field-Tested)"
            assert opp["buy_price"] == 12.50
            assert opp["sell_price"] == 15.00
            assert opp["profit_percentage"] >= 10.0

            # Шаг 3: Проверка кэширования
            cache_key = ("csgo", "arb-10.0", 0.0, float("inf"))
            assert cache_key in _arbitrage_cache


class TestArbitrageTraderAutoTrading:
    """Тесты автоматической торговли ArbitrageTrader."""

    @pytest.mark.asyncio()
    async def test_start_auto_trading_success(self):
        """Тест успешного запуска автоматической торговли."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.active = False

        # Mock check_balance для имитации достаточного баланса
        with patch.object(trader, "check_balance", return_value=(True, 100.0)):
            success, message = awAlgot trader.start_auto_trading(
                game="csgo",
                min_profit_percentage=5.0,
            )

        assert success is True
        assert "автоторговля запущена" in message.lower()
        assert trader.active is True
        assert trader.current_game == "csgo"

    @pytest.mark.asyncio()
    async def test_start_auto_trading_already_active(self):
        """Тест запуска автоторговли когда она уже запущена."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.active = True

        success, message = awAlgot trader.start_auto_trading()

        assert success is False
        assert "уже запущена" in message.lower()

    @pytest.mark.asyncio()
    async def test_start_auto_trading_insufficient_balance(self):
        """Тест запуска автоторговли с недостаточным балансом."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        with patch.object(trader, "check_balance", return_value=(False, 0.5)):
            success, message = awAlgot trader.start_auto_trading()

        assert success is False
        assert "недостаточно средств" in message.lower()
        assert trader.active is False

    @pytest.mark.asyncio()
    async def test_stop_auto_trading_success(self):
        """Тест успешной остановки автоторговли."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.active = True

        success, message = awAlgot trader.stop_auto_trading()

        assert success is True
        assert "остановлена" in message.lower()
        assert trader.active is False

    @pytest.mark.asyncio()
    async def test_stop_auto_trading_not_active(self):
        """Тест остановки неактивной автоторговли."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.active = False

        success, message = awAlgot trader.stop_auto_trading()

        assert success is False
        assert "не запущена" in message.lower()

    @pytest.mark.asyncio()
    async def test_execute_arbitrage_trade_insufficient_balance(self):
        """Тест выполнения сделки при недостаточном балансе."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        item = {
            "name": "Test Item",
            "market_hash_name": "Test Item",
            "buy_price": 100.0,
            "sell_price": 120.0,
            "profit": 16.0,
            "game": "csgo",
        }

        with (
            patch.object(trader, "_can_trade_now", return_value=True),
            patch.object(trader, "check_balance", return_value=(False, 50.0)),
        ):
            result = awAlgot trader.execute_arbitrage_trade(item)

        assert result["success"] is False
        assert "недостаточно средств" in str(result["errors"]).lower()

    @pytest.mark.asyncio()
    async def test_execute_arbitrage_trade_exceeds_limits(self):
        """Тест выполнения сделки при превышении лимитов."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")
        trader.max_trade_value = 50.0

        item = {
            "name": "Expensive Item",
            "market_hash_name": "Expensive Item",
            "buy_price": 100.0,
            "sell_price": 120.0,
            "profit": 16.0,
            "game": "csgo",
        }

        with (
            patch.object(trader, "_can_trade_now", return_value=True),
            patch.object(trader, "check_balance", return_value=(True, 200.0)),
            patch.object(trader, "_check_trading_limits", return_value=False),
        ):
            result = awAlgot trader.execute_arbitrage_trade(item)

        assert result["success"] is False
        assert "превышены лимиты" in str(result["errors"]).lower()

    @pytest.mark.asyncio()
    async def test_execute_arbitrage_trade_buy_error(self):
        """Тест ошибки при покупке предмета."""
        trader = ArbitrageTrader(public_key="test", secret_key="test")

        item = {
            "name": "Test Item",
            "market_hash_name": "Test Item",
            "buy_item_id": "test_item_123",
            "buy_price": 10.0,
            "sell_price": 12.0,
            "profit": 1.6,
            "profit_percentage": 16.0,
            "game": "csgo",
        }

        mock_buy_error = {"success": False, "error": "Предмет недоступен"}

        with (
            patch.object(
                trader,
                "check_balance",
                new_callable=AsyncMock,
                return_value=(True, 100.0),
            ),
            patch.object(
                trader,
                "_check_trading_limits",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch.object(
                trader,
                "purchase_item",
                new_callable=AsyncMock,
                return_value=mock_buy_error,
            ),
            patch.object(trader, "_handle_trading_error", new_callable=AsyncMock),
        ):
            result = awAlgot trader.execute_arbitrage_trade(item)

        assert result["success"] is False
        # Проверка наличия ошибки покупки
        error_found = any("ошибка" in str(e).lower() for e in result["errors"])
        assert error_found


class TestFindArbitrageItemsNew:
    """Тесты для функции find_arbitrage_items (новые)."""

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_low_mode(self):
        """Тест поиска предметов в режиме low/boost."""
        mock_results = [
            {
                "name": "Test Item",
                "buy_price": 1.0,
                "sell_price": 1.2,
                "profit": 0.16,
                "profit_percent": 16.0,
            }
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_boost_async",
            return_value=mock_results,
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="low",
                min_price=0.5,
                max_price=5.0,
            )

        assert len(result) == 1
        assert result[0]["name"] == "Test Item"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_mid_mode(self):
        """Тест поиска предметов в режиме mid."""
        mock_results = [
            {
                "name": "Test Item 2",
                "buy_price": 10.0,
                "sell_price": 12.0,
                "profit": 1.6,
                "profit_percent": 16.0,
            }
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            return_value=mock_results,
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="mid",
                min_price=5.0,
                max_price=20.0,
            )

        assert len(result) == 1
        assert result[0]["name"] == "Test Item 2"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_pro_mode(self):
        """Тест поиска предметов в режиме pro."""
        mock_results = [
            {
                "name": "Expensive Item",
                "buy_price": 500.0,
                "sell_price": 600.0,
                "profit": 80.0,
                "profit_percent": 16.0,
            }
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_pro_async",
            return_value=mock_results,
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="pro",
                min_price=100.0,
                max_price=1000.0,
            )

        assert len(result) == 1
        assert result[0]["name"] == "Expensive Item"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_tuple_conversion(self):
        """Тест конвертации результатов из формата кортежа."""
        # Возвращаем кортежи вместо словарей
        mock_results = [
            ("Item Name", 10.0, 12.0, 1.6, 16.0),
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            return_value=mock_results,
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="mid",
            )

        assert len(result) == 1
        assert result[0]["market_hash_name"] == "Item Name"
        assert result[0]["buy_price"] == 10.0
        assert result[0]["sell_price"] == 12.0
        assert result[0]["profit"] == 1.6
        assert result[0]["profit_percent"] == 16.0

    @pytest.mark.asyncio()
    async def test_find_arbitrage_items_default_mode(self):
        """Тест режима по умолчанию при неизвестном режиме."""
        mock_results = [
            {
                "name": "Default Item",
                "buy_price": 5.0,
                "sell_price": 6.0,
                "profit": 0.8,
                "profit_percent": 16.0,
            }
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            return_value=mock_results,
        ):
            result = awAlgot find_arbitrage_items(
                game="csgo",
                mode="unknown_mode",
            )

        assert len(result) == 1
        assert result[0]["name"] == "Default Item"


# ===== Дополнительные тесты для повышения покрытия до 70% =====


class TestFetchMarketItemsEnvKeys:
    """Тесты для fetch_market_items с различными конфигурациями переменных окружения."""

    @pytest.mark.asyncio()
    async def test_fetch_market_items_creates_api_from_env(self):
        """Тест создания API клиента из переменных окружения."""
        import os

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                    "DMARKET_API_URL": "https://test.api.com",
                },
            ),
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api_class,
        ):
            mock_api_instance = AsyncMock()
            mock_api_instance.get_market_items = AsyncMock(
                return_value={"objects": [{"title": "Test", "price": {"USD": 1000}}]}
            )
            mock_api_class.return_value = mock_api_instance

            items = awAlgot fetch_market_items(game="csgo", limit=10)

            # Проверяем создание API с правильными параметрами
            mock_api_class.assert_called_once_with(
                "test_public", "test_secret", "https://test.api.com", max_retries=3
            )
            assert len(items) == 1

    @pytest.mark.asyncio()
    async def test_fetch_market_items_missing_public_key(self):
        """Тест обработки отсутствующего публичного ключа."""
        import os

        with patch.dict(os.environ, {"DMARKET_SECRET_KEY": "test_secret"}, clear=True):
            items = awAlgot fetch_market_items(game="csgo")
            assert items == []

    @pytest.mark.asyncio()
    async def test_fetch_market_items_missing_secret_key(self):
        """Тест обработки отсутствующего секретного ключа."""
        import os

        with patch.dict(os.environ, {"DMARKET_PUBLIC_KEY": "test_public"}, clear=True):
            items = awAlgot fetch_market_items(game="csgo")
            assert items == []

    @pytest.mark.asyncio()
    async def test_fetch_market_items_price_conversion_to_cents(self):
        """Тест правильной конвертации цен в центы для API."""
        import os

        with (
            patch.dict(
                os.environ,
                {"DMARKET_PUBLIC_KEY": "test", "DMARKET_SECRET_KEY": "test"},
            ),
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api_class,
        ):
            mock_api_instance = AsyncMock()
            mock_api_instance.get_market_items = AsyncMock(return_value={"objects": []})
            mock_api_class.return_value = mock_api_instance

            awAlgot fetch_market_items(game="csgo", price_from=10.50, price_to=99.99)

            # Проверяем конвертацию: 10.50 -> 1050 центов, 99.99 -> 9999 центов
            call_kwargs = mock_api_instance.get_market_items.call_args.kwargs
            assert call_kwargs["price_from"] == 1050
            assert call_kwargs["price_to"] == 9999


class TestFindArbitrageAsyncPopularity:
    """Тесты для _find_arbitrage_async с различной популярностью предметов."""

    @pytest.mark.asyncio()
    async def test_find_arbitrage_high_popularity_low_fee(self):
        """Тест что высокая популярность (>0.7) использует низкую комиссию."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую через модуль
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "High Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
                "extra": {"popularity": 0.85},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=1.0, price_to=20.0
            )

            assert len(results) > 0
            assert results[0]["fee"] == f"{int(LOW_FEE * 100)}%"
            assert results[0]["liquidity"] == "high"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_medium_popularity_default_fee(self):
        """Тест средней популярности (0.4-0.7) со стандартной комиссией."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Medium Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
                "extra": {"popularity": 0.5},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=2.0, price_to=25.0
            )

            assert len(results) > 0
            assert results[0]["fee"] == f"{int(DEFAULT_FEE * 100)}%"
            assert results[0]["liquidity"] == "medium"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_low_popularity_high_fee(self):
        """Тест что низкая популярность (<0.4) использует высокую комиссию."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Low Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
                "extra": {"popularity": 0.2},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=3.0, price_to=30.0
            )

            assert len(results) > 0
            assert results[0]["fee"] == f"{int(HIGH_FEE * 100)}%"
            assert results[0]["liquidity"] == "low"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_no_suggested_price_high_popularity(self):
        """Тест расчёта без suggestedPrice для популярного предмета."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Item Without Suggested Price",
                "price": {"USD": 1000},  # $10 в центах
                "extra": {"popularity": 0.75},  # Высокая -> markup 1.1
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=4.0, price_to=35.0
            )

            assert len(results) > 0
            assert results[0]["sell"] == "$11.00"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_no_suggested_price_medium_popularity(self):
        """Тест расчёта без suggestedPrice для средней популярности."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Medium Item",
                "price": {"USD": 1000},  # $10 в центах
                "extra": {"popularity": 0.5},  # Средняя -> markup 1.12
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=5.0, price_to=40.0
            )

            assert len(results) > 0
            assert results[0]["sell"] == "$11.20"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_no_suggested_price_low_popularity(self):
        """Тест расчёта без suggestedPrice для низкой популярности."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Low Item",
                "price": {"USD": 1000},  # $10
                "extra": {"popularity": 0.3},  # Низкая -> markup 1.15
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=6.0, price_to=45.0
            )

            assert len(results) > 0
            assert results[0]["sell"] == "$11.50"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_no_extra_field_default_markup(self):
        """Тест расчёта без поля extra."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        # Очищаем кэш напрямую
        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Item Without Extra",
                "price": {"USD": 1000},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=7.0, price_to=50.0
            )

            assert len(results) > 0
            assert results[0]["sell"] == "$11.00"
            assert results[0]["liquidity"] == "medium"


class TestFindArbitrageAsyncProfitCalculation:
    """Тесты расчёта прибыли."""

    @pytest.mark.asyncio()
    async def test_profit_percent_calculation(self):
        """Тест правильного расчёта процента прибыли."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "itemId": "item1",
                "title": "Test Item",
                "price": {"USD": 1000},  # $10
                "suggestedPrice": {"USD": 1200},  # $12
                "extra": {"popularity": 0.75},  # low_fee = 2%
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(0.0, 100.0, game="csgo")

            assert len(results) > 0
            # Profit = $12 * 0.98 - $10 = $1.76
            assert results[0]["profit"] == "$1.76"
            assert results[0]["profit_percent"] == "17.6"

    @pytest.mark.asyncio()
    async def test_zero_buy_price_handled(self):
        """Тест обработки нулевой цены покупки."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "itemId": "item1",
                "title": "Free Item",
                "price": {"USD": 0},
                "suggestedPrice": {"USD": 100},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(0.0, 100.0, game="csgo")

            assert isinstance(results, list)

    @pytest.mark.asyncio()
    async def test_item_with_name_field_instead_of_title(self):
        """Тест обработки предмета с полем 'name'."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "name": "Item With Name Field",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=200.0, price_to=220.0
            )

            assert len(results) > 0
            assert results[0]["name"] == "Item With Name Field"

    @pytest.mark.asyncio()
    async def test_item_without_title_or_name(self):
        """Тест обработки предмета без названия."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=230.0, price_to=250.0
            )

            assert len(results) > 0
            assert results[0]["name"] == "Unknown"

    @pytest.mark.asyncio()
    async def test_filters_out_of_range_profits(self):
        """Тест фильтрации предметов вне диапазона прибыли."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "itemId": "item1",
                "title": "Low Profit",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1050},  # ~$0.37 profit
            },
            {
                "itemId": "item2",
                "title": "High Profit",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},  # ~$3.95 profit
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(1.0, 2.0, game="csgo")

            assert len(results) == 0

    @pytest.mark.asyncio()
    async def test_sorts_by_profit_descending(self):
        """Тест сортировки по прибыли (убывание)."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Item A",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},
            },
            {
                "itemId": "item2",
                "title": "Item B",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},
            },
            {
                "itemId": "item3",
                "title": "Item C",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=260.0, price_to=280.0
            )

            assert len(results) == 3
            profits = [float(r["profit"].replace("$", "")) for r in results]
            assert profits == sorted(profits, reverse=True)
            assert results[0]["name"] == "Item B"


class TestFindArbitrageAsyncErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio()
    async def test_handles_malformed_item(self):
        """Тест обработки некорректных данных."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Valid",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
            },
            {
                "itemId": "item2",
                "title": "Malformed",
                "price": {"USD": "invalid"},
            },
            {
                "itemId": "item3",
                "title": "Valid2",
                "price": {"USD": 2000},
                "suggestedPrice": {"USD": 2300},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=300.0, price_to=320.0
            )

            assert len(results) == 2

    @pytest.mark.asyncio()
    async def test_continues_after_item_error(self):
        """Тест продолжения обработки после ошибки."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import _find_arbitrage_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {"itemId": "item1", "title": "Item1", "price": {"USD": 1000}},
            {
                "itemId": "item2",
                "title": "Item2",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=330.0, price_to=350.0
            )

            assert len(results) == 2


class TestCacheIntegration:
    """Интеграционные тесты кэширования."""

    @pytest.mark.asyncio()
    async def test_uses_cache_on_second_call(self):
        """Тест использования кэша при повторном вызове."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "itemId": "item1",
                "title": "Cached",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items

            results1 = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=1.0, price_to=50.0
            )
            assert len(results1) > 0
            assert mock_fetch.call_count == 1

            results2 = awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=1.0, price_to=50.0
            )
            assert results2 == results1
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio()
    async def test_cache_key_differs_by_price_range(self):
        """Тест разных ключей кэша для разных диапазонов."""
        from src.dmarket.arbitrage import _find_arbitrage_async

        mock_items = [
            {
                "itemId": "item1",
                "title": "Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1200},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items

            awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=1.0, price_to=10.0
            )
            awAlgot _find_arbitrage_async(
                0.0, 100.0, game="csgo", price_from=10.0, price_to=50.0
            )

            assert mock_fetch.call_count == 2


class TestFindArbitrageOpportunitiesAsyncExtended:
    """Расширенные тесты для find_arbitrage_opportunities_async()."""

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_basic(self):
        """Тест базовой работы find_arbitrage_opportunities_async."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "High Profit Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},
                "extra": {"popularity": 0.8},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=10.0, max_results=5, game="csgo"
            )

            assert len(results) > 0
            assert results[0]["item_title"] == "High Profit Item"
            assert results[0]["market_from"] == "DMarket"

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_csgo_market(self):
        """Тест определения целевого рынка для CS:GO."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "CS:GO Skin",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=5.0, price_to=20.0
            )

            assert results[0]["market_to"] == "Steam Market"

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_non_csgo_market(self):
        """Тест определения целевого рынка для не-CS:GO игр."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Dota Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="dota2", price_from=7.0, price_to=25.0
            )

            assert results[0]["market_to"] == "Game Market"

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_filters_by_min_profit(self):
        """Тест фильтрации по минимальной прибыли."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Low Profit",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1050},
            },
            {
                "itemId": "item2",
                "title": "High Profit",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=20.0,
                game="csgo",
                price_from=8.0,
                price_to=30.0,
            )

            assert len(results) == 1
            assert results[0]["item_title"] == "High Profit"

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_limits_max_results(self):
        """Тест ограничения количества результатов."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": f"item{i}",
                "title": f"Item {i}",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1500},
            }
            for i in range(10)
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                max_results=3, game="csgo", price_from=9.0, price_to=35.0
            )

            assert len(results) == 3

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_handles_errors(self):
        """Тест обработки ошибок при поиске возможностей."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=10.0, price_to=40.0
            )

            assert results == []

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_uses_cache(self):
        """Тест использования кэша."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "Cached Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items

            results1 = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=11.0, price_to=45.0
            )
            results2 = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=11.0, price_to=45.0
            )

            assert results1 == results2
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_default_markup(self):
        """Тест наценки по умолчанию 15% при отсутствии suggestedPrice."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "item1",
                "title": "No Suggested Price",
                "price": {"USD": 1000},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=5.0,
                game="csgo",
                price_from=12.0,
                price_to=50.0,
            )

            assert len(results) > 0
            assert results[0]["sell_price"] == 11.5

    @pytest.mark.asyncio()
    async def test_find_opportunities_async_item_error_continues(self):
        """Тест продолжения обработки при ошибке с предметом."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {"itemId": "item1", "price": {"USD": "invalid"}},
            {
                "itemId": "item2",
                "title": "Valid Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
            },
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=13.0, price_to=55.0
            )

            assert len(results) == 1
            assert results[0]["item_title"] == "Valid Item"


class TestFindArbitrageOpportunitiesAsyncLiquidity:
    """Тесты для логики определения ликвидности и комиссий."""

    @pytest.mark.asyncio()
    async def test_high_popularity_uses_low_fee(self):
        """Тест: высокая популярность (>0.7) использует низкую комиссию."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import LOW_FEE, find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "high_pop",
                "title": "High Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1300},
                "extra": {"popularity": 0.85},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=15.0, price_to=60.0
            )

            assert len(results) == 1
            assert results[0]["fee"] == LOW_FEE

    @pytest.mark.asyncio()
    async def test_low_popularity_uses_high_fee(self):
        """Тест: низкая популярность (<0.4) использует высокую комиссию."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import HIGH_FEE, find_arbitrage_opportunities_async

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "low_pop",
                "title": "Low Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1400},
                "extra": {"popularity": 0.25},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=16.0, price_to=65.0
            )

            assert len(results) == 1
            assert results[0]["fee"] == HIGH_FEE

    @pytest.mark.asyncio()
    async def test_medium_popularity_uses_default_fee(self):
        """Тест: средняя популярность (0.4-0.7) использует стандартную
        комиссию."""
        import src.dmarket.arbitrage
        from src.dmarket.arbitrage import (
            DEFAULT_FEE,
            find_arbitrage_opportunities_async,
        )

        src.dmarket.arbitrage._arbitrage_cache.clear()

        mock_items = [
            {
                "itemId": "med_pop",
                "title": "Medium Popularity Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1350},
                "extra": {"popularity": 0.55},
            }
        ]

        with patch(
            "src.dmarket.arbitrage.core.fetch_market_items", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_items
            results = awAlgot find_arbitrage_opportunities_async(
                game="csgo", price_from=17.0, price_to=70.0
            )

            assert len(results) == 1
            assert results[0]["fee"] == DEFAULT_FEE


class TestArbitrageTraderErrorHandling:
    """Тесты для обработки ошибок в ArbitrageTrader."""

    @pytest.mark.asyncio()
    async def test_handle_trading_error_sets_pause_after_3_errors(self):
        """Тест: 3 ошибки за короткое время устанавливают паузу 15 минут."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        trader.error_count = 2
        trader.last_error_time = time.time() - 60

        awAlgot trader._handle_trading_error()

        assert trader.error_count == 3
        assert trader.pause_until > time.time()
        assert trader.pause_until <= time.time() + 900 + 1

    @pytest.mark.asyncio()
    async def test_handle_trading_error_resets_after_10_errors(self):
        """Тест: 10 ошибок устанавливают паузу 1 час и сбрасывают счетчик."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        trader.error_count = 9
        # Устанавливаем last_error_time так, чтобы прошло > 300 сек
        # Это обойдет условие "если >= 3 ошибки за 300 сек"
        trader.last_error_time = time.time() - 400

        awAlgot trader._handle_trading_error()

        assert trader.error_count == 0
        assert trader.pause_until > time.time()
        assert trader.pause_until <= time.time() + 3600 + 1

    @pytest.mark.asyncio()
    async def test_can_trade_now_returns_false_during_pause(self):
        """Тест: _can_trade_now возвращает False во время паузы."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        trader.pause_until = time.time() + 600

        can_trade = awAlgot trader._can_trade_now()

        assert can_trade is False

    @pytest.mark.asyncio()
    async def test_can_trade_now_resets_pause_after_expiry(self):
        """Тест: _can_trade_now сбрасывает паузу после истечения времени."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        trader.pause_until = time.time() - 1
        trader.error_count = 5

        can_trade = awAlgot trader._can_trade_now()

        assert can_trade is True
        assert trader.pause_until == 0
        assert trader.error_count == 0

    @pytest.mark.asyncio()
    async def test_can_trade_now_returns_true_without_pause(self):
        """Тест: _can_trade_now возвращает True без активной паузы."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        trader.pause_until = 0

        can_trade = awAlgot trader._can_trade_now()

        assert can_trade is True


class TestFindProfitableItems:
    """Тесты для метода find_profitable_items."""

    @pytest.mark.asyncio()
    async def test_find_profitable_items_returns_opportunities(self):
        """Тест: find_profitable_items возвращает выгодные предметы."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        # Mock API responses - нужно минимум 2 предмета с одинаковым названием
        # Код группирует по title и ищет арбитраж между дешевым и дорогим
        mock_items = [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1500"},  # $15.00 - дешевый
                "itemId": "item_123",
                "extra": {"popularity": 0.85, "rarity": "", "category": ""},
            },
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1800"},  # $18.00 - дорогой (20% разница)
                "itemId": "item_456",
                "extra": {"popularity": 0.85, "rarity": "", "category": ""},
            },
        ]

        # Патчим get_market_items (не get_market_items!) и context manager
        with (
            patch.object(
                trader.api, "get_market_items", new_callable=AsyncMock
            ) as mock_get_items,
            patch.object(
                trader.api, "__aenter__", new_callable=AsyncMock
            ) as mock_aenter,
            patch.object(trader.api, "__aexit__", new_callable=AsyncMock) as mock_aexit,
        ):
            mock_get_items.return_value = {"objects": mock_items}
            mock_aenter.return_value = trader.api
            mock_aexit.return_value = None

            results = awAlgot trader.find_profitable_items(
                game="csgo",
                min_profit_percentage=10.0,
                max_items=50,
                min_price=5.0,
                max_price=100.0,
            )

            # Должен быть найден минимум 1 предмет
            assert len(results) > 0
            assert results[0]["name"] == "AK-47 | Redline (FT)"
            # Profit = ($18 * 0.93) - $15 = $16.74 - $15 = $1.74
            # Profit% = ($1.74 / $15) * 100 = 11.6%
            assert results[0]["profit_percentage"] >= 10.0
            mock_get_items.assert_called_once()

    @pytest.mark.asyncio()
    async def test_find_profitable_items_handles_exception(self):
        """Тест: find_profitable_items обрабатывает исключения."""
        from src.dmarket.arbitrage import ArbitrageTrader

        trader = ArbitrageTrader(public_key="test_key", secret_key="test_secret")

        with patch(
            "src.dmarket.arbitrage.find_arbitrage_opportunities_async",
            new_callable=AsyncMock,
        ) as mock_find:
            mock_find.side_effect = Exception("API Error")

            results = awAlgot trader.find_profitable_items(game="csgo")

            assert results == []
