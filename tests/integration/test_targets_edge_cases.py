"""Integration тесты для Targets с edge cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_httpx import HTTPXMock

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


pytestmark = pytest.mark.asyncio


class TestTargetsEdgeCases:
    """Edge cases для создания и управления таргетами."""

    async def test_create_target_minimum_price(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с минимальной ценой."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            json={
                "Result": [
                    {
                        "TargetID": "target_1",
                        "Title": "Cheap Item",
                        "Status": "Created",
                    }
                ]
            },
            status_code=200,
        )

        targets = [
            {
                "Title": "Cheap Item",
                "Amount": 1,
                "Price": {"Amount": 1, "Currency": "USD"},  # $0.01
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None
        assert "Result" in result

    async def test_create_target_maximum_amount(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с максимальным количеством."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            json={
                "Result": [
                    {
                        "TargetID": "target_1",
                        "Title": "Bulk Item",
                        "Status": "Created",
                    }
                ]
            },
            status_code=200,
        )

        targets = [
            {
                "Title": "Bulk Item",
                "Amount": 100,  # Максимум
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_with_special_attributes(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с специальными атрибутами."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            json={
                "Result": [
                    {
                        "TargetID": "target_1",
                        "Title": "Knife with Specific Float",
                        "Status": "Created",
                    }
                ]
            },
            status_code=200,
        )

        targets = [
            {
                "Title": "Karambit | Doppler (Factory New)",
                "Amount": 1,
                "Price": {"Amount": 50000, "Currency": "USD"},
                "Attrs": {
                    "floatPartValue": 0.001,  # Очень низкий float
                    "phase": "Phase 2",
                    "paintSeed": 123,
                },
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_multiple_targets_batch(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания нескольких таргетов одним запросом."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            json={
                "Result": [
                    {
                        "TargetID": f"target_{i}",
                        "Title": f"Item {i}",
                        "Status": "Created",
                    }
                    for i in range(10)
                ]
            },
            status_code=200,
        )

        targets = [
            {
                "Title": f"Item {i}",
                "Amount": 1,
                "Price": {"Amount": 1000 + i * 100, "Currency": "USD"},
            }
            for i in range(10)
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None
        assert len(result.get("Result", [])) == 10

    async def test_create_target_duplicate_error(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания дублирующегося таргета."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=409,
            json={
                "error": "TargetAlreadyExists",
                "message": "Target with same parameters already exists",
            },
        )

        targets = [
            {
                "Title": "Duplicate Item",
                "Amount": 1,
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        # API должен обработать ошибку
        assert result is not None

    async def test_create_target_exceeds_limit(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест превышения лимита таргетов."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "TargetLimitExceeded",
                "message": "Maximum targets limit reached for this game",
            },
        )

        targets = [
            {
                "Title": "Item",
                "Amount": 1,
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_delete_nonexistent_target(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест удаления несуществующего таргета."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/delete",
            method="POST",
            status_code=404,
            json={
                "error": "TargetNotFound",
                "message": "Target with specified ID not found",
            },
        )

        result = await mock_dmarket_api.delete_targets(
            target_ids=["nonexistent_target"]
        )

        # API должен обработать ошибку
        assert result is not None

    async def test_get_targets_with_filters(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест получения таргетов с фильтрами."""
        import re

        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/user-targets\?.*"
            ),
            method="GET",
            json={
                "Items": [
                    {
                        "TargetID": "target_1",
                        "Title": "Filtered Item",
                        "Amount": 1,
                        "Price": {"Amount": 1500, "Currency": "USD"},
                        "Status": "TargetStatusActive",
                    }
                ],
                "Total": "1",
                "Cursor": "",
            },
            status_code=200,
        )

        # Запрос с фильтрами (game_id вместо game)
        result = await mock_dmarket_api.get_user_targets(
            game_id="a8db", status="TargetStatusActive"
        )

        assert result is not None
        assert "Items" in result

    async def test_get_targets_pagination(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест пагинации при получении таргетов."""
        import re

        # Первая страница
        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/user-targets\?.*"
            ),
            method="GET",
            json={
                "Items": [
                    {
                        "TargetID": f"target_{i}",
                        "Title": f"Item {i}",
                        "Amount": 1,
                        "Price": {"Amount": 1000, "Currency": "USD"},
                        "Status": "TargetStatusActive",
                    }
                    for i in range(50)
                ],
                "Total": "100",
                "Cursor": "cursor_1",
            },
            status_code=200,
        )

        # Вторая страница
        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/user-targets\?.*"
            ),
            method="GET",
            json={
                "Items": [
                    {
                        "TargetID": f"target_{i}",
                        "Title": f"Item {i}",
                        "Amount": 1,
                        "Price": {"Amount": 1000, "Currency": "USD"},
                        "Status": "TargetStatusActive",
                    }
                    for i in range(50, 100)
                ],
                "Total": "100",
                "Cursor": "",
            },
            status_code=200,
        )

        result1 = await mock_dmarket_api.get_user_targets(game_id="a8db")
        assert len(result1.get("Items", [])) == 50

        result2 = await mock_dmarket_api.get_user_targets(game_id="a8db", offset=50)
        assert len(result2.get("Items", [])) == 50

    async def test_target_with_unicode_title(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с Unicode символами в названии."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            json={
                "Result": [
                    {
                        "TargetID": "target_1",
                        "Title": "AK-47 | 红线 🔥",
                        "Status": "Created",
                    }
                ]
            },
            status_code=200,
        )

        targets = [
            {
                "Title": "AK-47 | 红线 🔥",  # Китайские символы + эмодзи
                "Amount": 1,
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_get_closed_targets_history(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест получения истории закрытых таргетов."""
        import re

        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/user-targets/closed\?.*"
            ),
            method="GET",
            json={
                "Trades": [
                    {
                        "TargetID": "target_1",
                        "Title": "Executed Target",
                        "Price": {"Amount": 1200, "Currency": "USD"},
                        "Status": "successful",
                        "ClosedAt": 1700000000,
                        "CreatedAt": 1699900000,
                    }
                ],
                "Total": "10",
                "Cursor": "",
            },
            status_code=200,
        )

        # get_closed_targets doesn't take game parameter
        result = await mock_dmarket_api.get_closed_targets(
            status="successful", limit=50
        )

        assert result is not None
        assert "Trades" in result


