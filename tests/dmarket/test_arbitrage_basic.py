"""Тесты для модуля arbitrage.

Проверяет функции арбитража на DMarket.
"""

import time

from src.dmarket.arbitrage import (
    CACHE_TTL,
    DEFAULT_FEE,
    DEFAULT_LIMIT,
    GAMES,
    HIGH_FEE,
    LOW_FEE,
    MAX_RETRIES,
    MIN_PROFIT_PERCENT,
    PRICE_RANGES,
    _arbitrage_cache,
    _get_cached_results,
    _save_to_cache,
    clear_cache,
)


class TestConstants:
    """Тесты констант арбитража."""

    def test_games_defined(self):
        """Тест что GAMES определены."""
        assert "csgo" in GAMES
        assert "dota2" in GAMES
        assert "tf2" in GAMES
        assert "rust" in GAMES

    def test_games_values(self):
        """Тест значений GAMES."""
        assert GAMES["csgo"] == "CS2"
        assert GAMES["dota2"] == "Dota 2"
        assert GAMES["tf2"] == "Team Fortress 2"
        assert GAMES["rust"] == "Rust"

    def test_default_fee(self):
        """Тест стандартной комиссии."""
        assert DEFAULT_FEE == 0.07

    def test_low_fee(self):
        """Тест низкой комиссии."""
        assert LOW_FEE == 0.02

    def test_high_fee(self):
        """Тест высокой комиссии."""
        assert HIGH_FEE == 0.10

    def test_default_limit(self):
        """Тест лимита по умолчанию."""
        assert DEFAULT_LIMIT == 100

    def test_max_retries(self):
        """Тест максимального числа повторов."""
        assert MAX_RETRIES == 3

    def test_cache_ttl(self):
        """Тест времени жизни кэша."""
        assert CACHE_TTL == 300

    def test_min_profit_percent_modes(self):
        """Тест режимов минимальной прибыли."""
        assert "low" in MIN_PROFIT_PERCENT
        assert "medium" in MIN_PROFIT_PERCENT
        assert "high" in MIN_PROFIT_PERCENT
        assert "boost" in MIN_PROFIT_PERCENT
        assert "pro" in MIN_PROFIT_PERCENT

    def test_min_profit_percent_values(self):
        """Тест значений минимальной прибыли."""
        assert MIN_PROFIT_PERCENT["low"] == 3.0
        assert MIN_PROFIT_PERCENT["medium"] == 5.0
        assert MIN_PROFIT_PERCENT["high"] == 10.0
        assert MIN_PROFIT_PERCENT["boost"] == 1.5
        assert MIN_PROFIT_PERCENT["pro"] == 15.0

    def test_price_ranges_modes(self):
        """Тест режимов ценовых диапазонов."""
        assert "low" in PRICE_RANGES
        assert "medium" in PRICE_RANGES
        assert "high" in PRICE_RANGES
        assert "boost" in PRICE_RANGES
        assert "pro" in PRICE_RANGES

    def test_price_ranges_values(self):
        """Тест значений ценовых диапазонов."""
        assert PRICE_RANGES["boost"] == (0.5, 1.0)  # Обновлено: разгон на самых дешевых
        assert PRICE_RANGES["low"] == (1.0, 5.0)
        assert PRICE_RANGES["medium"] == (5.0, 20.0)
        assert PRICE_RANGES["high"] == (20.0, 100.0)
        assert PRICE_RANGES["pro"] == (100.0, 1000.0)

    def test_price_ranges_ascending(self):
        """Тест что ценовые диапазоны возрастают."""
        _boost_min, boost_max = PRICE_RANGES["boost"]
        low_min, low_max = PRICE_RANGES["low"]
        medium_min, medium_max = PRICE_RANGES["medium"]
        high_min, high_max = PRICE_RANGES["high"]
        pro_min, _pro_max = PRICE_RANGES["pro"]

        assert boost_max <= low_min
        assert low_max <= medium_min
        assert medium_max <= high_min
        assert high_max <= pro_min


