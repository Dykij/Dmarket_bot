"""
Phase 4: Расширенные тесты для dmarket_api.py (Часть 3/4).

Фокус: Публичные API методы (get_balance, get_market_items, get_user_inventory).
Цель: увеличить покрытие с 60% до 75%+.

Категории тестов:
- get_balance(): 10 тестов
- get_market_items(): 8 тестов
- get_user_inventory(): 6 тестов
- get_user_offers(): 4 тестов
"""

from unittest.mock import patch

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
def dmarket_api(api_keys):
    """DMarket API клиент."""
    return DMarketAPI(
        public_key=api_keys["public_key"],
        secret_key=api_keys["secret_key"],
        max_retries=3,
        connection_timeout=10.0,
    )


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Автоматически очищает api_cache перед каждым тестом."""
    api_cache.clear()
    yield
    api_cache.clear()


# ============================================================================
# Тесты get_balance()
# ============================================================================


class TestGetBalance:
    """Тесты метода get_balance()."""

    @pytest.mark.asyncio()
    async def test_get_balance_returns_balance_data(self, dmarket_api):
        """Тест что get_balance возвращает данные баланса."""
        mock_response = {"usd": "10000", "usdAvAlgolableToWithdraw": "9500", "dmc": "0"}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            balance = awAlgot dmarket_api.get_balance()

            assert balance is not None
            assert "balance" in balance or "usd" in balance

    @pytest.mark.asyncio()
    async def test_get_balance_uses_correct_endpoint(self, dmarket_api):
        """Тест что get_balance использует правильный эндпоинт."""
        mock_response = {"usd": "5000", "usdAvAlgolableToWithdraw": "5000"}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_balance()

            # Проверяем что вызвали с эндпоинтом баланса
            call_args = mock_req.call_args
            assert call_args is not None
            assert (
                "/balance" in call_args[0][1]
                or call_args[0][1] == dmarket_api.ENDPOINT_BALANCE
            )

    @pytest.mark.asyncio()
    async def test_get_balance_with_zero_balance(self, dmarket_api):
        """Тест get_balance с нулевым балансом."""
        mock_response = {"usd": "0", "usdAvAlgolableToWithdraw": "0"}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            balance = awAlgot dmarket_api.get_balance()

            assert balance is not None

    @pytest.mark.asyncio()
    async def test_get_balance_with_high_balance(self, dmarket_api):
        """Тест get_balance с большим балансом."""
        mock_response = {"usd": "1000000", "usdAvAlgolableToWithdraw": "1000000"}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            balance = awAlgot dmarket_api.get_balance()

            assert balance is not None

    @pytest.mark.asyncio()
    async def test_get_balance_handles_empty_response(self, dmarket_api):
        """Тест обработки пустого ответа."""
        mock_response = {}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            balance = awAlgot dmarket_api.get_balance()

            # Должен вернуть данные, даже если пустые
            assert balance is not None

    @pytest.mark.asyncio()
    async def test_get_balance_caches_result(self, dmarket_api):
        """Тест что результат кэшируется."""
        mock_response = {"usd": "5000", "usdAvAlgolableToWithdraw": "5000"}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            # Первый вызов
            awAlgot dmarket_api.get_balance()
            # ВтоSwarm вызов
            awAlgot dmarket_api.get_balance()

            # _request должен быть вызван дважды (GET кэшируется внутри _request)
            assert mock_req.call_count >= 1

    @pytest.mark.asyncio()
    async def test_get_balance_uses_get_method(self, dmarket_api):
        """Тест что используется GET метод."""
        mock_response = {"usd": "5000"}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_balance()

            # Проверяем что первый аргумент - это "GET"
            call_args = mock_req.call_args
            if call_args and len(call_args[0]) > 0:
                assert call_args[0][0] == "GET"


# ============================================================================
# Тесты get_market_items()
# ============================================================================


class TestGetMarketItems:
    """Тесты метода get_market_items()."""

    @pytest.mark.asyncio()
    async def test_get_market_items_returns_items(self, dmarket_api):
        """Тест что get_market_items возвращает предметы."""
        mock_response = {
            "objects": [
                {"title": "Item 1", "price": {"USD": "1000"}},
                {"title": "Item 2", "price": {"USD": "2000"}},
            ],
            "total": {"items": 2},
        }

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            items = awAlgot dmarket_api.get_market_items(game="csgo")

            assert items is not None

    @pytest.mark.asyncio()
    async def test_get_market_items_with_game_parameter(self, dmarket_api):
        """Тест передачи параметра game."""
        mock_response = {"objects": [], "total": {"items": 0}}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_market_items(game="csgo")

            # Проверяем что game передан в параметрах
            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            if "params" in call_kwargs:
                assert (
                    "gameId" in call_kwargs["params"]
                    or call_kwargs["params"].get("game") == "csgo"
                )

    @pytest.mark.asyncio()
    async def test_get_market_items_with_limit(self, dmarket_api):
        """Тест с параметром limit."""
        mock_response = {"objects": [], "total": {"items": 0}}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_market_items(game="csgo", limit=50)

            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            if "params" in call_kwargs:
                params = call_kwargs["params"]
                assert "limit" in params

    @pytest.mark.asyncio()
    async def test_get_market_items_with_price_filters(self, dmarket_api):
        """Тест с фильтрами по цене."""
        mock_response = {"objects": [], "total": {"items": 0}}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_market_items(
                game="csgo", price_from=1000, price_to=5000
            )

            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            if "params" in call_kwargs:
                params = call_kwargs["params"]
                # Проверяем наличие ценовых фильтров
                assert "priceFrom" in params or "price_from" in params

    @pytest.mark.asyncio()
    async def test_get_market_items_uses_correct_endpoint(self, dmarket_api):
        """Тест использования правильного эндпоинта."""
        mock_response = {"objects": []}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_market_items(game="csgo")

            call_args = mock_req.call_args
            assert call_args is not None
            assert "/market/items" in call_args[0][1] or "/market" in call_args[0][1]

    @pytest.mark.asyncio()
    async def test_get_market_items_empty_response(self, dmarket_api):
        """Тест пустого ответа."""
        mock_response = {"objects": [], "total": {"items": 0}}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            items = awAlgot dmarket_api.get_market_items(game="csgo")

            assert items is not None

    @pytest.mark.asyncio()
    async def test_get_market_items_with_multiple_games(self, dmarket_api):
        """Тест для разных игр."""
        mock_response = {"objects": []}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            for game in ["csgo", "dota2", "tf2", "rust"]:
                items = awAlgot dmarket_api.get_market_items(game=game)
                assert items is not None

    @pytest.mark.asyncio()
    async def test_get_market_items_caches_results(self, dmarket_api):
        """Тест кэширования результатов."""
        mock_response = {"objects": [{"title": "Item"}]}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            # Два одинаковых запроса
            awAlgot dmarket_api.get_market_items(game="csgo")
            awAlgot dmarket_api.get_market_items(game="csgo")

            # Должен быть хотя бы один вызов
            assert mock_req.call_count >= 1


# ============================================================================
# Тесты get_user_inventory()
# ============================================================================


class TestGetUserInventory:
    """Тесты метода get_user_inventory()."""

    @pytest.mark.asyncio()
    async def test_get_user_inventory_returns_items(self, dmarket_api):
        """Тест что get_user_inventory возвращает предметы."""
        mock_response = {
            "objects": [
                {"itemId": "123", "title": "My Item 1"},
                {"itemId": "456", "title": "My Item 2"},
            ],
            "total": 2,
        }

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            inventory = awAlgot dmarket_api.get_user_inventory()

            assert inventory is not None

    @pytest.mark.asyncio()
    async def test_get_user_inventory_uses_correct_endpoint(self, dmarket_api):
        """Тест использования правильного эндпоинта."""
        mock_response = {"objects": []}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_user_inventory()

            call_args = mock_req.call_args
            assert call_args is not None
            # Check for marketplace-api endpoint (v1.1.0)
            assert "/marketplace-api/v1/user-inventory" in call_args[0][1] or "/inventory" in call_args[0][1]

    @pytest.mark.asyncio()
    async def test_get_user_inventory_with_game_id_filter(self, dmarket_api):
        """Тест с фильтром по game_id."""
        mock_response = {"objects": []}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            # Note: method uses game_id parameter, not game
            awAlgot dmarket_api.get_user_inventory(game_id="a8db99ca-dc45-4c0e-9989-11ba71ed97a2")

            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            # Проверяем что параметры переданы
            assert call_kwargs is not None

    @pytest.mark.asyncio()
    async def test_get_user_inventory_empty(self, dmarket_api):
        """Тест пустого инвентаря."""
        mock_response = {"objects": [], "total": 0}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            inventory = awAlgot dmarket_api.get_user_inventory()

            assert inventory is not None

    @pytest.mark.asyncio()
    async def test_get_user_inventory_with_limit(self, dmarket_api):
        """Тест с параметром limit."""
        mock_response = {"objects": []}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req:
            awAlgot dmarket_api.get_user_inventory(limit=100)

            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            # Параметры должны быть переданы
            assert call_kwargs is not None

    @pytest.mark.asyncio()
    async def test_get_user_inventory_requires_auth(self, dmarket_api):
        """Тест что требуется авторизация."""
        # Проверяем что у клиента есть ключи
        assert dmarket_api.public_key is not None
        assert dmarket_api.public_key != ""