class TestTargetsValidation:
    """Тесты валидации таргетов."""

    async def test_create_target_zero_price(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с нулевой ценой (должно быть отклонено)."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Price must be greater than 0",
            },
        )

        targets = [
            {
                "Title": "Zero Price Item",
                "Amount": 1,
                "Price": {"Amount": 0, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_negative_price(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с отрицательной ценой."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Price cannot be negative",
            },
        )

        targets = [
            {
                "Title": "Negative Price Item",
                "Amount": 1,
                "Price": {"Amount": -100, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_zero_amount(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с нулевым количеством."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Amount must be at least 1",
            },
        )

        targets = [
            {
                "Title": "Zero Amount Item",
                "Amount": 0,
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_exceeds_amount_limit(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с количеством выше лимита."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Amount cannot exceed 100",
            },
        )

        targets = [
            {
                "Title": "Too Many Items",
                "Amount": 101,  # Выше лимита
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_empty_title(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с пустым названием."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Title cannot be empty",
            },
        )

        targets = [
            {
                "Title": "",  # Пустое название
                "Amount": 1,
                "Price": {"Amount": 1000, "Currency": "USD"},
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None

    async def test_create_target_invalid_currency(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест создания таргета с некорректной валютой."""
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/user-targets/create",
            method="POST",
            status_code=400,
            json={
                "error": "ValidationError",
                "message": "Currency must be USD or DMC",
            },
        )

        targets = [
            {
                "Title": "Invalid Currency Item",
                "Amount": 1,
                "Price": {"Amount": 1000, "Currency": "EUR"},  # Некорректная валюта
            }
        ]

        result = await mock_dmarket_api.create_targets(game_id="a8db", targets=targets)

        assert result is not None
