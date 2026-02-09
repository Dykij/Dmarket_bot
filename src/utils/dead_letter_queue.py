"""Dead Letter Queue - сохранение неудавшихся операций для повторной обработки.

Этот модуль обеспечивает:
1. Сохранение операций, которые не удалось выполнить после всех retry
2. Периодическую повторную обработку операций из очереди
3. Персистентное хранение в Redis (опционально)
4. Метрики для мониторинга
5. Уведомления о критических операциях

Использование:
    >>> dlq = DeadLetterQueue()
    >>> await dlq.add(FailedOperation(
    ...     operation_type="buy_item",
    ...     payload={"item_id": "123", "price": 10.50},
    ...     error="API timeout",
    ... ))
    >>> # Позже - повторная обработка
    >>> batch = await dlq.get_batch(10)
    >>> for op in batch:
    ...     await retry_operation(op)

Created: January 2026
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class OperationType(StrEnum):
    """Типы операций для Dead Letter Queue."""

    BUY_ITEM = "buy_item"
    SELL_ITEM = "sell_item"
    CREATE_TARGET = "create_target"
    DELETE_TARGET = "delete_target"
    UPDATE_PRICE = "update_price"
    SEND_NOTIFICATION = "send_notification"
    SYNC_INVENTORY = "sync_inventory"
    OTHER = "other"


class OperationPriority(StrEnum):
    """Приоритет операций."""

    CRITICAL = "critical"  # Торговые операции - деньги
    HIGH = "high"  # Таргеты, ценовые обновления
    MEDIUM = "medium"  # Синхронизация инвентаря
    LOW = "low"  # Уведомления


@dataclass
class FailedOperation:
    """Неудавшаяся операция для сохранения в DLQ.

    Attributes:
        operation_type: Тип операции (buy, sell, target и т.д.)
        payload: Данные операции (параметры, контекст)
        error: Описание ошибки
        timestamp: Время первой неудачи
        retry_count: Количество попыток выполнения
        priority: Приоритет операции
        user_id: ID пользователя (для уведомлений)
        correlation_id: ID для трейсинга операции
        last_retry_at: Время последней попытки
        max_retries: Максимальное количество попыток
    """

    operation_type: str
    payload: dict[str, Any]
    error: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0
    priority: str = OperationPriority.MEDIUM
    user_id: int | None = None
    correlation_id: str | None = None
    last_retry_at: datetime | None = None
    max_retries: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь для сериализации."""
        data = asdict(self)
        # Преобразуем datetime в ISO строку
        data["timestamp"] = self.timestamp.isoformat()
        if self.last_retry_at:
            data["last_retry_at"] = self.last_retry_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailedOperation:
        """Создать из словаря."""
        # Преобразуем ISO строку обратно в datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("last_retry_at"), str):
            data["last_retry_at"] = datetime.fromisoformat(data["last_retry_at"])
        return cls(**data)

    def can_retry(self) -> bool:
        """Проверить, можно ли повторить операцию."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Увеличить счётчик попыток."""
        self.retry_count += 1
        self.last_retry_at = datetime.now(UTC)