class TestArbitrageCache:
    """Тесты кэширования арбитража."""

    def setup_method(self):
        """Очистить кэш перед каждым тестом."""
        clear_cache()

    def test_cache_initially_empty(self):
        """Тест что кэш изначально пуст."""
        assert len(_arbitrage_cache) == 0

    def test_get_cached_results_empty_cache(self):
        """Тест получения из пустого кэша."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        result = _get_cached_results(cache_key)
        assert result is None

    def test_save_to_cache(self):
        """Тест сохранения в кэш."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test Item", "price": 2.5}]

        _save_to_cache(cache_key, items)

        assert cache_key in _arbitrage_cache
        cached_items, timestamp = _arbitrage_cache[cache_key]
        assert cached_items == items
        assert isinstance(timestamp, float)

    def test_get_cached_results_valid_cache(self):
        """Тест получения из валидного кэша."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test Item", "price": 2.5}]

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == items

    def test_get_cached_results_expired_cache(self):
        """Тест получения из устаревшего кэша."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test Item", "price": 2.5}]

        # Сохраняем с timestamp в прошлом
        _arbitrage_cache[cache_key] = (items, time.time() - CACHE_TTL - 1)

        result = _get_cached_results(cache_key)
        assert result is None

    def test_cache_key_uniqueness(self):
        """Тест уникальности ключей кэша."""
        key1 = ("csgo", "low", 1.0, 5.0)
        key2 = ("csgo", "medium", 5.0, 20.0)
        key3 = ("dota2", "low", 1.0, 5.0)

        items1 = [{"title": "Item 1"}]
        items2 = [{"title": "Item 2"}]
        items3 = [{"title": "Item 3"}]

        _save_to_cache(key1, items1)
        _save_to_cache(key2, items2)
        _save_to_cache(key3, items3)

        assert _get_cached_results(key1) == items1
        assert _get_cached_results(key2) == items2
        assert _get_cached_results(key3) == items3

    def test_cache_overwrite(self):
        """Тест перезаписи кэша."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items1 = [{"title": "Item 1"}]
        items2 = [{"title": "Item 2"}]

        _save_to_cache(cache_key, items1)
        _save_to_cache(cache_key, items2)

        result = _get_cached_results(cache_key)
        assert result == items2

    def test_cache_with_empty_items(self):
        """Тест кэширования пустого списка."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = []

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == []

    def test_cache_timestamp_updated(self):
        """Тест что timestamp обновляется при повторном сохранении."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test"}]

        _save_to_cache(cache_key, items)
        _, timestamp1 = _arbitrage_cache[cache_key]

        time.sleep(0.1)

        _save_to_cache(cache_key, items)
        _, timestamp2 = _arbitrage_cache[cache_key]

        assert timestamp2 > timestamp1


class TestProfitCalculations:
    """Тесты расчета прибыли."""

    def test_min_profit_ascending(self):
        """Тест что минимальная прибыль возрастает."""
        assert MIN_PROFIT_PERCENT["boost"] < MIN_PROFIT_PERCENT["low"]
        assert MIN_PROFIT_PERCENT["low"] < MIN_PROFIT_PERCENT["medium"]
        assert MIN_PROFIT_PERCENT["medium"] < MIN_PROFIT_PERCENT["high"]
        assert MIN_PROFIT_PERCENT["high"] < MIN_PROFIT_PERCENT["pro"]

    def test_fee_values_logical(self):
        """Тест что значения комиссий логичны."""
        assert LOW_FEE < DEFAULT_FEE < HIGH_FEE
        assert LOW_FEE > 0
        assert HIGH_FEE < 1.0  # Меньше 100%


class TestGameConfiguration:
    """Тесты конфигурации игр."""

    def test_all_games_have_names(self):
        """Тест что у всех игр есть названия."""
        for game_key, game_name in GAMES.items():
            assert isinstance(game_key, str)
            assert isinstance(game_name, str)
            assert len(game_key) > 0
            assert len(game_name) > 0

    def test_game_keys_lowercase(self):
        """Тест что ключи игр в нижнем регистре."""
        for game_key in GAMES:
            assert game_key == game_key.lower()


class TestModeConfiguration:
    """Тесты конфигурации режимов."""

    def test_all_modes_have_profit(self):
        """Тест что у всех режимов есть минимальная прибыль."""
        modes = ["low", "medium", "high", "boost", "pro"]
        for mode in modes:
            assert mode in MIN_PROFIT_PERCENT
            assert MIN_PROFIT_PERCENT[mode] > 0

    def test_all_modes_have_price_range(self):
        """Тест что у всех режимов есть ценовой диапазон."""
        modes = ["low", "medium", "high", "boost", "pro"]
        for mode in modes:
            assert mode in PRICE_RANGES
            min_price, max_price = PRICE_RANGES[mode]
            assert min_price < max_price
            assert min_price > 0

    def test_mode_consistency(self):
        """Тест согласованности режимов."""
        # Одинаковые ключи в обоих словарях
        assert set(MIN_PROFIT_PERCENT.keys()) == set(PRICE_RANGES.keys())


class TestCachePerformance:
    """Тесты производительности кэша."""

    def setup_method(self):
        """Очистить кэш перед тестом."""
        _arbitrage_cache.clear()

    def test_cache_access_speed(self):
        """Тест скорости доступа к кэшу."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": f"Item {i}"} for i in range(100)]

        _save_to_cache(cache_key, items)

        # Измеряем время доступа
        start = time.time()
        for _ in range(1000):
            _get_cached_results(cache_key)
        elapsed = time.time() - start

        # Должно быть быстро (< 0.1 секунды для 1000 операций)
        assert elapsed < 0.1

    def test_cache_memory_efficiency(self):
        """Тест эффективности памяти кэша."""
        # Сохраняем много записей
        for i in range(100):
            cache_key = ("csgo", "low", float(i), float(i + 1))
            items = [{"title": f"Item {i}"}]
            _save_to_cache(cache_key, items)

        # Кэш должен содержать записи (may be less due to cleanup)
        assert len(_arbitrage_cache) >= 20  # At least some records should exist


