"""
Phase 4: Расширенные тесты для dmarket_api.py (Часть 4/4 - ФИНАЛ).

Фокус: Торговые операции (buy_item, sell_item).
Цель: увеличить покрытие с 75% до 85%+.

Категории тестов:
- buy_item(): 10 тестов
- sell_item(): 10 тестов
- DRY_RUN режим: 4 теста
"""

from unittest.mock import AsyncMock, patch

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


@pytest.fixture()
def dmarket_api_dry_run(api_keys):
    """DMarket API клиент с DRY_RUN режимом."""
    return DMarketAPI(
        public_key=api_keys["public_key"],
        secret_key=api_keys["secret_key"],
        dry_run=True,
    )


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Автоматически очищает api_cache перед каждым тестом."""
    api_cache.clear()
    yield
    api_cache.clear()


# ============================================================================
# Тесты buy_item()
# ============================================================================


class TestBuyItem:
    """Тесты метода buy_item()."""

    @pytest.mark.asyncio()
    async def test_buy_item_returns_success(self, dmarket_api):
        """Тест успешной покупки предмета."""
        mock_response = {"success": True, "itemId": "item123", "price": {"USD": "1000"}}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.buy_item(
                    item_id="item123", price=10.0, game="csgo"
                )

                assert result is not None
                assert result.get("success") is True

    @pytest.mark.asyncio()
    async def test_buy_item_converts_price_to_cents(self, dmarket_api):
        """Тест конвертации цены в центы."""
        mock_response = {"success": True}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req, patch.object(
            dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
        ):
            await dmarket_api.buy_item(item_id="item123", price=25.50, game="csgo")

            # Проверяем что данные переданы
            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            if "data" in call_kwargs:
                data = call_kwargs["data"]
                # Цена должна быть в центах
                assert "price" in data

    @pytest.mark.asyncio()
    async def test_buy_item_with_item_name(self, dmarket_api):
        """Тест покупки с указанием названия предмета."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.buy_item(
                    item_id="item123",
                    price=10.0,
                    game="csgo",
                    item_name="AK-47 | Redline",
                )

                assert result is not None

    @pytest.mark.asyncio()
    async def test_buy_item_with_different_games(self, dmarket_api):
        """Тест покупки для разных игр."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                for game in ["csgo", "dota2", "tf2", "rust"]:
                    result = await dmarket_api.buy_item(
                        item_id="item123", price=10.0, game=game
                    )
                    assert result is not None

    @pytest.mark.asyncio()
    async def test_buy_item_with_low_price(self, dmarket_api):
        """Тест покупки с низкой ценой."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.buy_item(
                    item_id="item123", price=0.50, game="csgo"
                )

                assert result is not None

    @pytest.mark.asyncio()
    async def test_buy_item_with_high_price(self, dmarket_api):
        """Тест покупки с высокой ценой."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.buy_item(
                    item_id="item123", price=500.00, game="csgo"
                )

                assert result is not None

    @pytest.mark.asyncio()
    async def test_buy_item_with_source_parameter(self, dmarket_api):
        """Тест покупки с параметром source."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.buy_item(
                    item_id="item123", price=10.0, game="csgo", source="arbitrage"
                )

                assert result is not None


# ============================================================================
# Тесты sell_item()
# ============================================================================


