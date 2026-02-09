"""Bulkhead Pattern - изоляция компонентов для предотвращения каскадных сбоев.

Этот модуль реализует паттерн Bulkhead (переборка), который:
1. Ограничивает количество одновременных операций для каждого компонента
2. Предотвращает распространение сбоев между компонентами
3. Обеспечивает graceful degradation при перегрузке
4. Предоставляет метрики использования ресурсов

Аналогия: В корабле переборки разделяют отсеки, чтобы пробоина
в одном не затопила весь корабль. Так же и здесь - сбой одного
компонента (например, API) не повлияет на другие (бот, БД).

Использование:
    >>> api_bulkhead = Bulkhead("api", max_concurrent=10)
    >>> async with api_bulkhead.acquire():
    ...     await api.call()

    # Или с таймаутом:
    >>> async with api_bulkhead.acquire(timeout=5.0):
    ...     await api.call()

Created: January 2026
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)


class BulkheadState(StrEnum):
    """Состояние Bulkhead."""

    HEALTHY = "healthy"  # Нормальная работа
    DEGRADED = "degraded"  # Высокая нагрузка (>80%)
    SATURATED = "saturated"  # Полностью загружен (100%)


@dataclass
class BulkheadStats:
    """Статистика использования Bulkhead.

    Attributes:
        total_acquired: Общее количество успешных захватов
        total_rejected: Общее количество отклоненных (таймаут/перегрузка)
        total_released: Общее количество освобождений
        current_active: Текущее количество активных операций
        max_concurrent_reached: Максимальное одновременное использование
        avg_wait_time_ms: Среднее время ожидания в мс
        last_rejection_time: Время последнего отклонения
    """

    total_acquired: int = 0
    total_rejected: int = 0
    total_released: int = 0
    current_active: int = 0
    max_concurrent_reached: int = 0
    avg_wait_time_ms: float = 0.0
    last_rejection_time: datetime | None = None
    _wait_times: list[float] = field(default_factory=list)

    def record_acquire(self, wait_time_ms: float) -> None:
        """Записать успешный захват."""
        self.total_acquired += 1
        self.current_active += 1
        self.max_concurrent_reached = max(
            self.max_concurrent_reached,
            self.current_active,
        )

        # Обновить среднее время ожидания (скользящее окно)
        self._wait_times.append(wait_time_ms)
        if len(self._wait_times) > 100:
            self._wait_times = self._wait_times[-100:]
        self.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times)

    def record_release(self) -> None:
        """Записать освобождение."""
        self.total_released += 1
        self.current_active = max(0, self.current_active - 1)

    def record_rejection(self) -> None:
        """Записать отклонение."""
        self.total_rejected += 1
        self.last_rejection_time = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "total_acquired": self.total_acquired,
            "total_rejected": self.total_rejected,
            "total_released": self.total_released,
            "current_active": self.current_active,
            "max_concurrent_reached": self.max_concurrent_reached,
            "avg_wait_time_ms": round(self.avg_wait_time_ms, 2),
            "last_rejection_time": (
                self.last_rejection_time.isoformat()
                if self.last_rejection_time
                else None
            ),
            "rejection_rate": (
                self.total_rejected / (self.total_acquired + self.total_rejected) * 100
                if (self.total_acquired + self.total_rejected) > 0
                else 0
            ),
        }


class BulkheadFullError(Exception):
    """Исключение при невозможности получить слот в Bulkhead."""

    def __init__(self, bulkhead_name: str, timeout: float | None = None) -> None:
        """Инициализация исключения.

        Args:
            bulkhead_name: Название bulkhead
            timeout: Таймаут ожидания (если был)
        """
        self.bulkhead_name = bulkhead_name
        self.timeout = timeout
        message = f"Bulkhead '{bulkhead_name}' is full"
        if timeout:
            message += f" (timeout: {timeout}s)"
        super().__init__(message)


class Bulkhead:
    """Bulkhead для изоляции компонентов и ограничения параллелизма.

    Пример использования:
        # Создание bulkhead для API
        api_bulkhead = Bulkhead("dmarket_api", max_concurrent=20)

        # Использование в коде
        async with api_bulkhead.acquire(timeout=10.0):
            result = await api.get_items()

        # Проверка состояния
        state = api_bulkhead.get_state()
        print(f"API bulkhead state: {state}")
    """

    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        warn_threshold: float = 0.8,
    ) -> None:
        """Инициализация Bulkhead.

        Args:
            name: Название bulkhead (для логов и метрик)
            max_concurrent: Максимальное количество одновременных операций
            warn_threshold: Порог предупреждения (доля от max_concurrent)
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.warn_threshold = warn_threshold

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = BulkheadStats()

        logger.info(
            "bulkhead_initialized",
            name=name,
            max_concurrent=max_concurrent,
            warn_threshold=warn_threshold,
        )

    @asynccontextmanager
    async def acquire(
        self,
        timeout: float | None = 30.0,
    ) -> AsyncGenerator[None, None]:
        """Получить слот в bulkhead.

        Args:
            timeout: Максимальное время ожидания в секундах.
                    None = бесконечное ожидание.

        Yields:
            None (context manager)

        Raises:
            BulkheadFullError: Если не удалось получить слот за timeout
            asyncio.TimeoutError: Если истёк timeout

        Example:
            async with bulkhead.acquire(timeout=5.0):
                await do_something()
        """
        start_time = asyncio.get_event_loop().time()

        try:
            if timeout is not None:
                acquired = await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=timeout,
                )
            else:
                acquired = await self._semaphore.acquire()

            if not acquired:
                self._stats.record_rejection()
                self._track_metrics("rejected")
                raise BulkheadFullError(self.name, timeout)

            # Записать время ожидания
            wait_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            self._stats.record_acquire(wait_time_ms)
            self._track_metrics("acquired")

            # Проверить состояние и залогировать предупреждения
            self._check_and_warn()

            try:
                yield
            finally:
                self._semaphore.release()
                self._stats.record_release()
                self._track_metrics("released")

        except TimeoutError:
            self._stats.record_rejection()
            self._track_metrics("timeout")
            logger.warning(
                "bulkhead_timeout",
                name=self.name,
                timeout=timeout,
                current_active=self._stats.current_active,
                max_concurrent=self.max_concurrent,
            )
            raise BulkheadFullError(self.name, timeout) from None

    def _check_and_warn(self) -> None:
        """Проверить состояние и выдать предупреждения."""
        usage = self._stats.current_active / self.max_concurrent

        if usage >= 1.0:
            logger.error(
                "bulkhead_saturated",
                name=self.name,
                current_active=self._stats.current_active,
                max_concurrent=self.max_concurrent,
            )
        elif usage >= self.warn_threshold:
            logger.warning(
                "bulkhead_high_usage",
                name=self.name,
                usage_percent=round(usage * 100, 1),
                current_active=self._stats.current_active,
                max_concurrent=self.max_concurrent,
            )

    def get_state(self) -> BulkheadState:
        """Получить текущее состояние bulkhead.

        Returns:
            BulkheadState: HEALTHY, DEGRADED или SATURATED
        """
        usage = self._stats.current_active / self.max_concurrent

        if usage >= 1.0:
            return BulkheadState.SATURATED
        if usage >= self.warn_threshold:
            return BulkheadState.DEGRADED
        return BulkheadState.HEALTHY

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику использования.

        Returns:
            Словарь со статистикой
        """
        stats = self._stats.to_dict()
        stats["name"] = self.name
        stats["max_concurrent"] = self.max_concurrent
        stats["state"] = self.get_state().value
        stats["available_slots"] = self.max_concurrent - self._stats.current_active
        return stats

    def is_available(self) -> bool:
        """Проверить, есть ли свободные слоты.

        Returns:
            True если есть свободные слоты
        """
        return self._stats.current_active < self.max_concurrent

    @property
    def current_usage(self) -> float:
        """Текущий процент использования (0.0 - 1.0)."""
        return self._stats.current_active / self.max_concurrent

    @property
    def available_slots(self) -> int:
        """Количество свободных слотов."""
        return max(0, self.max_concurrent - self._stats.current_active)

    def _track_metrics(self, action: str) -> None:
        """Обновить Prometheus метрики.

        Args:
            action: Тип действия (acquired, released, rejected, timeout)
        """
        try:
            from src.utils.prometheus_metrics import (
                BULKHEAD_ACTIVE,
                BULKHEAD_OPERATIONS,
            )

            BULKHEAD_OPERATIONS.labels(
                bulkhead=self.name,
                action=action,
            ).inc()

            BULKHEAD_ACTIVE.labels(
                bulkhead=self.name,
            ).set(self._stats.current_active)
        except ImportError:
            pass  # Prometheus not available


class BulkheadRegistry:
    """Реестр всех Bulkhead в системе.

    Централизованное управление и мониторинг всех bulkhead.

    Использование:
        >>> registry = BulkheadRegistry()
        >>> api_bulkhead = registry.create("api", max_concurrent=20)
        >>> db_bulkhead = registry.create("database", max_concurrent=50)
        >>>
        >>> # Получить bulkhead по имени
        >>> api = registry.get("api")
        >>>
        >>> # Получить статистику всех bulkhead
        >>> stats = registry.get_all_stats()
    """

    def __init__(self) -> None:
        """Инициализация реестра."""
        self._bulkheads: dict[str, Bulkhead] = {}

    def create(
        self,
        name: str,
        max_concurrent: int = 10,
        warn_threshold: float = 0.8,
    ) -> Bulkhead:
        """Создать новый bulkhead и зарегистрировать его.

        Args:
            name: Уникальное название bulkhead
            max_concurrent: Максимум одновременных операций
            warn_threshold: Порог предупреждения

        Returns:
            Созданный Bulkhead

        Raises:
            ValueError: Если bulkhead с таким именем уже существует
        """
        if name in self._bulkheads:
            raise ValueError(f"Bulkhead '{name}' already exists")

        bulkhead = Bulkhead(name, max_concurrent, warn_threshold)
        self._bulkheads[name] = bulkhead

        logger.info(
            "bulkhead_registered",
            name=name,
            total_bulkheads=len(self._bulkheads),
        )

        return bulkhead

    def get(self, name: str) -> Bulkhead | None:
        """Получить bulkhead по имени.

        Args:
            name: Название bulkhead

        Returns:
            Bulkhead или None если не найден
        """
        return self._bulkheads.get(name)

    def get_or_create(
        self,
        name: str,
        max_concurrent: int = 10,
        warn_threshold: float = 0.8,
    ) -> Bulkhead:
        """Получить существующий bulkhead или создать новый.

        Args:
            name: Название bulkhead
            max_concurrent: Максимум одновременных операций
            warn_threshold: Порог предупреждения

        Returns:
            Существующий или новый Bulkhead
        """
        if name in self._bulkheads:
            return self._bulkheads[name]
        return self.create(name, max_concurrent, warn_threshold)

    def remove(self, name: str) -> bool:
        """Удалить bulkhead из реестра.

        Args:
            name: Название bulkhead

        Returns:
            True если был удалён, False если не найден
        """
        if name in self._bulkheads:
            del self._bulkheads[name]
            logger.info("bulkhead_removed", name=name)
            return True
        return False

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Получить статистику всех bulkhead.

        Returns:
            Словарь {name: stats}
        """
        return {name: b.get_stats() for name, b in self._bulkheads.items()}

    def get_unhealthy(self) -> list[str]:
        """Получить список bulkhead с высокой нагрузкой.

        Returns:
            Список названий bulkhead в состоянии DEGRADED или SATURATED
        """
        return [
            name
            for name, b in self._bulkheads.items()
            if b.get_state() != BulkheadState.HEALTHY
        ]

    @property
    def names(self) -> list[str]:
        """Список всех зарегистрированных названий."""
        return list(self._bulkheads.keys())


