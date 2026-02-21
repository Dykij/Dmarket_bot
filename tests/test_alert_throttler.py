"""Тесты для Alert Throttler.

Тестирование функциональности:
- Throttling по cooldown
- Приоритизация алертов
- Группировка и дайджесты
- Статистика
"""

from datetime import UTC, datetime

import pytest

from src.utils.alert_throttler import (
    AlertCategory,
    AlertDigestScheduler,
    AlertPriority,
    AlertRecord,
    AlertThrottler,
    PendingAlert,
)


class TestAlertPriority:
    """Тесты для AlertPriority."""

    def test_priority_ordering(self):
        """Тест порядка приоритетов."""
        assert AlertPriority.LOW < AlertPriority.MEDIUM
        assert AlertPriority.MEDIUM < AlertPriority.HIGH
        assert AlertPriority.HIGH < AlertPriority.CRITICAL

    def test_priority_values(self):
        """Тест числовых значений."""
        assert AlertPriority.LOW == 1
        assert AlertPriority.CRITICAL == 4


class TestAlertRecord:
    """Тесты для AlertRecord."""

    def test_create_record(self):
        """Тест создания записи."""
        record = AlertRecord(
            category=AlertCategory.API_ERROR,
            priority=AlertPriority.HIGH,
            sent_at=datetime.now(UTC),
            message="API Error occurred",
        )

        assert record.category == AlertCategory.API_ERROR
        assert record.priority == AlertPriority.HIGH
        assert record.count == 1


class TestPendingAlert:
    """Тесты для PendingAlert."""

    def test_add_message(self):
        """Тест добавления сообщений."""
        alert = PendingAlert(
            category=AlertCategory.RATE_LIMIT,
            priority=AlertPriority.MEDIUM,
        )

        alert.add_message("Rate limit hit on /market")
        alert.add_message("Rate limit hit on /balance")

        assert alert.count == 2
        assert len(alert.messages) == 2

    def test_timestamps(self):
        """Тест обновления timestamps."""
        alert = PendingAlert(
            category=AlertCategory.RATE_LIMIT,
            priority=AlertPriority.MEDIUM,
        )
        first_at = alert.first_at

        alert.add_message("Message 1")
        alert.add_message("Message 2")

        assert alert.first_at == first_at
        assert alert.last_at >= first_at


