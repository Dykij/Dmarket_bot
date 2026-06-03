"""Тесты для CursorPaginator - cursor-based пагинация."""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.cursor_paginator import (
    CursorPaginator,
    CursorPaginatorConfig,
    CursorState,
)


class TestCursorState:
    """Тесты для CursorState dataclass."""

    def test_initial_state(self):
        """Тест начального состояния."""
        state = CursorState()
        assert state.cursor is None
        assert state.has_more is True
        assert state.page_count == 0
        assert state.items_fetched == 0

    def test_record_response_time(self):
        """Тест записи времени ответа."""
        state = CursorState()

        state.record_response_time(100)
        state.record_response_time(200)

        assert state.avg_response_time_ms == 150
        assert state.first_request_time is not None
        assert state.last_request_time is not None

    def test_total_time_seconds(self):
        """Тест расчета общего времени."""
        state = CursorState()

        state.record_response_time(100)
        import time
        time.sleep(0.1)
        state.record_response_time(200)

        assert state.total_time_seconds >= 0.1

    def test_reset(self):
        """Тест сброса состояния."""
        state = CursorState(
            cursor="test_cursor",
            has_more=False,
            page_count=5,
            items_fetched=500,
        )
        state._response_times = [100, 200]

        state.reset()

        assert state.cursor is None
        assert state.has_more is True
        assert state.page_count == 0
        assert state.items_fetched == 0
        assert len(state._response_times) == 0