# Глобальный реестр bulkhead
_registry: BulkheadRegistry | None = None


def get_bulkhead_registry() -> BulkheadRegistry:
    """Получить глобальный реестр bulkhead.

    Returns:
        BulkheadRegistry
    """
    global _registry
    if _registry is None:
        _registry = BulkheadRegistry()
    return _registry


# Предустановленные bulkhead для основных компонентов
def get_api_bulkhead() -> Bulkhead:
    """Получить bulkhead для API вызовов."""
    return get_bulkhead_registry().get_or_create(
        "dmarket_api",
        max_concurrent=20,
        warn_threshold=0.8,
    )


def get_database_bulkhead() -> Bulkhead:
    """Получить bulkhead для операций с БД."""
    return get_bulkhead_registry().get_or_create(
        "database",
        max_concurrent=50,
        warn_threshold=0.9,
    )


def get_scanner_bulkhead() -> Bulkhead:
    """Получить bulkhead для операций сканирования."""
    return get_bulkhead_registry().get_or_create(
        "scanner",
        max_concurrent=5,
        warn_threshold=0.8,
    )


def get_notification_bulkhead() -> Bulkhead:
    """Получить bulkhead для отправки уведомлений."""
    return get_bulkhead_registry().get_or_create(
        "notifications",
        max_concurrent=10,
        warn_threshold=0.7,
    )


__all__ = [
    "Bulkhead",
    "BulkheadFullError",
    "BulkheadRegistry",
    "BulkheadState",
    "BulkheadStats",
    "get_api_bulkhead",
    "get_bulkhead_registry",
    "get_database_bulkhead",
    "get_notification_bulkhead",
    "get_scanner_bulkhead",
]