class DeadLetterQueue:
    """Dead Letter Queue для сохранения неудавшихся операций.

    Поддерживает:
    - In-memory хранение (по умолчанию)
    - Redis persistence (опционально)
    - Приоритизацию операций
    - Batch processing
    - Метрики и мониторинг
    """

    def __init__(
        self,
        max_size: int = 1000,
        redis_client: Redis | None = None,
        redis_key: str = "dlq:operations",
    ) -> None:
        """Инициализация Dead Letter Queue.

        Args:
            max_size: Максимальный размер очереди в памяти
            redis_client: Redis клиент для персистентности (опционально)
            redis_key: Ключ для хранения в Redis
        """
        self._queue: deque[FailedOperation] = deque(maxlen=max_size)
        self._redis = redis_client
        self._redis_key = redis_key
        self._lock = asyncio.Lock()

        # Статистика
        self._total_added = 0
        self._total_processed = 0
        self._total_expired = 0

        logger.info(
            "dead_letter_queue_initialized",
            max_size=max_size,
            redis_enabled=redis_client is not None,
        )

    async def add(self, operation: FailedOperation) -> None:
        """Добавить неудавшуюся операцию в очередь.

        Args:
            operation: Операция для сохранения
        """
        async with self._lock:
            self._queue.append(operation)
            self._total_added += 1

            # Сохранить в Redis если настроен
            if self._redis:
                try:
                    await self._redis.rpush(
                        self._redis_key,
                        json.dumps(operation.to_dict()),
                    )
                except Exception as e:
                    logger.warning(
                        "dlq_redis_save_failed",
                        error=str(e),
                        operation_type=operation.operation_type,
                    )

            # Обновить метрики Prometheus
            self._track_metrics("add", operation)

            logger.warning(
                "operation_added_to_dlq",
                operation_type=operation.operation_type,
                error=operation.error,
                retry_count=operation.retry_count,
                user_id=operation.user_id,
                priority=operation.priority,
                queue_size=len(self._queue),
            )

    async def get_batch(
        self,
        batch_size: int = 10,
        priority: str | None = None,
    ) -> list[FailedOperation]:
        """Получить партию операций для повторной обработки.

        Args:
            batch_size: Размер партии
            priority: Фильтр по приоритету (опционально)

        Returns:
            Список операций для обработки
        """
        async with self._lock:
            batch: list[FailedOperation] = []
            remaining: list[FailedOperation] = []

            while self._queue and len(batch) < batch_size:
                op = self._queue.popleft()

                # Фильтр по приоритету
                if priority and op.priority != priority:
                    remaining.append(op)
                    continue

                # Проверка на возможность retry
                if op.can_retry():
                    batch.append(op)
                else:
                    self._total_expired += 1
                    logger.error(
                        "dlq_operation_expired",
                        operation_type=op.operation_type,
                        retry_count=op.retry_count,
                        max_retries=op.max_retries,
                        user_id=op.user_id,
                    )

            # Вернуть неподходящие операции обратно
            for op in remaining:
                self._queue.appendleft(op)

            return batch

    async def return_to_queue(self, operation: FailedOperation) -> None:
        """Вернуть операцию обратно в очередь после неудачной повторной попытки.

        Args:
            operation: Операция для возврата
        """
        operation.increment_retry()

        if operation.can_retry():
            async with self._lock:
                # Добавляем в конец очереди
                self._queue.append(operation)
            logger.info(
                "dlq_operation_returned",
                operation_type=operation.operation_type,
                retry_count=operation.retry_count,
            )
        else:
            self._total_expired += 1
            logger.error(
                "dlq_operation_max_retries_exceeded",
                operation_type=operation.operation_type,
                retry_count=operation.retry_count,
                user_id=operation.user_id,
            )

    async def mark_processed(self, operation: FailedOperation) -> None:
        """Отметить операцию как успешно обработанную.

        Args:
            operation: Обработанная операция
        """
        self._total_processed += 1
        self._track_metrics("processed", operation)

        logger.info(
            "dlq_operation_processed",
            operation_type=operation.operation_type,
            retry_count=operation.retry_count,
            user_id=operation.user_id,
        )

    async def get_by_priority(self, priority: str) -> list[FailedOperation]:
        """Получить все операции с заданным приоритетом.

        Args:
            priority: Приоритет для фильтрации

        Returns:
            Список операций с заданным приоритетом
        """
        async with self._lock:
            return [op for op in self._queue if op.priority == priority]

    async def get_by_user(self, user_id: int) -> list[FailedOperation]:
        """Получить все операции для конкретного пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список операций пользователя
        """
        async with self._lock:
            return [op for op in self._queue if op.user_id == user_id]

    async def clear(self) -> int:
        """Очистить очередь.

        Returns:
            Количество удалённых операций
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()

            if self._redis:
                try:
                    await self._redis.delete(self._redis_key)
                except Exception as e:
                    logger.warning("dlq_redis_clear_failed", error=str(e))

            logger.warning("dlq_cleared", count=count)
            return count

    async def load_from_redis(self) -> int:
        """Загрузить операции из Redis при старте.

        Returns:
            Количество загруженных операций
        """
        if not self._redis:
            return 0

        try:
            data = await self._redis.lrange(self._redis_key, 0, -1)
            count = 0

            for item in data:
                try:
                    op_dict = json.loads(item)
                    operation = FailedOperation.from_dict(op_dict)
                    self._queue.append(operation)
                    count += 1
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("dlq_redis_load_item_failed", error=str(e))

            logger.info("dlq_loaded_from_redis", count=count)
            return count

        except Exception as e:
            logger.exception("dlq_redis_load_failed", error=str(e))
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику очереди.

        Returns:
            Словарь со статистикой
        """
        by_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for op in self._queue:
            by_type[op.operation_type] = by_type.get(op.operation_type, 0) + 1
            by_priority[op.priority] = by_priority.get(op.priority, 0) + 1

        return {
            "queue_size": len(self._queue),
            "total_added": self._total_added,
            "total_processed": self._total_processed,
            "total_expired": self._total_expired,
            "by_type": by_type,
            "by_priority": by_priority,
            "success_rate": (
                self._total_processed / self._total_added * 100
                if self._total_added > 0
                else 0
            ),
        }

    def _track_metrics(self, action: str, operation: FailedOperation) -> None:
        """Обновить Prometheus метрики.

        Args:
            action: Тип действия (add, processed)
            operation: Операция
        """
        try:
            from src.utils.prometheus_metrics import (
                DLQ_OPERATIONS,
                DLQ_QUEUE_SIZE,
            )

            DLQ_OPERATIONS.labels(
                action=action,
                operation_type=operation.operation_type,
                priority=operation.priority,
            ).inc()

            DLQ_QUEUE_SIZE.set(len(self._queue))
        except ImportError:
            pass  # Prometheus not available

    @property
    def size(self) -> int:
        """Текущий размер очереди."""
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """Проверка на пустоту очереди."""
        return len(self._queue) == 0


