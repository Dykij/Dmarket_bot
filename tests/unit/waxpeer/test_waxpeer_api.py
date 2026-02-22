"""
Тесты для Waxpeer API клиента.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.waxpeer.waxpeer_api import (
    ListingStatus,
    WaxpeerAPI,
    WaxpeerAuthError,
    WaxpeerBalance,
    WaxpeerGame,
    WaxpeerItem,
    WaxpeerRateLimitError,
)


class TestWaxpeerAPI:
    """Тесты для WaxpeerAPI."""

    @pytest.fixture()
    def api_key(self) -> str:
        """API ключ для тестов."""
        return "test_api_key_12345"

    @pytest.fixture()
    def mock_response_success(self) -> dict:
        """Успешный ответ API."""
        return {
            "success": True,
            "user": {
                "wallet": 45500,  # $45.50 в милах
                "can_trade": True,
                "tradelink": "https://steamcommunity.com/tradeoffer/new/?partner=123",
            },
        }

    @pytest.fixture()
    def mock_items_response(self) -> dict:
        """Ответ со списком предметов."""
        return {
            "success": True,
            "items": [
                {
                    "item_id": "item_001",
                    "name": "AK-47 | Redline (Field-Tested)",
                    "price": 5500,  # $5.50
                    "float": 0.25,
                },
                {
                    "item_id": "item_002",
                    "name": "AWP | Asiimov (Battle-Scarred)",
                    "price": 15000,  # $15.00
                    "float": 0.96,
                },
            ],
        }

    @pytest.mark.asyncio()
    async def test_get_balance_parses_correctly(
        self, api_key: str, mock_response_success: dict
    ) -> None:
        """Тест корректного парсинга баланса."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_success
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                balance = await api.get_balance()

            assert isinstance(balance, WaxpeerBalance)
            assert balance.wallet == Decimal("45.5")
            assert balance.wallet_mils == 45500

    @pytest.mark.asyncio()
    async def test_get_my_items_returns_list(self, api_key: str, mock_items_response: dict) -> None:
        """Тест получения списка своих предметов."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_items_response
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                items = await api.get_my_items()

            assert len(items) == 2
            assert isinstance(items[0], WaxpeerItem)
            assert items[0].name == "AK-47 | Redline (Field-Tested)"
            assert items[0].price == Decimal("5.5")
            assert items[1].float_value == 0.96

    @pytest.mark.asyncio()
    async def test_list_single_item_converts_price_to_mils(self, api_key: str) -> None:
        """Тест конвертации цены в милы при листинге."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                result = await api.list_single_item(
                    item_id="asset_123",
                    price_usd=10.50,
                    game=WaxpeerGame.CS2,
                )

            # Проверяем что запрос был сделан с правильной ценой в милах
            call_args = mock_client.request.call_args
            json_data = call_args.kwargs.get("json", {})
            assert json_data["items"][0]["price"] == 10500  # $10.50 = 10500 mils

    @pytest.mark.asyncio()
    async def test_auth_error_on_401(self, api_key: str) -> None:
        """Тест обработки ошибки авторизации."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                with pytest.raises(WaxpeerAuthError):
                    await api.get_user()

    @pytest.mark.asyncio()
    async def test_rate_limit_error_on_429(self, api_key: str) -> None:
        """Тест обработки превышения лимита запросов."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                with pytest.raises(WaxpeerRateLimitError):
                    await api.get_user()

    @pytest.mark.asyncio()
    async def test_get_item_price_returns_decimal(self, api_key: str) -> None:
        """Тест получения цены предмета."""
        market_response = {
            "success": True,
            "items": [{"price": 8500, "name": "Test Item"}],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = market_response
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                price = await api.get_item_price("Test Item")

            assert price == Decimal("8.5")

    @pytest.mark.asyncio()
    async def test_get_item_price_returns_none_for_no_offers(self, api_key: str) -> None:
        """Тест возврата None когда нет предложений."""
        market_response = {"success": True, "items": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = market_response
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with WaxpeerAPI(api_key) as api:
                price = await api.get_item_price("Nonexistent Item")

            assert price is None


class TestWaxpeerDataClasses:
    """Тесты для dataclasses Waxpeer."""

    def test_waxpeer_item_creation(self) -> None:
        """Тест создания WaxpeerItem."""
        item = WaxpeerItem(
            item_id="123",
            name="AK-47 | Redline",
            price=Decimal("5.50"),
            price_mils=5500,
            game=WaxpeerGame.CS2,
            float_value=0.25,
        )

        assert item.item_id == "123"
        assert item.price == Decimal("5.50")
        assert item.game == WaxpeerGame.CS2
        assert item.status == ListingStatus.PENDING

    def test_waxpeer_balance_creation(self) -> None:
        """Тест создания WaxpeerBalance."""
        balance = WaxpeerBalance(
            wallet=Decimal("45.50"),
            wallet_mils=45500,
            avAlgolable_for_withdrawal=Decimal("45.50"),
        )

        assert balance.wallet == Decimal("45.50")
        assert balance.pending == Decimal(0)

    def test_waxpeer_game_enum(self) -> None:
        """Тест enum WaxpeerGame."""
        assert WaxpeerGame.CS2.value == "cs2"
        assert WaxpeerGame.CSGO.value == "csgo"