class TestCacheTTL:
    """Тесты времени жизни кэша."""

    def setup_method(self):
        """Очистить кэш."""
        _arbitrage_cache.clear()

    def test_cache_ttl_value(self):
        """Тест что TTL установлен правильно."""
        assert CACHE_TTL == 300  # 5 минут

    def test_cache_expires_after_ttl(self):
        """Тест что кэш истекает после TTL."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test"}]

        # Устанавливаем timestamp в прошлом
        expired_time = time.time() - CACHE_TTL - 10
        _arbitrage_cache[cache_key] = (items, expired_time)

        result = _get_cached_results(cache_key)
        assert result is None

    def test_cache_valid_before_ttl(self):
        """Тест что кэш валиден до истечения TTL."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Test"}]

        # Устанавливаем timestamp недавно
        recent_time = time.time() - 10  # 10 секунд назад
        _arbitrage_cache[cache_key] = (items, recent_time)

        result = _get_cached_results(cache_key)
        assert result == items


class TestEdgeCases:
    """Тесты граничных случаев."""

    def setup_method(self):
        """Очистить кэш."""
        _arbitrage_cache.clear()

    def test_cache_key_with_zero_prices(self):
        """Тест ключа кэша с нулевыми ценами."""
        cache_key = ("csgo", "low", 0.0, 0.0)
        items = [{"title": "Test"}]

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == items

    def test_cache_key_with_large_prices(self):
        """Тест ключа с большими ценами."""
        cache_key = ("csgo", "pro", 1000.0, 10000.0)
        items = [{"title": "Expensive"}]

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == items

    def test_cache_with_special_characters(self):
        """Тест кэша со спецсимволами в данных."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Item with special: ™ ® © € £"}]

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == items

    def test_cache_with_unicode(self):
        """Тест кэша с Unicode."""
        cache_key = ("csgo", "low", 1.0, 5.0)
        items = [{"title": "Предмет с русским названием 中文"}]

        _save_to_cache(cache_key, items)
        result = _get_cached_results(cache_key)

        assert result == items
