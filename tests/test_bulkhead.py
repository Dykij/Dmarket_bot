"""Тесты для Bulkhead паттерна.

Тестирование функциональности:
- Ограничение параллельных операций
- Таймауты
- Статистика и состояния
- Реестр bulkhead
"""

import asyncio

import pytest

from src.utils.bulkhead import (
    Bulkhead,
    BulkheadFullError,
    BulkheadRegistry,
    BulkheadState,
    get_api_bulkhead,
    get_database_bulkhead,
)


class TestBulkhead:
    """Тесты для класса Bulkhead."""

    @pytest.fixture
    def bulkhead(self):
        """Фикстура для создания Bulkhead."""
        return Bulkhead("test_bulkhead", max_concurrent=3, warn_threshold=0.7)

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, bulkhead):
        """Тест получения и освобождения слота."""
        assert bulkhead.available_slots == 3
        assert bulkhead.current_usage == 0.0

        async with bulkhead.acquire():
            assert bulkhead.available_slots == 2
            assert bulkhead.current_usage == pytest.approx(1 / 3, rel=0.01)

        assert bulkhead.available_slots == 3

    @pytest.mark.asyncio
    async def test_max_concurrent_limit(self, bulkhead):
        """Тест ограничения параллельных операций."""
        acquired = []

        async def acquire_slot():
            async with bulkhead.acquire(timeout=0.1):
                acquired.append(True)
                await asyncio.sleep(0.5)

        # Запускаем 4 задачи, но max_concurrent=3
        tasks = [asyncio.create_task(acquire_slot()) for _ in range(4)]

        # Даём время на запуск
        await asyncio.sleep(0.1)

        # Три должны успеть захватить слот
        assert bulkhead.available_slots == 0

        # Ждём завершения
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Три успешных, один с ошибкой таймаута
        errors = [r for r in results if isinstance(r, BulkheadFullError)]
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, bulkhead):
        """Тест ошибки при таймауте."""
        # Занимаем все слоты
        async def hold_slot():
            async with bulkhead.acquire():
                await asyncio.sleep(2)

        tasks = [asyncio.create_task(hold_slot()) for _ in range(3)]
        await asyncio.sleep(0.1)

        # Попытка захвата с коротким таймаутом
        with pytest.raises(BulkheadFullError) as exc_info:
            async with bulkhead.acquire(timeout=0.1):
                pass

        assert exc_info.value.bulkhead_name == "test_bulkhead"
        assert exc_info.value.timeout == 0.1

        # Отменяем задачи
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_state_transitions(self, bulkhead):
        """Тест переходов состояний."""
        assert bulkhead.get_state() == BulkheadState.HEALTHY

        # Занимаем 3 из 3 слотов (100%) и держим их
        hold_event = asyncio.Event()

        async def hold():
            async with bulkhead.acquire():
                await hold_event.wait()
                return True

        tasks = [asyncio.create_task(hold()) for _ in range(3)]
        await asyncio.sleep(0.1)  # Дать задачам время захватить слоты

        assert bulkhead.get_state() == BulkheadState.SATURATED

        # Освобождаем слоты
        hold_event.set()
        await asyncio.gather(*tasks)

        assert bulkhead.get_state() == BulkheadState.HEALTHY

    @pytest.mark.asyncio
    async def test_degraded_state(self):
        """Тест состояния DEGRADED."""
        bulkhead = Bulkhead("test", max_concurrent=10, warn_threshold=0.5)

        assert bulkhead.get_state() == BulkheadState.HEALTHY

        async def hold():
            async with bulkhead.acquire():
                await asyncio.sleep(0.5)

        # Занимаем 6 из 10 (60% > 50% threshold)
        tasks = [asyncio.create_task(hold()) for _ in range(6)]
        await asyncio.sleep(0.1)

        assert bulkhead.get_state() == BulkheadState.DEGRADED

        # Ждём завершения
        await asyncio.gather(*tasks)

    @pytest.mark.asyncio
    async def test_stats_tracking(self, bulkhead):
        """Тест отслеживания статистики."""
        stats_before = bulkhead.get_stats()
        assert stats_before["total_acquired"] == 0

        async with bulkhead.acquire():
            pass

        stats_after = bulkhead.get_stats()
        assert stats_after["total_acquired"] == 1
        assert stats_after["total_released"] == 1
        assert stats_after["max_concurrent_reached"] == 1

    @pytest.mark.asyncio
    async def test_is_available(self, bulkhead):
        """Тест проверки доступности."""
        assert bulkhead.is_available() is True

        # Занимаем все слоты
        async def hold():
            async with bulkhead.acquire():
                await asyncio.sleep(0.5)

        tasks = [asyncio.create_task(hold()) for _ in range(3)]
        await asyncio.sleep(0.1)

        assert bulkhead.is_available() is False

        await asyncio.gather(*tasks)

        assert bulkhead.is_available() is True

    @pytest.mark.asyncio
    async def test_infinite_wait(self):
        """Тест бесконечного ожидания (timeout=None)."""
        bulkhead = Bulkhead("test", max_concurrent=1)

        release_event = asyncio.Event()

        async def hold_and_release():
            async with bulkhead.acquire():
                await release_event.wait()

        # Запускаем первую задачу
        task1 = asyncio.create_task(hold_and_release())
        await asyncio.sleep(0.1)

        # Запускаем вторую с бесконечным ожиданием
        async def wait_infinite():
            async with bulkhead.acquire(timeout=None):
                return True

        task2 = asyncio.create_task(wait_infinite())
        await asyncio.sleep(0.1)

        # task2 должна ждать
        assert not task2.done()

        # Освобождаем первый слот
        release_event.set()
        await task1

        # Теперь task2 должна завершиться
        result = await asyncio.wait_for(task2, timeout=1.0)
        assert result is True


