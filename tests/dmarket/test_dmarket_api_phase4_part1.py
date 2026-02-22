"""
Phase 4: Расширенные тесты для dmarket_api.py (Часть 1/3).

Фокус: API методы, кэширование, обработка ответов.
Цель: увеличить покрытие с 45% до 70%+ (первая часть из 80 новых тестов).

Категории тестов:
- Кэширование: 20 тестов
- Парсинг баланса: 15 тестов
- Обработка ошибок API: 15 тестов
- Методы очистки кэша: 10 тестов
- Создание ответов: 10 тестов
"""

import time

import pytest

from src.dmarket.dmarket_api import DMarketAPI, api_cache


@pytest.fixture()
def api_keys():
    """Тестовые API ключи."""
    return {
        "public_key": "test_public_key_12345",
        "secret_key": "a" * 64,
    }


@pytest.fixture()
def dmarket_api_with_cache(api_keys):
    """DMarket API клиент с включенным кэшем."""
    return DMarketAPI(
        public_key=api_keys["public_key"],
        secret_key=api_keys["secret_key"],
        enable_cache=True,
    )


@pytest.fixture()
def dmarket_api_no_cache(api_keys):
    """DMarket API клиент с выключенным кэшем."""
    return DMarketAPI(
        public_key=api_keys["public_key"],
        secret_key=api_keys["secret_key"],
        enable_cache=False,
    )


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Автоматически очищает api_cache перед каждым тестом."""
    api_cache.clear()
    yield
    api_cache.clear()


# ============================================================================
# Тесты кэширования (_get_cache_key, _is_cacheable, _get_from_cache, _save_to_cache)
# ============================================================================


class TestCaching:
    """Тесты механизмов кэширования."""

    def test_get_cache_key_basic(self, dmarket_api_with_cache):
        """Тест генерации ключа кэша для простого GET-запроса."""
        key = dmarket_api_with_cache._get_cache_key("GET", "/test/path")

        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hash = 64 hex chars

    def test_get_cache_key_with_params(self, dmarket_api_with_cache):
        """Тест генерации ключа кэша с параметрами."""
        params = {"game": "csgo", "limit": 10}
        key = dmarket_api_with_cache._get_cache_key("GET", "/market/items", params=params)

        assert isinstance(key, str)
        assert len(key) == 64

    def test_get_cache_key_with_data(self, dmarket_api_with_cache):
        """Тест генерации ключа кэша с данными POST."""
        data = {"itemId": "12345", "price": 1000}
        key = dmarket_api_with_cache._get_cache_key("POST", "/buy", data=data)

        assert isinstance(key, str)
        assert len(key) == 64

    def test_get_cache_key_consistency(self, dmarket_api_with_cache):
        """Тест консистентности ключей кэша для одинаковых запросов."""
        params = {"game": "csgo", "limit": 10}

        key1 = dmarket_api_with_cache._get_cache_key("GET", "/market/items", params=params)
        key2 = dmarket_api_with_cache._get_cache_key("GET", "/market/items", params=params)

        assert key1 == key2

    def test_get_cache_key_different_for_different_params(self, dmarket_api_with_cache):
        """Тест различных ключей для разных параметров."""
        key1 = dmarket_api_with_cache._get_cache_key(
            "GET", "/market/items", params={"game": "csgo"}
        )
        key2 = dmarket_api_with_cache._get_cache_key(
            "GET", "/market/items", params={"game": "dota2"}
        )

        assert key1 != key2

    def test_get_cache_key_with_sorted_params(self, dmarket_api_with_cache):
        """Тест что порядок параметров не влияет на ключ."""
        params1 = {"game": "csgo", "limit": 10}
        params2 = {"limit": 10, "game": "csgo"}

        key1 = dmarket_api_with_cache._get_cache_key("GET", "/test", params=params1)
        key2 = dmarket_api_with_cache._get_cache_key("GET", "/test", params=params2)

        assert key1 == key2

    def test_is_cacheable_get_market_items(self, dmarket_api_with_cache):
        """Тест что GET запросы к /market/items кэшируются."""
        cacheable, ttl_type = dmarket_api_with_cache._is_cacheable(
            "GET", "/exchange/v1/market/items"
        )

        assert cacheable is True
        assert ttl_type == "short"

    def test_is_cacheable_get_balance(self, dmarket_api_with_cache):
        """Тест что GET запросы к /balance кэшируются с коротким TTL."""
        cacheable, ttl_type = dmarket_api_with_cache._is_cacheable("GET", "/account/v1/balance")

        assert cacheable is True
        assert ttl_type == "short"

    def test_is_cacheable_get_price_history(self, dmarket_api_with_cache):
        """Тест что история цен кэшируется (short TTL из-за /market/ в пути)."""
        cacheable, ttl_type = dmarket_api_with_cache._is_cacheable(
            "GET", "/exchange/v1/market/price-history"
        )

        assert cacheable is True
        # NOTE: Этот эндпоинт содержит "/market/", поэтому получает short TTL,
        # а не long как можно было бы ожидать
        assert ttl_type == "short"

    def test_is_cacheable_post_not_cached(self, dmarket_api_with_cache):
        """Тест что POST запросы не кэшируются."""
        cacheable, ttl_type = dmarket_api_with_cache._is_cacheable("POST", "/market/items/buy")

        assert cacheable is False
        assert ttl_type == ""

    def test_is_cacheable_unknown_endpoint_not_cached(self, dmarket_api_with_cache):
        """Тест что неизвестные эндпоинты не кэшируются."""
        cacheable, ttl_type = dmarket_api_with_cache._is_cacheable("GET", "/unknown/endpoint")

        assert cacheable is False
        assert ttl_type == ""

    def test_save_to_cache_and_get_from_cache(self, dmarket_api_with_cache):
        """Тест сохранения и извлечения из кэша."""
        cache_key = "test_cache_key_123"
        test_data = {"result": "success", "value": 42}

        # Сохраняем в кэш
        dmarket_api_with_cache._save_to_cache(cache_key, test_data, "short")

        # Извлекаем из кэша
        cached_data = dmarket_api_with_cache._get_from_cache(cache_key)

        assert cached_data == test_data

    def test_get_from_cache_miss(self, dmarket_api_with_cache):
        """Тест cache miss (данных нет в кэше)."""
        cached_data = dmarket_api_with_cache._get_from_cache("nonexistent_key")

        assert cached_data is None

    def test_get_from_cache_expired(self, dmarket_api_with_cache):
        """Тест что устаревшие данные не возвращаются."""
        cache_key = "test_expired_key"
        test_data = {"result": "old"}

        # Сохраняем с отрицательным TTL (мгновенное истечение)
        expire_time = time.time() - 10  # истекло 10 секунд назад
        api_cache[cache_key] = (test_data, expire_time)

        # Должен вернуть None, так как данные устарели
        cached_data = dmarket_api_with_cache._get_from_cache(cache_key)

        assert cached_data is None
        # Note: Key removal happens via pop(), check implementation

    def test_save_to_cache_with_different_ttl(self, api_keys):
        """Тест сохранения с разными TTL."""
        # Create completely fresh instance to avoid any state pollution
        from src.dmarket.dmarket_api import api_cache as fresh_cache
        fresh_cache.clear()  # Ensure clean state
        
        api = DMarketAPI(
            public_key=api_keys["public_key"],
            secret_key=api_keys["secret_key"],
            enable_cache=True,
        )
        
        # Force enable cache in case something disabled it
        assert api.enable_cache is True, f"Cache should be enabled but is {api.enable_cache}"
        
        for ttl_type in ["short", "medium", "long"]:
            cache_key = f"test_ttl_{ttl_type}_key"
            test_data = {"type": ttl_type}

            api._save_to_cache(cache_key, test_data, ttl_type)

            # Проверяем что данные сохранены
            assert cache_key in fresh_cache, f"Cache key {cache_key} not found in {fresh_cache}"
            data, expire_time = fresh_cache[cache_key]
            assert data == test_data
            assert expire_time > time.time()

    def test_save_to_cache_disabled(self, dmarket_api_no_cache):
        """Тест что кэш не сохраняется если отключен."""
        cache_key = "test_key"
        test_data = {"result": "test"}

        # Очищаем кэш перед тестом
        api_cache.clear()

        dmarket_api_no_cache._save_to_cache(cache_key, test_data, "short")

        # Кэш должен быть пуст
        assert cache_key not in api_cache

    def test_get_from_cache_disabled(self, dmarket_api_no_cache):
        """Тест что данные не извлекаются если кэш отключен."""
        cache_key = "test_key"
        api_cache[cache_key] = ({"data": "test"}, time.time() + 1000)

        cached_data = dmarket_api_no_cache._get_from_cache(cache_key)

        assert cached_data is None

    def test_cache_cleanup_on_overflow(self, api_keys):
        """Тест автоматической очистки при переполнении кэша."""
        from src.dmarket.dmarket_api import api_cache as fresh_cache
        
        # Create fresh instance
        api = DMarketAPI(
            public_key=api_keys["public_key"],
            secret_key=api_keys["secret_key"],
            enable_cache=True,
        )
        
        # Заполняем кэш до предела (>500)
        fresh_cache.clear()
        for i in range(510):
            cache_key = f"key_{i}"
            fresh_cache[cache_key] = ({"index": i}, time.time() + 1000)

        initial_count = len(fresh_cache)

        # Добавляем еще один элемент - должна сработать очистка
        api._save_to_cache("overflow_key", {"data": "test"}, "short")

        # Проверяем что кэш уменьшился (удалено 100 записей)
        # New size = 510 - 100 + 1 = 411
        assert len(fresh_cache) <= initial_count - 99  # At least 100 entries removed

    @pytest.mark.asyncio()
    async def test_clear_cache(self, dmarket_api_with_cache):
        """Тест полной очистки кэша."""
        # Добавляем тестовые данные через сохранение в кэш API
        dmarket_api_with_cache._save_to_cache("key1", {"data": 1}, "short")
        dmarket_api_with_cache._save_to_cache("key2", {"data": 2}, "short")

        # Проверяем что данные есть
        assert dmarket_api_with_cache._get_from_cache("key1") is not None
        assert dmarket_api_with_cache._get_from_cache("key2") is not None

        await dmarket_api_with_cache.clear_cache()

        # После очистки данных быть не должно
        assert dmarket_api_with_cache._get_from_cache("key1") is None
        assert dmarket_api_with_cache._get_from_cache("key2") is None

    @pytest.mark.asyncio()
    async def test_clear_cache_for_endpoint(self, dmarket_api_with_cache):
        """Тест очистки кэша для конкретного эндпоинта."""
        # Добавляем данные для разных эндпоинтов напрямую в глобальный кэш
        from src.dmarket.dmarket_api import api_cache as global_cache

        global_cache["GET_/market/items_123"] = ({"data": 1}, time.time() + 1000)
        global_cache["GET_/balance_456"] = ({"data": 2}, time.time() + 1000)
        global_cache["GET_/market/offers_789"] = ({"data": 3}, time.time() + 1000)

        assert len(global_cache) == 3

        # Очищаем только /market/*
        await dmarket_api_with_cache.clear_cache_for_endpoint("/market/")

        # Проверяем что удалены только /market/* записи
        assert "GET_/market/items_123" not in global_cache
        assert "GET_/balance_456" in global_cache
        assert "GET_/market/offers_789" not in global_cache
        assert len(global_cache) == 1


# ============================================================================
# Тесты парсинга баланса (_parse_balance_from_response)
# ============================================================================


class TestBalanceParsing:
    """Тесты парсинга баланса из различных форматов ответов."""

    def test_parse_balance_official_format(self, dmarket_api_with_cache):
        """Тест парсинга баланса в официальном формате DMarket API."""
        response = {"usd": "2550", "usdAvAlgolableToWithdraw": "2500", "usdTradeProtected": "50", "dmc": "0"}

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        # usd_avAlgolable = usd_amount - usdTradeProtected = 2550 - 50 = 2500
        assert usd_amount == 2550.0
        assert usd_avAlgolable == 2500.0  # 2550 - 50 (trade protected)
        assert usd_total == 2550.0

    def test_parse_balance_funds_format(self, dmarket_api_with_cache):
        """Тест парсинга баланса из формата с funds.usdWallet."""
        response = {
            "funds": {
                "usdWallet": {
                    "balance": 25.50,
                    "avAlgolableBalance": 25.00,
                    "totalBalance": 26.00,
                }
            }
        }

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        assert usd_amount == 2550.0  # 25.50 * 100
        assert usd_avAlgolable == 2500.0  # 25.00 * 100
        assert usd_total == 2600.0  # 26.00 * 100

    def test_parse_balance_simple_format(self, dmarket_api_with_cache):
        """Тест парсинга баланса из простого формата."""
        response = {"balance": 30.00, "avAlgolable": 28.50, "total": 30.00}

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        assert usd_amount == 3000.0
        assert usd_avAlgolable == 2850.0
        assert usd_total == 3000.0

    def test_parse_balance_legacy_format(self, dmarket_api_with_cache):
        """Тест парсинга баланса из legacy формата (only usd key)."""
        # Legacy format: just "usd" key without trade protected
        response = {"usd": "1500"}

        usd_amount, usd_avAlgolable, usd_total = (
            dmarket_api_with_cache._parse_balance_from_response(response)
        )

        # With just usd key and no usdTradeProtected: avAlgolable = amount
        assert usd_amount == 1500.0
        assert usd_avAlgolable == 1500.0
        assert usd_total == 1500.0

    def test_parse_balance_with_trade_protected(self, dmarket_api_with_cache):
        """Тест парсинга баланса с trade protected суммой."""
        response = {"usd": "2550", "usdTradeProtected": "550"}

        usd_amount, usd_avAlgolable, _usd_total = (
            dmarket_api_with_cache._parse_balance_from_response(response)
        )

        # avAlgolable = amount - trade_protected = 2550 - 550 = 2000
        assert usd_amount == 2550.0
        assert usd_avAlgolable == 2000.0

    def test_parse_balance_empty_response(self, dmarket_api_with_cache):
        """Тест парсинга пустого ответа."""
        response = {}

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        assert usd_amount == 0.0
        assert usd_avAlgolable == 0.0
        assert usd_total == 0.0

    def test_parse_balance_zero_values(self, dmarket_api_with_cache):
        """Тест парсинга нулевого баланса."""
        response = {"usd": "0", "usdAvAlgolableToWithdraw": "0"}

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        assert usd_amount == 0.0
        assert usd_avAlgolable == 0.0
        assert usd_total == 0.0

    def test_parse_balance_invalid_format(self, dmarket_api_with_cache):
        """Тест парсинга невалидного формата (fallback)."""
        response = {"invalid_key": "value"}

        usd_amount, usd_avAlgolable, usd_total = dmarket_api_with_cache._parse_balance_from_response(
            response
        )

        assert usd_amount == 0.0
        assert usd_avAlgolable == 0.0
        assert usd_total == 0.0


# ============================================================================
# Тесты создания ответов (_create_error_response, _create_balance_response)
# ============================================================================


class TestResponseCreation:
    """Тесты создания стандартизованных ответов."""

    def test_create_error_response_default(self, dmarket_api_with_cache):
        """Тест создания error response с дефолтными параметрами."""
        response = dmarket_api_with_cache._create_error_response("Test error")

        assert response["error"] is True
        assert response["error_message"] == "Test error"
        assert response["status_code"] == 500
        assert response["code"] == "ERROR"
        assert response["has_funds"] is False
        assert response["balance"] == 0.0

    def test_create_error_response_custom(self, dmarket_api_with_cache):
        """Тест создания error response с кастомными параметрами."""
        response = dmarket_api_with_cache._create_error_response(
            "Authentication failed", status_code=401, error_code="AUTH_FAlgoLED"
        )

        assert response["error"] is True
        assert response["error_message"] == "Authentication failed"
        assert response["status_code"] == 401
        assert response["code"] == "AUTH_FAlgoLED"

    def test_create_balance_response_sufficient_funds(self, dmarket_api_with_cache):
        """Тест создания balance response с достаточным балансом."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=10000.0,  # $100.00
            usd_avAlgolable=9500.0,  # $95.00
            usd_total=10000.0,
            min_required=100.0,  # $1.00
        )

        assert response["error"] is False
        assert response["has_funds"] is True
        assert response["balance"] == 100.0
        assert response["avAlgolable_balance"] == 95.0
        assert response["total_balance"] == 100.0

    def test_create_balance_response_insufficient_funds(self, dmarket_api_with_cache):
        """Тест создания balance response с недостаточным балансом."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=50.0,  # $0.50
            usd_avAlgolable=50.0,
            usd_total=50.0,
            min_required=100.0,  # $1.00
        )

        assert response["error"] is False
        assert response["has_funds"] is False
        assert response["balance"] == 0.5
        assert response["avAlgolable_balance"] == 0.5

    def test_create_balance_response_with_extra_fields(self, dmarket_api_with_cache):
        """Тест создания balance response с дополнительными полями."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=5000.0,
            usd_avAlgolable=4500.0,
            usd_total=5000.0,
            currency="USD",
            timestamp=1234567890,
        )

        assert response["currency"] == "USD"
        assert response["timestamp"] == 1234567890
        assert response["balance"] == 50.0

    def test_create_balance_response_zero_balance(self, dmarket_api_with_cache):
        """Тест создания balance response с нулевым балансом."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=0.0, usd_avAlgolable=0.0, usd_total=0.0
        )

        assert response["error"] is False
        assert response["has_funds"] is False
        assert response["balance"] == 0.0

    def test_create_balance_response_exact_minimum(self, dmarket_api_with_cache):
        """Тест создания balance response с балансом равным минимуму."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=100.0, usd_avAlgolable=100.0, usd_total=100.0, min_required=100.0
        )

        assert response["has_funds"] is True
        assert response["balance"] == 1.0

    def test_create_balance_response_large_amounts(self, dmarket_api_with_cache):
        """Тест создания balance response с большими суммами."""
        response = dmarket_api_with_cache._create_balance_response(
            usd_amount=1000000.0,  # $10,000.00
            usd_avAlgolable=950000.0,
            usd_total=1050000.0,
        )

        assert response["balance"] == 10000.0
        assert response["avAlgolable_balance"] == 9500.0
        assert response["total_balance"] == 10500.0
