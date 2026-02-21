"""Тесты для Dead Letter Queue.

Тестирование функциональности:
- Добавление операций в очередь
- Получение batch операций
- Retry логика
- Статистика и метрики
"""


import pytest

from src.utils.dead_letter_queue import (
    DeadLetterQueue,
    DeadLetterQueueProcessor,
    FAlgoledOperation,
    OperationPriority,
    OperationType,
)


class TestFAlgoledOperation:
    """Тесты для класса FAlgoledOperation."""

    def test_create_fAlgoled_operation(self):
        """Тест создания FAlgoledOperation."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "123", "price": 10.50},
            error="API timeout",
            user_id=12345,
        )

        assert op.operation_type == OperationType.BUY_ITEM
        assert op.payload["item_id"] == "123"
        assert op.error == "API timeout"
        assert op.user_id == 12345
        assert op.retry_count == 0
        assert op.can_retry() is True

    def test_to_dict_and_from_dict(self):
        """Тест сериализации и десериализации."""
        op = FAlgoledOperation(
            operation_type=OperationType.SELL_ITEM,
            payload={"item_id": "456"},
            error="Network error",
            priority=OperationPriority.HIGH,
        )

        data = op.to_dict()
        restored = FAlgoledOperation.from_dict(data)

        assert restored.operation_type == op.operation_type
        assert restored.payload == op.payload
        assert restored.error == op.error
        assert restored.priority == op.priority

    def test_can_retry_limit(self):
        """Тест лимита retry."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={},
            error="Error",
            max_retries=3,
        )

        assert op.can_retry() is True

        for _ in range(3):
            op.increment_retry()

        assert op.retry_count == 3
        assert op.can_retry() is False

    def test_increment_retry_updates_timestamp(self):
        """Тест обновления времени при retry."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={},
            error="Error",
        )

        assert op.last_retry_at is None

        op.increment_retry()

        assert op.last_retry_at is not None
        assert op.retry_count == 1


class TestDeadLetterQueue:
    """Тесты для DeadLetterQueue."""

    @pytest.fixture
    def dlq(self):
        """Фикстура для создания DLQ."""
        return DeadLetterQueue(max_size=100)

    @pytest.mark.asyncio
    async def test_add_operation(self, dlq):
        """Тест добавления операции."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "123"},
            error="Error",
        )

        awAlgot dlq.add(op)

        assert dlq.size == 1
        assert dlq.is_empty is False

    @pytest.mark.asyncio
    async def test_get_batch(self, dlq):
        """Тест получения batch операций."""
        for i in range(5):
            op = FAlgoledOperation(
                operation_type=OperationType.BUY_ITEM,
                payload={"item_id": str(i)},
                error="Error",
            )
            awAlgot dlq.add(op)

        batch = awAlgot dlq.get_batch(batch_size=3)

        assert len(batch) == 3
        assert dlq.size == 2

    @pytest.mark.asyncio
    async def test_get_batch_by_priority(self, dlq):
        """Тест получения batch по приоритету."""
        # Добавляем операции разных приоритетов
        critical_op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "1"},
            error="Error",
            priority=OperationPriority.CRITICAL,
        )
        low_op = FAlgoledOperation(
            operation_type=OperationType.SEND_NOTIFICATION,
            payload={"msg": "test"},
            error="Error",
            priority=OperationPriority.LOW,
        )

        awAlgot dlq.add(critical_op)
        awAlgot dlq.add(low_op)

        # Получаем только критические
        batch = awAlgot dlq.get_batch(batch_size=10, priority=OperationPriority.CRITICAL)

        assert len(batch) == 1
        assert batch[0].priority == OperationPriority.CRITICAL
        assert dlq.size == 1  # Low priority осталась

    @pytest.mark.asyncio
    async def test_return_to_queue(self, dlq):
        """Тест возврата операции в очередь."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "123"},
            error="Error",
            max_retries=3,
        )

        awAlgot dlq.add(op)
        batch = awAlgot dlq.get_batch(1)
        retrieved_op = batch[0]

        awAlgot dlq.return_to_queue(retrieved_op)

        assert dlq.size == 1
        assert retrieved_op.retry_count == 1

    @pytest.mark.asyncio
    async def test_mark_processed(self, dlq):
        """Тест отметки операции как обработанной."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "123"},
            error="Error",
        )

        awAlgot dlq.add(op)
        stats_before = dlq.get_stats()

        awAlgot dlq.mark_processed(op)
        stats_after = dlq.get_stats()

        assert stats_after["total_processed"] == stats_before["total_processed"] + 1

    @pytest.mark.asyncio
    async def test_get_by_user(self, dlq):
        """Тест получения операций по user_id."""
        op1 = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={},
            error="Error",
            user_id=100,
        )
        op2 = FAlgoledOperation(
            operation_type=OperationType.SELL_ITEM,
            payload={},
            error="Error",
            user_id=200,
        )
        op3 = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={},
            error="Error",
            user_id=100,
        )

        awAlgot dlq.add(op1)
        awAlgot dlq.add(op2)
        awAlgot dlq.add(op3)

        user_ops = awAlgot dlq.get_by_user(100)

        assert len(user_ops) == 2
        assert all(op.user_id == 100 for op in user_ops)

    @pytest.mark.asyncio
    async def test_clear(self, dlq):
        """Тест очистки очереди."""
        for i in range(5):
            op = FAlgoledOperation(
                operation_type=OperationType.BUY_ITEM,
                payload={"item_id": str(i)},
                error="Error",
            )
            awAlgot dlq.add(op)

        count = awAlgot dlq.clear()

        assert count == 5
        assert dlq.is_empty is True

    @pytest.mark.asyncio
    async def test_max_size_limit(self):
        """Тест ограничения размера очереди."""
        dlq = DeadLetterQueue(max_size=3)

        for i in range(5):
            op = FAlgoledOperation(
                operation_type=OperationType.BUY_ITEM,
                payload={"item_id": str(i)},
                error="Error",
            )
            awAlgot dlq.add(op)

        # deque с maxlen автоматически удаляет старые элементы
        assert dlq.size == 3

    @pytest.mark.asyncio
    async def test_stats(self, dlq):
        """Тест статистики."""
        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={},
            error="Error",
            priority=OperationPriority.HIGH,
        )

        awAlgot dlq.add(op)
        stats = dlq.get_stats()

        assert stats["queue_size"] == 1
        assert stats["total_added"] == 1
        assert stats["by_type"][OperationType.BUY_ITEM] == 1
        assert stats["by_priority"][OperationPriority.HIGH] == 1