class TestBulkheadRegistry:
    """Тесты для BulkheadRegistry."""

    @pytest.fixture
    def registry(self):
        """Фикстура для создания реестра."""
        return BulkheadRegistry()

    def test_create_bulkhead(self, registry):
        """Тест создания bulkhead через реестр."""
        bulkhead = registry.create("test", max_concurrent=5)

        assert bulkhead.name == "test"
        assert bulkhead.max_concurrent == 5
        assert "test" in registry.names

    def test_create_duplicate_raises_error(self, registry):
        """Тест ошибки при создании дубликата."""
        registry.create("test", max_concurrent=5)

        with pytest.raises(ValueError, match="already exists"):
            registry.create("test", max_concurrent=10)

    def test_get_bulkhead(self, registry):
        """Тест получения bulkhead по имени."""
        created = registry.create("test", max_concurrent=5)
        retrieved = registry.get("test")

        assert retrieved is created
        assert registry.get("nonexistent") is None

    def test_get_or_create(self, registry):
        """Тест get_or_create."""
        # Первый вызов создаёт
        bulkhead1 = registry.get_or_create("test", max_concurrent=5)

        # Второй вызов возвращает существующий
        bulkhead2 = registry.get_or_create("test", max_concurrent=10)

        assert bulkhead1 is bulkhead2
        assert bulkhead1.max_concurrent == 5  # Не изменился

    def test_remove_bulkhead(self, registry):
        """Тест удаления bulkhead."""
        registry.create("test", max_concurrent=5)

        assert registry.remove("test") is True
        assert registry.get("test") is None
        assert registry.remove("test") is False  # Уже удалён

    @pytest.mark.asyncio
    async def test_get_all_stats(self, registry):
        """Тест получения статистики всех bulkhead."""
        registry.create("api", max_concurrent=10)
        registry.create("db", max_concurrent=50)

        stats = registry.get_all_stats()

        assert "api" in stats
        assert "db" in stats
        assert stats["api"]["max_concurrent"] == 10
        assert stats["db"]["max_concurrent"] == 50

    @pytest.mark.asyncio
    async def test_get_unhealthy(self, registry):
        """Тест получения unhealthy bulkhead."""
        bulkhead = registry.create("test", max_concurrent=2, warn_threshold=0.5)

        assert registry.get_unhealthy() == []

        # Занимаем оба слота
        async def hold():
            async with bulkhead.acquire():
                await asyncio.sleep(0.5)

        tasks = [asyncio.create_task(hold()) for _ in range(2)]
        await asyncio.sleep(0.1)

        unhealthy = registry.get_unhealthy()
        assert "test" in unhealthy

        await asyncio.gather(*tasks)


class TestPresetBulkheads:
    """Тесты для предустановленных bulkhead."""

    def test_get_api_bulkhead(self):
        """Тест получения API bulkhead."""
        bulkhead = get_api_bulkhead()

        assert bulkhead.name == "dmarket_api"
        assert bulkhead.max_concurrent == 20

    def test_get_database_bulkhead(self):
        """Тест получения Database bulkhead."""
        bulkhead = get_database_bulkhead()

        assert bulkhead.name == "database"
        assert bulkhead.max_concurrent == 50

    def test_singleton_behavior(self):
        """Тест singleton поведения через реестр."""
        bulkhead1 = get_api_bulkhead()
        bulkhead2 = get_api_bulkhead()

        assert bulkhead1 is bulkhead2