class TestAlertThrottler:
    """Тесты для AlertThrottler."""

    @pytest.fixture
    def throttler(self):
        """Фикстура для создания throttler."""
        return AlertThrottler(
            cooldowns={
                AlertPriority.LOW: 60,
                AlertPriority.MEDIUM: 30,
                AlertPriority.HIGH: 10,
                AlertPriority.CRITICAL: 0,
            }
        )

    def test_should_send_first_time(self, throttler):
        """Тест первой отправки."""
        assert throttler.should_send(AlertCategory.API_ERROR, AlertPriority.HIGH) is True

    def test_should_send_after_cooldown(self, throttler):
        """Тест отправки после cooldown."""
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.HIGH)

        # Сразу после отправки - нельзя (cooldown = 10 секунд)
        assert throttler.should_send(AlertCategory.API_ERROR, AlertPriority.HIGH) is False

        # Для другой категории - можно (независимо)
        assert throttler.should_send(AlertCategory.TRADE_ERROR, AlertPriority.HIGH) is True

    def test_critical_always_sends(self, throttler):
        """Тест: критические алерты всегда отправляются."""
        # Отправляем несколько критических алертов
        for i in range(5):
            throttler.record_sent(AlertCategory.TRADE_ERROR, AlertPriority.CRITICAL)

            # Сразу можно отправить ещё
            assert throttler.should_send(
                AlertCategory.TRADE_ERROR,
                AlertPriority.CRITICAL,
            ) is True

    def test_record_suppressed(self, throttler):
        """Тест записи подавленных алертов."""
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.MEDIUM)
        throttler.record_suppressed(
            AlertCategory.API_ERROR,
            AlertPriority.MEDIUM,
            "Error 1",
        )
        throttler.record_suppressed(
            AlertCategory.API_ERROR,
            AlertPriority.MEDIUM,
            "Error 2",
        )

        stats = throttler.get_stats()
        assert stats["total_suppressed"] == 2
        assert AlertCategory.API_ERROR in stats["suppressed_by_category"]
        assert stats["suppressed_by_category"][AlertCategory.API_ERROR] == 2

    def test_different_categories_independent(self, throttler):
        """Тест: разные категории независимы."""
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.HIGH)

        # Другая категория - можно отправить
        assert throttler.should_send(AlertCategory.RATE_LIMIT, AlertPriority.HIGH) is True

    @pytest.mark.asyncio
    async def test_process_with_throttle(self, throttler):
        """Тест process_with_throttle."""
        sent_messages = []

        async def mock_send(msg):
            sent_messages.append(msg)

        # Первый раз - отправляется
        result1 = awAlgot throttler.process_with_throttle(
            AlertCategory.API_ERROR,
            AlertPriority.HIGH,
            "Error 1",
            mock_send,
        )
        assert result1 is True
        assert len(sent_messages) == 1

        # ВтоSwarm раз - подавляется
        result2 = awAlgot throttler.process_with_throttle(
            AlertCategory.API_ERROR,
            AlertPriority.HIGH,
            "Error 2",
            mock_send,
        )
        assert result2 is False
        assert len(sent_messages) == 1  # Не увеличилось

    def test_get_pending_digest(self, throttler):
        """Тест получения дайджестов."""
        # Создаём throttler с коротким интервалом дайджеста
        short_throttler = AlertThrottler(digest_interval=0)

        short_throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.MEDIUM)
        short_throttler.record_suppressed(
            AlertCategory.API_ERROR,
            AlertPriority.MEDIUM,
            "Error 1",
        )

        pending = short_throttler.get_pending_digest()
        assert len(pending) == 1
        assert pending[0].category == AlertCategory.API_ERROR

    def test_format_digest(self, throttler):
        """Тест форматирования дайджеста."""
        alert = PendingAlert(
            category=AlertCategory.RATE_LIMIT,
            priority=AlertPriority.MEDIUM,
        )
        alert.add_message("Rate limit on /market")
        alert.add_message("Rate limit on /balance")

        digest = throttler.format_digest([alert])

        assert "Alert Digest" in digest
        assert AlertCategory.RATE_LIMIT in digest
        assert "2 событий" in digest

    def test_clear_pending(self, throttler):
        """Тест очистки ожидающих."""
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.MEDIUM)
        throttler.record_suppressed(AlertCategory.API_ERROR, AlertPriority.MEDIUM, "E1")
        throttler.record_suppressed(AlertCategory.API_ERROR, AlertPriority.MEDIUM, "E2")

        count = throttler.clear_pending(AlertCategory.API_ERROR)

        assert count == 2
        assert throttler.get_stats()["pending_messages"] == 0

    def test_stats(self, throttler):
        """Тест статистики."""
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.HIGH)
        throttler.record_sent(AlertCategory.TRADE_SUCCESS, AlertPriority.LOW)
        throttler.record_suppressed(AlertCategory.API_ERROR, AlertPriority.HIGH, "E1")

        stats = throttler.get_stats()

        assert stats["total_sent"] == 2
        assert stats["total_suppressed"] == 1
        assert stats["suppression_rate"] > 0
        assert AlertCategory.API_ERROR in stats["categories"]

    def test_set_cooldown(self, throttler):
        """Тест изменения cooldown."""
        # По умолчанию HIGH = 10
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.HIGH)
        assert throttler.should_send(AlertCategory.API_ERROR, AlertPriority.HIGH) is False

        # Устанавливаем cooldown = 0
        throttler.set_cooldown(AlertPriority.HIGH, 0)

        # Теперь можно отправить
        assert throttler.should_send(AlertCategory.API_ERROR, AlertPriority.HIGH) is True


class TestAlertDigestScheduler:
    """Тесты для AlertDigestScheduler."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Тест запуска и остановки."""
        throttler = AlertThrottler()
        digests_sent = []

        async def mock_send(msg):
            digests_sent.append(msg)

        scheduler = AlertDigestScheduler(
            throttler=throttler,
            send_func=mock_send,
            check_interval=1,
        )

        awAlgot scheduler.start()
        assert scheduler._running is True

        awAlgot scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_sends_digest(self):
        """Тест отправки дайджеста."""
        # Создаём throttler с мгновенным дайджестом
        throttler = AlertThrottler(digest_interval=0)
        digests_sent = []

        async def mock_send(msg):
            digests_sent.append(msg)

        # Добавляем подавленные алерты
        throttler.record_sent(AlertCategory.API_ERROR, AlertPriority.MEDIUM)
        throttler.record_suppressed(AlertCategory.API_ERROR, AlertPriority.MEDIUM, "E1")
        throttler.record_suppressed(AlertCategory.API_ERROR, AlertPriority.MEDIUM, "E2")

        scheduler = AlertDigestScheduler(
            throttler=throttler,
            send_func=mock_send,
            check_interval=1,
        )

        # Проверяем вручную
        awAlgot scheduler._check_and_send_digests()

        assert len(digests_sent) == 1
        assert "Alert Digest" in digests_sent[0]
