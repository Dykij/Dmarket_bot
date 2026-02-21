"""
Тесты для Steam API интеграции.

Проверяет:
- Получение цен через Steam Market API
- Rate Limit защиту
- Расчет арбитража
- Нормализацию названий
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.steam_api import (
    ItemNotFoundError,
    RateLimitError,
    SteamAPIError,
    calculate_arbitrage,
    calculate_net_profit,
    get_liquidity_status,
    get_steam_price,
    normalize_item_name,
    reset_backoff,
)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Сбрасывает rate limit перед каждым тестом."""
    reset_backoff()
    yield
    reset_backoff()


class TestCalculations:
    """Тесты расчетов прибыли."""

    def test_calculate_arbitrage_positive(self):
        """Тест расчета положительной прибыли."""
        # Arrange
        dmarket_price = 2.0
        steam_price = 2.5

        # Act
        profit = calculate_arbitrage(dmarket_price, steam_price)

        # Assert
        # Steam net = 2.5 * 0.8696 = 2.174
        # Profit = (2.174 - 2.0) / 2.0 * 100 = 8.7%
        assert profit == 8.7

    def test_calculate_arbitrage_negative(self):
        """Тест расчета отрицательной прибыли."""
        # Arrange
        dmarket_price = 3.0
        steam_price = 2.5

        # Act
        profit = calculate_arbitrage(dmarket_price, steam_price)

        # Assert
        assert profit < 0

    def test_calculate_arbitrage_zero_price(self):
        """Тест с нулевой ценой."""
        # Act
        profit = calculate_arbitrage(0, 10.0)

        # Assert
        assert profit == 0.0

    def test_calculate_net_profit(self):
        """Тест расчета чистой прибыли."""
        # Arrange
        dmarket_price = 2.0
        steam_price = 3.0
        dmarket_fee = 0.05  # 5%

        # Act
        net = calculate_net_profit(dmarket_price, steam_price, dmarket_fee)

        # Assert
        # Steam net = 3.0 * 0.8696 = 2.6088
        # Cost = 2.0 * 1.05 = 2.1
        # Profit = 2.6088 - 2.1 = 0.51
        assert net == 0.51


class TestItemNameNormalization:
    """Тесты нормализации названий."""

    def test_normalize_field_tested(self):
        """Тест нормализации 'Field Tested'."""
        # Arrange
        name = "AK-47 | Slate (Field Tested)"

        # Act
        result = normalize_item_name(name)

        # Assert
        assert result == "AK-47 | Slate (Field-Tested)"

    def test_normalize_well_worn(self):
        """Тест нормализации 'Well Worn'."""
        # Arrange
        name = "AWP | Asiimov (Well Worn)"

        # Act
        result = normalize_item_name(name)

        # Assert
        assert result == "AWP | Asiimov (Well-Worn)"

    def test_normalize_battle_scarred(self):
        """Тест нормализации 'Battle Scarred'."""
        # Arrange
        name = "M4A4 | Howl (Battle Scarred)"

        # Act
        result = normalize_item_name(name)

        # Assert
        assert result == "M4A4 | Howl (Battle-Scarred)"


class TestLiquidityStatus:
    """Тесты определения ликвидности."""

    def test_high_liquidity(self):
        """Тест высокой ликвидности."""
        status = get_liquidity_status(250)
        assert "🔥" in status
        assert "Высокая" in status

    def test_medium_liquidity(self):
        """Тест средней ликвидности."""
        status = get_liquidity_status(150)
        assert "✅" in status
        assert "Средняя" in status

    def test_low_liquidity(self):
        """Тест низкой ликвидности."""
        status = get_liquidity_status(75)
        assert "⚠️" in status
        assert "Низкая" in status

    def test_very_low_liquidity(self):
        """Тест очень низкой ликвидности."""
        status = get_liquidity_status(10)
        assert "❌" in status
        assert "Очень низкая" in status


@pytest.mark.asyncio()
class TestSteamAPIIntegration:
    """Тесты интеграции с Steam API."""

    async def test_get_steam_price_success(self):
        """Тест успешного получения цены."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "lowest_price": "$2.15",
            "volume": "145",
            "median_price": "$2.20",
        }

        # Act
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = awAlgot get_steam_price("AK-47 | Slate (Field-Tested)")

        # Assert
        assert result is not None
        assert result["price"] == 2.15
        assert result["volume"] == 145
        assert result["median_price"] == 2.20

    async def test_get_steam_price_not_found(self):
        """Тест предмета не найденного на рынке."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False}

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.rAlgoses(ItemNotFoundError):
                awAlgot get_steam_price("Non-Existent Item")

    async def test_get_steam_price_rate_limit(self):
        """Тест обработки Rate Limit."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 429

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.rAlgoses(RateLimitError):
                awAlgot get_steam_price("Test Item")

    async def test_get_steam_price_server_error(self):
        """Тест обработки ошибки сервера."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 500

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.rAlgoses(SteamAPIError):
                awAlgot get_steam_price("Test Item")

    async def test_rate_limit_protection_delay(self):
        """Тест паузы между запросами."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "lowest_price": "$1.00",
            "volume": "100",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Act - делаем два запроса подряд
            start_time = asyncio.get_event_loop().time()
            awAlgot get_steam_price("Item 1")
            awAlgot get_steam_price("Item 2")
            end_time = asyncio.get_event_loop().time()

            # Assert - между запросами должна быть пауза минимум 2 секунды
            elapsed = end_time - start_time
            assert elapsed >= 2.0, f"Expected delay >=2s, got {elapsed:.2f}s"


if __name__ == "__mAlgon__":
    pytest.mAlgon([__file__, "-v"])