class DeadLetterQueueProcessor:
    """Процессор для автоматической обработки DLQ.

    Запускает фоновую задачу для периодической обработки
    операций из Dead Letter Queue.
    """

    def __init__(
        self,
        dlq: DeadLetterQueue,
        process_interval: int = 300,  # 5 минут
        batch_size: int = 10,
    ) -> None:
        """Инициализация процессора.

        Args:
            dlq: Dead Letter Queue для обработки
            process_interval: Интервал обработки в секундах
            batch_size: Размер партии для обработки
        """
        self._dlq = dlq
        self._interval = process_interval
        self._batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None
        self._handlers: dict[str, Any] = {}

    def register_handler(
        self,
        operation_type: str,
        handler: Any,
    ) -> None:
        """Зарегистрировать обработчик для типа операции.

        Args:
            operation_type: Тип операции
            handler: Async функция-обработчик
        """
        self._handlers[operation_type] = handler
        logger.info(
            "dlq_handler_registered",
            operation_type=operation_type,
        )

    async def start(self) -> None:
        """Запустить процессор."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info(
            "dlq_processor_started",
            interval=self._interval,
            batch_size=self._batch_size,
        )

    async def stop(self) -> None:
        """Остановить процессор."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("dlq_processor_stopped")

    async def _process_loop(self) -> None:
        """Основной цикл обработки."""
        while self._running:
            try:
                await self._process_batch()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("dlq_process_loop_error", error=str(e))
                await asyncio.sleep(60)  # Подождать минуту при ошибке

    async def _process_batch(self) -> None:
        """Обработать партию операций."""
        # Сначала обрабатываем критические операции
        for priority in [
            OperationPriority.CRITICAL,
            OperationPriority.HIGH,
            OperationPriority.MEDIUM,
            OperationPriority.LOW,
        ]:
            batch = await self._dlq.get_batch(
                batch_size=self._batch_size,
                priority=priority,
            )

            for operation in batch:
                await self._process_operation(operation)

    async def _process_operation(self, operation: FailedOperation) -> None:
        """Обработать одну операцию.

        Args:
            operation: Операция для обработки
        """
        handler = self._handlers.get(operation.operation_type)

        if not handler:
            logger.warning(
                "dlq_no_handler_for_operation",
                operation_type=operation.operation_type,
            )
            await self._dlq.return_to_queue(operation)
            return

        try:
            await handler(operation.payload)
            await self._dlq.mark_processed(operation)
        except Exception as e:
            logger.warning(
                "dlq_operation_retry_failed",
                operation_type=operation.operation_type,
                error=str(e),
                retry_count=operation.retry_count,
            )
            operation.error = str(e)
            await self._dlq.return_to_queue(operation)


# Глобальный экземпляр для использования в приложении
_dlq_instance: DeadLetterQueue | None = None


def get_dead_letter_queue() -> DeadLetterQueue:
    """Получить глобальный экземпляр Dead Letter Queue.

    Returns:
        Экземпляр DeadLetterQueue
    """
    global _dlq_instance
    if _dlq_instance is None:
        _dlq_instance = DeadLetterQueue()
    return _dlq_instance


def set_dead_letter_queue(dlq: DeadLetterQueue) -> None:
    """Установить глобальный экземпляр Dead Letter Queue.

    Args:
        dlq: Экземпляр DeadLetterQueue
    """
    global _dlq_instance
    _dlq_instance = dlq


__all__ = [
    "DeadLetterQueue",
    "DeadLetterQueueProcessor",
    "FailedOperation",
    "OperationPriority",
    "OperationType",
    "get_dead_letter_queue",
    "set_dead_letter_queue",
]
