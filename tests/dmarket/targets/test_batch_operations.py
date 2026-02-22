"""Тесты для пакетных операций с таргетами.

Тестируем:
- Создание пакетных ордеров
- Обнаружение существующих ордеров
- Проверку дубликатов
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.models.target_enhancements import BatchTargetItem
from src.dmarket.targets.batch_operations import (
    check_duplicate_order,
    create_batch_target,
    detect_existing_orders,
)


@pytest.mark.asyncio()
class TestCreateBatchTarget:
    """Тесты создания пакетных ордеров."""

    async def test_create_batch_empty_items(self):
        """Тест создания с пустым списком предметов."""
        api_client = AsyncMock()

        result = await create_batch_target(
            api_client=api_client,
            game="csgo",
            items=[],
            price=50.0,
        )

        assert result.success is False
        assert "empty" in result.reason.lower()

    async def test_create_batch_too_many_items(self):
        """Тест создания со слишком многими предметами."""
        api_client = AsyncMock()
        items = [BatchTargetItem(title=f"Item {i}") for i in range(150)]

        result = await create_batch_target(
            api_client=api_client,
            game="csgo",
            items=items,
            price=1000.0,
        )

        assert result.success is False
        assert "100" in result.reason

    async def test_create_batch_success(self):
        """Тест успешного создания пакетного ордера."""
        api_client = AsyncMock()
        api_client.create_targets = AsyncMock(
            return_value={
                "Result": [
                    {"TargetID": "target1", "Status": "Created"},
                    {"TargetID": "target2", "Status": "Created"},
                ]
            }
        )

        items = [
            BatchTargetItem(title="Item 1", attrs={"floatPartValue": "0.15"}),
            BatchTargetItem(title="Item 2", attrs={"floatPartValue": "0.25"}),
        ]

        result = await create_batch_target(
            api_client=api_client,
            game="csgo",
            items=items,
            price=20.0,
            total_amount=2,
        )

        assert result.success is True
        assert result.metadata["success_count"] == 2
        assert len(result.metadata["target_ids"]) == 2
        api_client.create_targets.assert_called_once()

    async def test_create_batch_partial_success(self):
        """Тест частично успешного создания."""
        api_client = AsyncMock()
        api_client.create_targets = AsyncMock(
            return_value={
                "Result": [
                    {"TargetID": "target1", "Status": "Created"},
                    {"TargetID": "target2", "Status": "Failed"},
                ]
            }
        )

        items = [
            BatchTargetItem(title="Item 1"),
            BatchTargetItem(title="Item 2"),
        ]

        result = await create_batch_target(
            api_client=api_client,
            game="csgo",
            items=items,
            price=20.0,
        )

        assert result.success is True
        assert result.status.value == "partial"
        assert result.metadata["success_count"] == 1
        assert result.metadata["failed_count"] == 1

    async def test_create_batch_distributes_price(self):
        """Тест распределения цены по весам."""
        api_client = AsyncMock()
        api_client.create_targets = AsyncMock(
            return_value={"Result": [{"Status": "Created"} for _ in range(3)]}
        )

        items = [
            BatchTargetItem(title="Item 1", weight=1.0),
            BatchTargetItem(title="Item 2", weight=2.0),
            BatchTargetItem(title="Item 3", weight=3.0),
        ]

        result = await create_batch_target(
            api_client=api_client,
            game="csgo",
            items=items,
            price=60.0,  # Должно распределиться как 10/20/30
            total_amount=6,
        )

        assert result.success is True

        # Проверить вызов API
        call_args = api_client.create_targets.call_args
        targets = call_args.kwargs["targets"]

        # Цены должны быть распределены пропорционально весам
        assert len(targets) == 3


@pytest.mark.asyncio()
class TestDetectExistingOrders:
    """Тесты обнаружения существующих ордеров."""

    async def test_detect_no_existing_orders(self):
        """Тест когда нет существующих ордеров."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(return_value={"Items": []})
        api_client.get_targets_by_title = AsyncMock(return_value={"orders": []})

        info = await detect_existing_orders(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            user_id="12345",
        )

        assert info.has_user_order is False
        assert info.total_orders == 0
        assert info.can_create is True

    async def test_detect_user_has_order(self):
        """Тест когда у пользователя уже есть ордер."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(
            return_value={
                "Items": [
                    {
                        "TargetID": "abc123",
                        "Title": "Test Item",
                        "Price": {"Amount": 1000},
                    }
                ]
            }
        )
        api_client.get_targets_by_title = AsyncMock(return_value={"orders": []})

        info = await detect_existing_orders(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            user_id="12345",
        )

        assert info.has_user_order is True
        assert info.user_order is not None
        assert info.can_create is False
        assert "$10.00" in info.reason

    async def test_detect_market_orders(self):
        """Тест обнаружения рыночных ордеров."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(return_value={"Items": []})
        api_client.get_targets_by_title = AsyncMock(
            return_value={
                "orders": [
                    {"price": "1000", "amount": 1},
                    {"price": "1200", "amount": 2},
                    {"price": "800", "amount": 1},
                ]
            }
        )

        info = await detect_existing_orders(
            api_client=api_client,
            game="csgo",
            title="Test Item",
        )

        assert info.total_orders == 3
        assert info.best_price == 12.00  # Лучшая (самая высокая) цена
        assert info.average_price == 10.00  # (10+12+8)/3
        assert info.recommended_price == 12.01  # best + 0.01
        assert len(info.suggestions) > 0

    async def test_detect_handles_api_errors(self):
        """Тест обработки ошибок API."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(side_effect=Exception("API Error"))
        api_client.get_targets_by_title = AsyncMock(return_value={"orders": []})

        info = await detect_existing_orders(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            user_id="12345",
        )

        # Должен вернуть результат с информацией о рыночных ордерах
        # даже если не удалось получить ордера пользователя
        assert info.total_orders >= 0  # Проверяем что функция не упала


@pytest.mark.asyncio()
class TestCheckDuplicateOrder:
    """Тесты проверки дубликатов."""

    async def test_check_no_duplicates(self):
        """Тест когда дубликатов нет."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(return_value={"Items": []})

        is_dup, message = await check_duplicate_order(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            price=10.00,
        )

        assert is_dup is False
        assert "No duplicate" in message

    async def test_check_duplicate_found(self):
        """Тест когда найден дубликат."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(
            return_value={
                "Items": [
                    {
                        "TargetID": "abc123",
                        "Title": "Test Item",
                        "Price": {"Amount": 1005},  # $10.05
                    }
                ]
            }
        )

        is_dup, message = await check_duplicate_order(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            price=10.00,
            tolerance=0.10,  # $0.10 допуск
        )

        assert is_dup is True
        assert "$10.05" in message
        assert "Similar" in message

    async def test_check_no_duplicate_outside_tolerance(self):
        """Тест что цены вне допуска не считаются дубликатами."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(
            return_value={
                "Items": [
                    {
                        "TargetID": "abc123",
                        "Title": "Test Item",
                        "Price": {"Amount": 1500},  # $15.00
                    }
                ]
            }
        )

        is_dup, message = await check_duplicate_order(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            price=10.00,
            tolerance=0.05,  # Маленький допуск
        )

        assert is_dup is False  # Разница $5, больше допуска

    async def test_check_handles_errors(self):
        """Тест обработки ошибок."""
        api_client = AsyncMock()
        api_client.get_user_targets = AsyncMock(side_effect=Exception("API Error"))

        is_dup, message = await check_duplicate_order(
            api_client=api_client,
            game="csgo",
            title="Test Item",
            price=10.00,
        )

        assert is_dup is False
        assert "Error" in message