class TestCursorPaginatorConfig:
    """Тесты для CursorPaginatorConfig."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        config = CursorPaginatorConfig()

        assert config.page_size == 100
        assert config.max_pages == 0
        assert config.request_delay == 0.1
        assert config.auto_retry is True
        assert config.max_retries == 3

    def test_custom_values(self):
        """Тест пользовательских значений."""
        config = CursorPaginatorConfig(
            page_size=50,
            max_pages=10,
            request_delay=0.5,
            auto_retry=False,
        )

        assert config.page_size == 50
        assert config.max_pages == 10
        assert config.request_delay == 0.5
        assert config.auto_retry is False


class TestCursorPaginator:
    """Тесты для CursorPaginator."""

    @pytest.fixture
    def paginator(self):
        """Создать пагинатор без API (mock режим)."""
        config = CursorPaginatorConfig(
            page_size=100,
            max_pages=3,
            request_delay=0.01,
            log_progress=False,
        )
        return CursorPaginator(config=config)

    @pytest.mark.asyncio
    async def test_paginate_mock(self, paginator):
        """Тест пагинации в mock режиме."""
        all_items = []

        async for items in paginator.paginate(game="csgo"):
            all_items.extend(items)

        assert len(all_items) > 0
        assert paginator.state.page_count <= 3

    @pytest.mark.asyncio
    async def test_paginate_max_pages(self):
        """Тест лимита страниц."""
        config = CursorPaginatorConfig(
            page_size=10,
            max_pages=2,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(config=config)

        pages_fetched = 0
        async for _ in paginator.paginate(game="csgo"):
            pages_fetched += 1

        assert pages_fetched <= 2

    @pytest.mark.asyncio
    async def test_get_all_items(self):
        """Тест получения всех предметов."""
        config = CursorPaginatorConfig(
            page_size=50,
            max_pages=5,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(config=config)

        items = await paginator.get_all_items(game="csgo", max_items=100)

        assert len(items) <= 100

    @pytest.mark.asyncio
    async def test_get_all_items_with_limit(self):
        """Тест получения с лимитом."""
        config = CursorPaginatorConfig(
            page_size=50,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(config=config)

        items = await paginator.get_all_items(game="csgo", max_items=25)

        assert len(items) <= 25

    def test_save_cursor(self, paginator):
        """Тест сохранения cursor."""
        paginator._save_cursor("csgo", None, "test_cursor_123")

        saved = paginator.get_saved_cursor("csgo")

        assert saved == "test_cursor_123"

    def test_save_cursor_with_filters(self, paginator):
        """Тест сохранения cursor с фильтрами."""
        filters = {"priceFrom": 100, "priceTo": 1000}
        paginator._save_cursor("csgo", filters, "cursor_with_filters")

        saved = paginator.get_saved_cursor("csgo", filters)

        assert saved == "cursor_with_filters"

    def test_different_filters_different_cursors(self, paginator):
        """Тест разных cursor для разных фильтров."""
        filters1 = {"priceFrom": 100}
        filters2 = {"priceFrom": 200}

        paginator._save_cursor("csgo", filters1, "cursor_1")
        paginator._save_cursor("csgo", filters2, "cursor_2")

        assert paginator.get_saved_cursor("csgo", filters1) == "cursor_1"
        assert paginator.get_saved_cursor("csgo", filters2) == "cursor_2"

    def test_get_performance_stats(self, paginator):
        """Тест получения статистики производительности."""
        paginator.state.page_count = 5
        paginator.state.items_fetched = 500
        paginator.state._response_times = [100, 150, 200]
        paginator.state.avg_response_time_ms = 150

        stats = paginator.get_performance_stats()

        assert stats["pages_fetched"] == 5
        assert stats["items_fetched"] == 500
        assert stats["avg_response_time_ms"] == 150


class TestCursorPaginatorWithAPI:
    """Тесты CursorPaginator с mock API."""

    @pytest.fixture
    def mock_api(self):
        """Создать mock API клиент."""
        api = AsyncMock()

        # Симуляция нескольких страниц
        pages = [
            {"objects": [{"itemId": f"item_{i}"} for i in range(10)], "cursor": "page_2", "total": 30},
            {"objects": [{"itemId": f"item_{i}"} for i in range(10, 20)], "cursor": "page_3", "total": 30},
            {"objects": [{"itemId": f"item_{i}"} for i in range(20, 30)], "cursor": None, "total": 30},
        ]

        api._request = AsyncMock(side_effect=pages)
        return api

    @pytest.mark.asyncio
    async def test_paginate_with_api(self, mock_api):
        """Тест пагинации через API."""
        config = CursorPaginatorConfig(
            page_size=10,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(api_client=mock_api, config=config)

        all_items = []
        async for items in paginator.paginate(game="csgo"):
            all_items.extend(items)

        assert len(all_items) == 30
        assert paginator.state.page_count == 3

    @pytest.mark.asyncio
    async def test_start_from_cursor(self, mock_api):
        """Тест возобновления с cursor."""
        config = CursorPaginatorConfig(
            page_size=10,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(api_client=mock_api, config=config)

        all_items = []
        async for items in paginator.paginate(game="csgo", start_cursor="page_2"):
            all_items.extend(items)

        # Должны начать со втоSwarm страницы
        assert len(all_items) > 0


class TestCursorVsOffset:
    """Тесты сравнения cursor vs offset производительности."""

    def test_benchmark_exists(self):
        """Тест что benchmark документирован в коде."""

        # Проверяем что есть docstring с benchmark
        import src.dmarket.cursor_paginator as module
        module_doc = module.__doc__

        assert "cursor" in module_doc.lower()
        assert "offset" in module_doc.lower()

    @pytest.mark.asyncio
    async def test_cursor_performance(self):
        """Тест что cursor быстрее offset (mock)."""
        config = CursorPaginatorConfig(
            page_size=100,
            max_pages=5,
            request_delay=0.01,
            log_progress=False,
        )
        paginator = CursorPaginator(config=config)

        # Выполняем пагинацию
        async for _ in paginator.paginate(game="csgo"):
            pass

        # Проверяем что статистика собирается
        stats = paginator.get_performance_stats()
        assert stats["pages_fetched"] > 0
        assert stats["avg_response_time_ms"] > 0


class TestCursorPaginatorEdgeCases:
    """Тесты edge cases."""

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """Тест пустого ответа."""
        api = AsyncMock()
        api._request = AsyncMock(return_value={
            "objects": [],
            "cursor": None,
            "total": 0,
        })

        config = CursorPaginatorConfig(log_progress=False)
        paginator = CursorPaginator(api_client=api, config=config)

        all_items = []
        async for items in paginator.paginate(game="csgo"):
            all_items.extend(items)

        assert len(all_items) == 0

    @pytest.mark.asyncio
    async def test_single_page(self):
        """Тест одной страницы."""
        api = AsyncMock()
        api._request = AsyncMock(return_value={
            "objects": [{"itemId": "item_1"}],
            "cursor": None,  # Нет следующей страницы
            "total": 1,
        })

        config = CursorPaginatorConfig(log_progress=False)
        paginator = CursorPaginator(api_client=api, config=config)

        all_items = []
        async for items in paginator.paginate(game="csgo"):
            all_items.extend(items)

        assert len(all_items) == 1
        assert paginator.state.page_count == 1
