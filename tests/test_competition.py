"""Тесты для механизма оценки конкуренции buy orders.

Этот модуль тестирует функциональность оценки конкуренции
для предотвращения создания buy orders на высококонкурентные предметы.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.dmarket_api import DMarketAPI

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_dmarket_api():
    """Создать мок DMarket API клиента для тестов конкуренции."""
    api = MagicMock(spec=DMarketAPI)
    api.public_key = "test_public_key"
    api._secret_key = "test_secret_key"

    # Мок для get_targets_by_title
    api.get_targets_by_title = AsyncMock()

    return api


@pytest.fixture()
def sample_orders_response_low():
    """Пример ответа API с низкой конкуренцией (мало ордеров)."""
    return {
        "orders": [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": "850",  # $8.50 в центах
                "amount": 2,
                "attributes": {"exterior": "Field-Tested"},
            },
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": "820",  # $8.20 в центах
                "amount": 1,
                "attributes": {},
            },
        ]
    }


@pytest.fixture()
def sample_orders_response_high():
    """Пример ответа API с высокой конкуренцией (много ордеров)."""
    return {
        "orders": [
            {"title": "Popular Item", "price": str(i * 100), "amount": i + 1}
            for i in range(1, 16)  # 15 ордеров
        ]
    }


@pytest.fixture()
def sample_orders_response_empty():
    """Пример ответа API без ордеров."""
    return {"orders": []}


# ============================================================================
# Tests: get_buy_orders_competition
# ============================================================================


class TestGetBuyOrdersCompetition:
    """Тесты метода get_buy_orders_competition."""

    @pytest.mark.asyncio()
    async def test_low_competition_detection(
        self, mock_dmarket_api, sample_orders_response_low
    ):
        """Тест определения низкой конкуренции."""
        # Arrange
        mock_dmarket_api.get_targets_by_title.return_value = sample_orders_response_low

        # Создаем реальный экземпляр для тестирования метода
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="AK-47 | Redline (Field-Tested)",
        )

        # Assert
        assert result["competition_level"] == "low"
        assert result["total_orders"] == 2
        assert result["total_amount"] == 3  # 2 + 1
        assert result["best_price"] == 8.50  # Максимальная цена
        assert result["average_price"] == 8.35  # (8.50 + 8.20) / 2

    @pytest.mark.asyncio()
    async def test_high_competition_detection(
        self, mock_dmarket_api, sample_orders_response_high
    ):
        """Тест определения высокой конкуренции."""
        # Arrange
        mock_dmarket_api.get_targets_by_title.return_value = sample_orders_response_high

        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="Popular Item",
        )

        # Assert
        assert result["competition_level"] == "high"
        assert result["total_orders"] == 15

    @pytest.mark.asyncio()
    async def test_no_competition(self, mock_dmarket_api, sample_orders_response_empty):
        """Тест при отсутствии конкуренции."""
        # Arrange
        mock_dmarket_api.get_targets_by_title.return_value = (
            sample_orders_response_empty
        )

        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="Rare Item",
        )

        # Assert
        assert result["competition_level"] == "low"
        assert result["total_orders"] == 0
        assert result["total_amount"] == 0
        assert result["best_price"] == 0.0

    @pytest.mark.asyncio()
    async def test_price_threshold_filtering(self, mock_dmarket_api):
        """Тест фильтрации по порогу цены."""
        # Arrange
        mock_dmarket_api.get_targets_by_title.return_value = {
            "orders": [
                {"title": "Item", "price": "1000", "amount": 5},  # $10.00
                {"title": "Item", "price": "800", "amount": 3},  # $8.00
                {"title": "Item", "price": "600", "amount": 2},  # $6.00
            ]
        }

        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="Item",
            price_threshold=7.50,  # Фильтруем ордера < $7.50
        )

        # Assert
        # Должны учитываться только ордера >= $7.50 ($10 и $8)
        assert result["filtered_orders"] == 2
        assert result["filtered_amount"] == 8  # 5 + 3

    @pytest.mark.asyncio()
    async def test_api_error_handling(self, mock_dmarket_api):
        """Тест обработки ошибки API."""
        # Arrange
        mock_dmarket_api.get_targets_by_title.side_effect = Exception("API Error")

        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="Test Item",
        )

        # Assert
        assert result["competition_level"] == "unknown"
        assert result["total_orders"] == 0
        assert "error" in result


class TestCompetitionLevelClassification:
    """Тесты классификации уровня конкуренции."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("orders_count", "total_amount", "expected_level"),
        (
            (0, 0, "low"),
            (1, 2, "low"),
            (2, 5, "low"),
            (3, 6, "medium"),
            (5, 15, "medium"),
            (10, 20, "medium"),
            (11, 21, "high"),
            (15, 50, "high"),
        ),
    )
    async def test_competition_level_boundaries(
        self, mock_dmarket_api, orders_count, total_amount, expected_level
    ):
        """Тест границ классификации уровня конкуренции."""
        # Arrange
        orders = []
        remaining_amount = total_amount
        for i in range(orders_count):
            # Распределяем amount между ордерами
            if i == orders_count - 1:
                amount = remaining_amount
            else:
                amount = max(1, remaining_amount // (orders_count - i))
                remaining_amount -= amount
            orders.append({"price": str((i + 1) * 100), "amount": amount})

        mock_dmarket_api.get_targets_by_title.return_value = {"orders": orders}

        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )
        api.get_targets_by_title = mock_dmarket_api.get_targets_by_title

        # Act
        result = await api.get_buy_orders_competition(
            game_id="a8db",
            title="Test Item",
        )

        # Assert
        assert result["competition_level"] == expected_level
        assert result["total_orders"] == orders_count
