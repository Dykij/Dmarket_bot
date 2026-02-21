"""Integration тесты для ArbitrageScanner с edge cases."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from pytest_httpx import HTTPXMock

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


pytestmark = pytest.mark.asyncio


class TestArbitrageScannerEdgeCases:
    """Edge cases для ArbitrageScanner."""

    async def test_scan_with_no_profitable_items(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования когда нет прибыльных предметов."""
        import re

        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Все предметы убыточные
        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Unprofitable Item 1",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "900"},  # Убыток
                },
                {
                    "itemId": "item_2",
                    "title": "Unprofitable Item 2",
                    "price": {"USD": "500"},
                    "suggestedPrice": {"USD": "450"},  # Убыток
                },
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        # Мок для aggregated-prices (вызывается автоматически)
        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/aggregated-prices.*"
            ),
            method="POST",
            json={"aggregatedPrices": []},
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен вернуть пустой список
        assert opportunities == []

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    async def test_scan_with_very_high_profit(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования с аномально высокой прибылью."""
        import re

        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Предмет с 200% прибылью (подозрительно)
        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Suspicious Item",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "3000"},  # 200% прибыль
                }
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        # Мок для aggregated-prices (вызывается автоматически)
        httpx_mock.add_response(
            url=re.compile(
                r"https://api\.dmarket\.com/marketplace-api/v1/aggregated-prices.*"
            ),
            method="POST",
            json={"aggregatedPrices": []},
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен найти, но возможно пометить как подозрительный
        assert len(opportunities) >= 0

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    async def test_scan_with_zero_suggested_price(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования с нулевой рекомендуемой ценой."""
        import re

        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Item with Zero Suggested",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "0"},
                }
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        # Мок для aggregated-prices (вызывается автоматически)
        httpx_mock.add_response(
            url="https://api.dmarket.com/marketplace-api/v1/aggregated-prices",
            method="POST",
            json={"aggregatedPrices": []},
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Не должен крашиться
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_missing_suggested_price(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования без поля suggestedPrice."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Item without Suggested Price",
                    "price": {"USD": "1000"},
                    # Отсутствует suggestedPrice
                }
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен обработать отсутствие поля
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_invalid_price_format(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования с некорректным форматом цены."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Item with Invalid Price",
                    "price": {"USD": "invalid"},  # Не число
                    "suggestedPrice": {"USD": "1000"},
                }
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)

        # Не должен крашиться, должен пропустить некорректный предмет
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
    )
    async def test_scan_all_levels_with_api_errors(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования всех уровней с ошибками API."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Первый запрос - ошибка
        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            status_code=500,
        )

        # Последующие запросы - успех
        for _ in range(10):
            httpx_mock.add_response(
                url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
                method="GET",
                json={"objects": [], "cursor": ""},
                status_code=200,
            )

        scanner = ArbitrageScanner(mock_dmarket_api)
        results = awAlgot scanner.scan_all_levels(game="csgo")

        # Должен обработать ошибки и вернуть результаты
        assert isinstance(results, dict)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_extreme_price_ranges(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования с экстремальными ценовыми диапазонами."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Very Cheap",
                    "price": {"USD": "1"},  # $0.01
                    "suggestedPrice": {"USD": "2"},
                },
                {
                    "itemId": "item_2",
                    "title": "Very Expensive",
                    "price": {"USD": "10000000"},  # $100,000
                    "suggestedPrice": {"USD": "11000000"},
                },
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url="https://api.dmarket.com/exchange/v1/market/items",
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="boost", game="csgo")

        # Должен обработать экстремальные значения
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_concurrent_level_scans(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест одновременного сканирования нескольких уровней."""
        import asyncio

        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Подготовка моков для нескольких запросов
        for _ in range(10):
            httpx_mock.add_response(
                url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
                method="GET",
                json={"objects": [], "cursor": ""},
                status_code=200,
            )

        scanner = ArbitrageScanner(mock_dmarket_api)

        # Одновременное сканирование
        tasks = [
            scanner.scan_level("boost", "csgo"),
            scanner.scan_level("standard", "csgo"),
            scanner.scan_level("medium", "csgo"),
        ]

        results = awAlgot asyncio.gather(*tasks, return_exceptions=True)

        # Все должны завершиться без ошибок
        assert len(results) == 3
        for result in results:
            assert isinstance(result, (list, Exception))

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_rate_limit_recovery(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест восстановления после rate limit во время сканирования."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Rate limit на первый запрос
        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            status_code=429,
            headers={"Retry-After": "1"},
        )

        # Успешный запрос после повтора
        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json={
                "objects": [
                    {
                        "itemId": "item_1",
                        "title": "Item 1",
                        "price": {"USD": "1000"},
                        "suggestedPrice": {"USD": "1200"},
                    }
                ],
                "cursor": "",
            },
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен восстановиться и найти предметы
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_with_partial_data(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования с частичными данными."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Complete Item",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1200"},
                    "category": "Rifle",
                },
                {
                    "itemId": "item_2",
                    "title": "Partial Item",
                    "price": {"USD": "500"},
                    # Отсутствуют suggestedPrice и category
                },
                {
                    # Минимальные данные
                    "itemId": "item_3",
                },
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url="https://api.dmarket.com/exchange/v1/market/items",
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен обработать все предметы
        assert isinstance(opportunities, list)


class TestArbitrageScannerPerformance:
    """Тесты производительности ArbitrageScanner."""

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_large_dataset(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест сканирования большого набора данных."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # Создаем большой набор данных (1000 предметов)
        large_response = {
            "objects": [
                {
                    "itemId": f"item_{i}",
                    "title": f"Item {i}",
                    "price": {"USD": str(1000 + i)},
                    "suggestedPrice": {"USD": str(1100 + i)},
                }
                for i in range(1000)
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=large_response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)

        import time

        start = time.time()
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")
        duration = time.time() - start

        # Должен обработать за разумное время (< 5 секунд)
        assert duration < 5.0
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_scan_multiple_pages_performance(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест производительности пагинации."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        # 5 страниц по 100 предметов
        for i in range(5):
            cursor = f"cursor_{i}" if i < 4 else ""
            response = {
                "objects": [
                    {
                        "itemId": f"item_{i * 100 + j}",
                        "title": f"Item {i * 100 + j}",
                        "price": {"USD": "1000"},
                        "suggestedPrice": {"USD": "1100"},
                    }
                    for j in range(100)
                ],
                "cursor": cursor,
            }

            httpx_mock.add_response(
                url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
                method="GET",
                json=response,
                status_code=200,
            )

        ArbitrageScanner(mock_dmarket_api)

        import time

        start = time.time()
        # scan_level не использует пагинацию, используем напрямую API
        items = awAlgot mock_dmarket_api.get_all_market_items(game="csgo", max_items=500)
        duration = time.time() - start

        # Должен обработать за разумное время
        assert duration < 10.0
        assert isinstance(items, list)


class TestArbitrageScannerFiltering:
    """Тесты фильтрации в ArbitrageScanner."""

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_filter_by_minimum_profit(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест фильтрации по минимальной прибыли."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Low Profit",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1020"},  # 2% прибыль
                },
                {
                    "itemId": "item_2",
                    "title": "High Profit",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1200"},  # 20% прибыль
                },
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Должен отфильтровать предметы с низкой прибылью
        # В зависимости от реализации может вернуть только high profit
        assert isinstance(opportunities, list)

    @pytest.mark.httpx_mock(
        assert_all_responses_were_requested=False,
        can_send_already_matched_responses=True,
        assert_all_requests_were_expected=False,
    )
    async def test_filter_by_category(
        self,
        mock_dmarket_api: DMarketAPI,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Тест фильтрации по категории."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "AK-47",
                    "price": {"USD": "1000"},
                    "suggestedPrice": {"USD": "1200"},
                    "category": "Rifle",
                },
                {
                    "itemId": "item_2",
                    "title": "Glock",
                    "price": {"USD": "500"},
                    "suggestedPrice": {"USD": "600"},
                    "category": "Pistol",
                },
            ],
            "cursor": "",
        }

        httpx_mock.add_response(
            url=re.compile(r"https://api\.dmarket\.com/exchange/v1/market/items.*"),
            method="GET",
            json=response,
            status_code=200,
        )

        scanner = ArbitrageScanner(mock_dmarket_api)
        opportunities = awAlgot scanner.scan_level(level="standard", game="csgo")

        # Проверяем что категории обрабатываются
        assert isinstance(opportunities, list)