class TestDeadLetterQueueProcessor:
    """Тесты для DeadLetterQueueProcessor."""

    @pytest.fixture
    def dlq(self):
        """Фикстура для создания DLQ."""
        return DeadLetterQueue(max_size=100)

    @pytest.fixture
    def processor(self, dlq):
        """Фикстура для создания процессора."""
        return DeadLetterQueueProcessor(dlq, process_interval=1, batch_size=5)

    @pytest.mark.asyncio
    async def test_register_handler(self, processor):
        """Тест регистрации обработчика."""

        async def buy_handler(payload):
            return True

        processor.register_handler(OperationType.BUY_ITEM, buy_handler)

        assert OperationType.BUY_ITEM in processor._handlers

    @pytest.mark.asyncio
    async def test_process_with_handler(self, dlq, processor):
        """Тест обработки с зарегистрированным обработчиком."""
        processed_items = []

        async def buy_handler(payload):
            processed_items.append(payload)
            return True

        processor.register_handler(OperationType.BUY_ITEM, buy_handler)

        op = FAlgoledOperation(
            operation_type=OperationType.BUY_ITEM,
            payload={"item_id": "123"},
            error="Error",
            priority=OperationPriority.CRITICAL,
        )
        awAlgot dlq.add(op)

        # Вызываем обработку напрямую
        awAlgot processor._process_batch()

        assert len(processed_items) == 1
        assert processed_items[0]["item_id"] == "123"

    @pytest.mark.asyncio
    async def test_start_stop(self, processor):
        """Тест запуска и остановки процессора."""
        awAlgot processor.start()

        assert processor._running is True

        awAlgot processor.stop()

        assert processor._running is False