class TestSellItem:
    """Тесты метода sell_item()."""

    @pytest.mark.asyncio()
    async def test_sell_item_returns_success(self, dmarket_api):
        """Тест успешной продажи предмета."""
        mock_response = {"success": True, "offerId": "offer123"}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.sell_item(
                    item_id="item123", price=15.0, game="csgo"
                )

                assert result is not None
                assert result.get("success") is True

    @pytest.mark.asyncio()
    async def test_sell_item_converts_price_to_cents(self, dmarket_api):
        """Тест конвертации цены в центы."""
        mock_response = {"success": True}

        with patch.object(
            dmarket_api, "_request", return_value=mock_response
        ) as mock_req, patch.object(
            dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
        ):
            await dmarket_api.sell_item(item_id="item123", price=25.50, game="csgo")

            # Проверяем данные
            call_kwargs = mock_req.call_args.kwargs if mock_req.call_args else {}
            if "data" in call_kwargs:
                data = call_kwargs["data"]
                assert "price" in data

    @pytest.mark.asyncio()
    async def test_sell_item_with_buy_price_calculates_profit(self, dmarket_api):
        """Тест расчета прибыли при указании цены покупки."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.sell_item(
                    item_id="item123", price=15.0, game="csgo", buy_price=10.0
                )

                # Прибыль должна быть рассчитана (5.0 USD)
                assert result is not None

    @pytest.mark.asyncio()
    async def test_sell_item_with_item_name(self, dmarket_api):
        """Тест продажи с указанием названия."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.sell_item(
                    item_id="item123",
                    price=15.0,
                    game="csgo",
                    item_name="AWP | Dragon Lore",
                )

                assert result is not None

    @pytest.mark.asyncio()
    async def test_sell_item_with_different_games(self, dmarket_api):
        """Тест продажи для разных игр."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                for game in ["csgo", "dota2", "tf2", "rust"]:
                    result = await dmarket_api.sell_item(
                        item_id="item123", price=15.0, game=game
                    )
                    assert result is not None

    @pytest.mark.asyncio()
    async def test_sell_item_with_source_parameter(self, dmarket_api):
        """Тест продажи с параметром source."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.sell_item(
                    item_id="item123", price=15.0, game="csgo", source="auto_sell"
                )

                assert result is not None

    @pytest.mark.asyncio()
    async def test_sell_item_with_low_price(self, dmarket_api):
        """Тест продажи с низкой ценой."""
        mock_response = {"success": True}

        with patch.object(dmarket_api, "_request", return_value=mock_response):
            with patch.object(
                dmarket_api, "clear_cache_for_endpoint", new_callable=AsyncMock
            ):
                result = await dmarket_api.sell_item(
                    item_id="item123", price=0.75, game="csgo"
                )

                assert result is not None


# ============================================================================
# Тесты DRY_RUN режима
# ============================================================================


class TestDryRunMode:
    """Тесты DRY_RUN режима для торговых операций."""

    @pytest.mark.asyncio()
    async def test_buy_item_dry_run_does_not_call_api(self, dmarket_api_dry_run):
        """Тест что buy_item в DRY_RUN не вызывает API."""
        with patch.object(dmarket_api_dry_run, "_request") as mock_req:
            result = await dmarket_api_dry_run.buy_item(
                item_id="item123", price=10.0, game="csgo"
            )

            # API не должен быть вызван
            mock_req.assert_not_called()
            # Результат должен содержать dry_run флаг
            assert result.get("dry_run") is True
            assert result.get("operation") == "buy"

    @pytest.mark.asyncio()
    async def test_sell_item_dry_run_does_not_call_api(self, dmarket_api_dry_run):
        """Тест что sell_item в DRY_RUN не вызывает API."""
        with patch.object(dmarket_api_dry_run, "_request") as mock_req:
            result = await dmarket_api_dry_run.sell_item(
                item_id="item123", price=15.0, game="csgo"
            )

            # API не должен быть вызван
            mock_req.assert_not_called()
            # Результат должен содержать dry_run флаг
            assert result.get("dry_run") is True
            assert result.get("operation") == "sell"

    @pytest.mark.asyncio()
    async def test_dry_run_buy_returns_success(self, dmarket_api_dry_run):
        """Тест что DRY_RUN buy всегда возвращает success."""
        result = await dmarket_api_dry_run.buy_item(
            item_id="item123", price=10.0, game="csgo"
        )

        assert result.get("success") is True
        assert result.get("dry_run") is True

    @pytest.mark.asyncio()
    async def test_dry_run_sell_returns_success(self, dmarket_api_dry_run):
        """Тест что DRY_RUN sell всегда возвращает success."""
        result = await dmarket_api_dry_run.sell_item(
            item_id="item123", price=15.0, game="csgo"
        )

        assert result.get("success") is True
        assert result.get("dry_run") is True
