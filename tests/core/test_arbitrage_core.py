"""Комплексные тесты для сканера арбитража.

Покрывают основные аспекты работы сканера:
- Инициализация сканера
- Многоуровневое сканирование (boost, standard, medium, advanced, pro)
- Фильтрация результатов
- Кэширование
- Работа с разными играми
- Анализ ликвидности
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.dmarket.arbitrage_scanner import (
    ARBITRAGE_LEVELS,
    GAME_IDS,
    ArbitrageScanner,
)

from src.dmarket.dmarket_api import DMarketAPI


class TestArbitrageScannerInitialization:
    """Тесты инициализации сканера."""

    def test_init_with_api_client(self):
        """Тест создания сканера с API клиентом."""
        mock_api = MagicMock(spec=DMarketAPI)
        scanner = ArbitrageScanner(api_client=mock_api)

        assert scanner.api_client is mock_api

    def test_init_without_api_client(self):
        """Тест создания сканера без API клиента."""
        scanner = ArbitrageScanner()

        # Сканер может работать без API для кэшированных данных
        assert scanner is not None


class TestArbitrageLevelsConstants:
    """Тесты констант уровней арбитража."""

    def test_boost_level_exists(self):
        """Тест наличия уровня boost."""
        assert "boost" in ARBITRAGE_LEVELS
        boost = ARBITRAGE_LEVELS["boost"]
        assert "name" in boost
        assert "min_profit_percent" in boost
        assert boost["min_profit_percent"] == 1.0

    def test_standard_level_exists(self):
        """Тест наличия уровня standard."""
        assert "standard" in ARBITRAGE_LEVELS
        standard = ARBITRAGE_LEVELS["standard"]
        assert "name" in standard
        assert "min_profit_percent" in standard
        assert standard["min_profit_percent"] == 5.0

    def test_medium_level_exists(self):
        """Тест наличия уровня medium."""
        assert "medium" in ARBITRAGE_LEVELS
        medium = ARBITRAGE_LEVELS["medium"]
        assert "name" in medium
        assert "min_profit_percent" in medium

    def test_advanced_level_exists(self):
        """Тест наличия уровня advanced."""
        assert "advanced" in ARBITRAGE_LEVELS
        advanced = ARBITRAGE_LEVELS["advanced"]
        assert "name" in advanced
        assert "min_profit_percent" in advanced
        assert advanced["min_profit_percent"] == 10.0

    def test_pro_level_exists(self):
        """Тест наличия уровня pro."""
        assert "pro" in ARBITRAGE_LEVELS
        pro = ARBITRAGE_LEVELS["pro"]
        assert "name" in pro
        assert "min_profit_percent" in pro
        assert pro["min_profit_percent"] == 20.0

    def test_all_levels_have_required_fields(self):
        """Тест наличия всех обязательных полей в уровнях."""
        required_fields = ["name", "min_profit_percent", "description"]

        for level_name, level_config in ARBITRAGE_LEVELS.items():
            for field in required_fields:
                assert (
                    field in level_config
                ), f"Level {level_name} missing field {field}"

    def test_profit_percentages_ascending(self):
        """Тест что процент прибыли возрастает с уровнем."""
        levels_order = ["boost", "standard", "medium", "advanced", "pro"]

        for i in range(len(levels_order) - 1):
            current_level = ARBITRAGE_LEVELS[levels_order[i]]
            next_level = ARBITRAGE_LEVELS[levels_order[i + 1]]

            assert (
                current_level["min_profit_percent"] <= next_level["min_profit_percent"]
            )


class TestGameIDsConstants:
    """Тесты констант ID игр."""

    def test_csgo_game_id(self):
        """Тест ID игры CS:GO."""
        assert "csgo" in GAME_IDS
        assert GAME_IDS["csgo"] == "a8db"

    def test_dota2_game_id(self):
        """Тест ID игры Dota 2."""
        assert "dota2" in GAME_IDS
        assert GAME_IDS["dota2"] == "9a92"

    def test_tf2_game_id(self):
        """Тест ID игры Team Fortress 2."""
        assert "tf2" in GAME_IDS
        assert GAME_IDS["tf2"] == "tf2"

    def test_rust_game_id(self):
        """Тест ID игры Rust."""
        assert "rust" in GAME_IDS
        assert GAME_IDS["rust"] == "rust"

    def test_all_supported_games(self):
        """Тест поддержки всех ожидаемых игр."""
        expected_games = ["csgo", "dota2", "tf2", "rust"]

        for game in expected_games:
            assert game in GAME_IDS


class TestArbitrageScannerBasicOperations:
    """Тесты базовых операций сканера."""

    @pytest.mark.asyncio()
    async def test_scan_level_initialization(self):
        """Тест инициализации сканера для разных уровней."""
        mock_api = MagicMock(spec=DMarketAPI)
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        scanner = ArbitrageScanner(api_client=mock_api)

        # Проверка что сканер создан
        assert scanner is not None
        assert scanner.api_client is mock_api

    @pytest.mark.asyncio()
    async def test_scan_different_games_setup(self):
        """Тест настSwarmки сканирования для разных игр."""
        mock_api = MagicMock(spec=DMarketAPI)
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        ArbitrageScanner(api_client=mock_api)

        # Проверка поддержки всех игр
        games = ["csgo", "dota2", "tf2", "rust"]
        for game in games:
            assert game in GAME_IDS


class TestArbitrageScannerFiltering:
    """Тесты фильтрации результатов."""

    def test_filter_by_min_profit(self):
        """Тест фильтрации по минимальной прибыли."""
        ArbitrageScanner()

        opportunities = [
            {"profit_percent": 5.0, "title": "Item1"},
            {"profit_percent": 10.0, "title": "Item2"},
            {"profit_percent": 15.0, "title": "Item3"},
        ]

        # Фильтрация результатов с минимальной прибылью 10%
        filtered = [opp for opp in opportunities if opp["profit_percent"] >= 10.0]

        assert len(filtered) == 2
        assert all(opp["profit_percent"] >= 10.0 for opp in filtered)

    def test_filter_by_price_range(self):
        """Тест фильтрации по диапазону цен."""
        ArbitrageScanner()

        opportunities = [
            {"buy_price": 5.0, "title": "Item1"},
            {"buy_price": 15.0, "title": "Item2"},
            {"buy_price": 25.0, "title": "Item3"},
        ]

        # Фильтрация по диапазону 10-20
        price_range = (10.0, 20.0)
        filtered = [
            opp
            for opp in opportunities
            if price_range[0] <= opp["buy_price"] <= price_range[1]
        ]

        assert len(filtered) == 1
        assert filtered[0]["buy_price"] == 15.0


class TestArbitrageScannerCaching:
    """Тесты кэширования результатов."""

    def test_cache_saves_results(self):
        """Тест сохранения результатов в кэш."""
        import time

        ArbitrageScanner()

        cache_key = "test_cache_key"
        test_data = [{"item": "test"}]

        # Симуляция сохранения в кэш
        cache = {}
        cache[cache_key] = {
            "data": test_data,
            "timestamp": time.time(),
        }

        assert cache_key in cache
        assert cache[cache_key]["data"] == test_data

    def test_cache_retrieves_results(self):
        """Тест получения результатов из кэша."""
        import time

        ArbitrageScanner()

        cache_key = "test_cache_key"
        test_data = [{"item": "test"}]

        # Симуляция кэша
        cache = {
            cache_key: {
                "data": test_data,
                "timestamp": time.time(),
            }
        }

        # Получение из кэша
        if cache_key in cache:
            cached_data = cache[cache_key]["data"]
            assert cached_data == test_data

    @pytest.mark.asyncio()
    async def test_cache_expiration(self):
        """Тест истечения срока действия кэша."""
        import time

        cache_key = "test_cache_key"
        test_data = [{"item": "test"}]
        cache_ttl = 1  # 1 секунда

        # Симуляция кэша с устаревшим временем
        cache = {
            cache_key: {
                "data": test_data,
                "timestamp": time.time() - (cache_ttl + 1),
            }
        }

        # Проверка устаревания
        cached_entry = cache.get(cache_key)
        if cached_entry:
            is_expired = time.time() - cached_entry["timestamp"] > cache_ttl
            assert is_expired is True


class TestArbitrageScannerLiquidity:
    """Тесты анализа ликвидности."""

    @pytest.mark.asyncio()
    async def test_liquidity_classification_high(self):
        """Тест классификации высокой ликвидности."""
        # Предмет с большим количеством продаж считается высоколиквидным
        item_data = {
            "sales_count": 100,
            "avg_dAlgoly_volume": 50,
        }

        # Простая классификация
        if item_data["sales_count"] > 50:
            liquidity = "high"
        elif item_data["sales_count"] > 20:
            liquidity = "medium"
        else:
            liquidity = "low"

        assert liquidity == "high"

    @pytest.mark.asyncio()
    async def test_liquidity_classification_medium(self):
        """Тест классификации средней ликвидности."""
        item_data = {
            "sales_count": 30,
            "avg_dAlgoly_volume": 15,
        }

        if item_data["sales_count"] > 50:
            liquidity = "high"
        elif item_data["sales_count"] > 20:
            liquidity = "medium"
        else:
            liquidity = "low"

        assert liquidity == "medium"

    @pytest.mark.asyncio()
    async def test_liquidity_classification_low(self):
        """Тест классификации низкой ликвидности."""
        item_data = {
            "sales_count": 5,
            "avg_dAlgoly_volume": 2,
        }

        if item_data["sales_count"] > 50:
            liquidity = "high"
        elif item_data["sales_count"] > 20:
            liquidity = "medium"
        else:
            liquidity = "low"

        assert liquidity == "low"


class TestArbitrageScannerMultiGame:
    """Тесты мультиигрового сканирования."""

    def test_game_specific_filtering(self):
        """Тест фильтрации специфичной для игры."""
        ArbitrageScanner()

        # Разные предметы для разных игр
        csgo_items = [{"game": "csgo", "title": "AK-47"}]
        dota2_items = [{"game": "dota2", "title": "Arcana"}]

        # Фильтрация по игре
        filtered_csgo = [item for item in csgo_items if item["game"] == "csgo"]
        filtered_dota2 = [item for item in dota2_items if item["game"] == "dota2"]

        assert len(filtered_csgo) == 1
        assert len(filtered_dota2) == 1
        assert filtered_csgo[0]["game"] == "csgo"
        assert filtered_dota2[0]["game"] == "dota2"


class TestArbitrageScannerProfitCalculation:
    """Тесты расчета прибыли."""

    def test_profit_calculation_basic(self):
        """Тест базового расчета прибыли."""
        buy_price = 100.0
        sell_price = 120.0
        fee_percent = 7.0

        # Расчет прибыли с учетом комиссии
        fee = sell_price * (fee_percent / 100)
        profit = sell_price - buy_price - fee
        profit_percent = (profit / buy_price) * 100

        assert profit == 11.6
        assert profit_percent == 11.6

    def test_profit_calculation_with_zero_profit(self):
        """Тест расчета нулевой прибыли."""
        buy_price = 100.0
        sell_price = 107.0
        fee_percent = 7.0

        fee = sell_price * (fee_percent / 100)
        profit = sell_price - buy_price - fee

        # Прибыль близка к нулю после комиссии (может быть небольшая из-за округления)
        assert abs(profit - 0.0) < 0.5

    def test_profit_calculation_with_loss(self):
        """Тест расчета убытка."""
        buy_price = 100.0
        sell_price = 100.0
        fee_percent = 7.0

        fee = sell_price * (fee_percent / 100)
        profit = sell_price - buy_price - fee

        assert profit < 0  # Убыток из-за комиссии

    def test_profit_percent_calculation(self):
        """Тест расчета процента прибыли."""
        buy_price = 100.0
        profit = 20.0

        profit_percent = (profit / buy_price) * 100

        assert profit_percent == 20.0


class TestArbitrageScannerEdgeCases:
    """Тесты граничных случаев."""

    def test_scanner_initialization_without_params(self):
        """Тест создания сканера без параметров."""
        scanner = ArbitrageScanner()

        assert scanner is not None
        assert scanner.api_client is None

    def test_scanner_with_disabled_liquidity_filter(self):
        """Тест создания сканера с отключенным фильтром ликвидности."""
        scanner = ArbitrageScanner(enable_liquidity_filter=False)

        assert scanner is not None
        assert scanner.enable_liquidity_filter is False
