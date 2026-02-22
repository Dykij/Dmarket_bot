"""Тесты для конфигурации логирования в тестах.

Этот модуль проверяет работу фикстур и утилит для управления логами.
"""

import logging
from unittest.mock import MagicMock

import pytest

from tests.conftest import LogAssertions, generate_test_item_data


class TestLoggingFixtures:
    """Тесты для фикстур управления логами."""

    def test_suppress_logs_fixture(
        self, suppress_logs: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Проверяет что фикстура suppress_logs подавляет логи."""
        logger = logging.getLogger("test_logger")
        logger.info("This should not appear")
        logger.warning("This too")

        # При CRITICAL уровне INFO и WARNING не должны появляться
        assert len(caplog.records) == 0

    def test_enable_debug_logs_fixture(
        self, enable_debug_logs: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Проверяет что фикстура enable_debug_logs показывает DEBUG логи."""
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("test_logger")
        logger.debug("Debug message")

        assert any("Debug message" in r.message for r in caplog.records)

    def test_log_capture_fixture(self, log_capture: pytest.LogCaptureFixture) -> None:
        """Проверяет работу фикстуры log_capture."""
        logger = logging.getLogger("test_logger")
        logger.info("Info message")
        logger.error("Error message")

        assert "Info message" in log_capture.text
        assert "Error message" in log_capture.text

    def test_mock_logger_fixture(self, mock_logger: MagicMock) -> None:
        """Проверяет что mock_logger имеет все необходимые методы."""
        mock_logger.info("test")
        mock_logger.debug("test")
        mock_logger.warning("test")
        mock_logger.error("test")
        mock_logger.critical("test")
        mock_logger.exception("test exception")

        assert mock_logger.info.called
        assert mock_logger.debug.called
        assert mock_logger.warning.called
        assert mock_logger.error.called
        assert mock_logger.critical.called
        assert mock_logger.exception.called


class TestLogAssertions:
    """Тесты для класса LogAssertions."""

    def test_assert_logged_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет успешную проверку наличия лога."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("test")
        logger.info("Expected message")

        # Не должно вызывать исключение
        LogAssertions.assert_logged(caplog, "Expected message")

    def test_assert_logged_with_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет фильтрацию по уровню."""
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("test")
        logger.info("Info message")
        logger.error("Error message")

        LogAssertions.assert_logged(caplog, "Error message", level="ERROR")
        LogAssertions.assert_logged(caplog, "Info message", level="INFO")

    def test_assert_logged_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет что assert_logged fail при отсутствии сообщения."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("test")
        logger.info("Different message")

        with pytest.raises(pytest.fail.Exception, match="not found"):
            LogAssertions.assert_logged(caplog, "Expected but missing")

    def test_assert_not_logged_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет успешную проверку отсутствия лога."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("test")
        logger.info("Safe message")

        # Не должно вызывать исключение
        LogAssertions.assert_not_logged(caplog, "Forbidden message")

    def test_assert_not_logged_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет что assert_not_logged fail при наличии сообщения."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("test")
        logger.info("Forbidden message")

        with pytest.raises(pytest.fail.Exception, match="Unexpected"):
            LogAssertions.assert_not_logged(caplog, "Forbidden message")

    def test_assert_error_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет shortcut для ошибок."""
        caplog.set_level(logging.ERROR)
        logger = logging.getLogger("test")
        logger.error("Something went wrong")

        LogAssertions.assert_error_logged(caplog, "went wrong")

    def test_get_log_messages(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет получение списка сообщений."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("test")
        logger.info("Message 1")
        logger.info("Message 2")
        logger.error("Error message")

        all_messages = LogAssertions.get_log_messages(caplog)
        assert len(all_messages) >= 3

        error_messages = LogAssertions.get_log_messages(caplog, level="ERROR")
        assert len(error_messages) == 1
        assert "Error message" in error_messages[0]


class TestDataGenerators:
    """Тесты для функций генерации тестовых данных."""

    def test_generate_test_item_data_defaults(self) -> None:
        """Проверяет генерацию данных предмета с дефолтными параметрами."""
        item = generate_test_item_data()

        assert item["title"] == "Test Item"
        assert item["price"]["USD"] == 1000  # 10.0 * 100
        assert item["gameId"] == "csgo"
        assert "itemId" in item
        assert "image" in item

    def test_generate_test_item_data_custom(self) -> None:
        """Проверяет генерацию данных предмета с кастомными параметрами."""
        item = generate_test_item_data(
            title="AK-47 | Redline",
            price_usd=25.50,
            game="dota2",
        )

        assert item["title"] == "AK-47 | Redline"
        assert item["price"]["USD"] == 2550  # 25.50 * 100
        assert item["gameId"] == "dota2"


class TestMockSentry:
    """Тесты для фикстуры mock_sentry."""

    def test_mock_sentry_capture_exception(self, mock_sentry: MagicMock) -> None:
        """Проверяет что mock_sentry перехватывает capture_exception."""
        import sentry_sdk

        try:
            raise ValueError("Test error")
        except ValueError as e:
            sentry_sdk.capture_exception(e)

        mock_sentry.capture_exception.assert_called_once()

    def test_mock_sentry_capture_message(self, mock_sentry: MagicMock) -> None:
        """Проверяет что mock_sentry перехватывает capture_message."""
        import sentry_sdk

        sentry_sdk.capture_message("Test message")

        mock_sentry.capture_message.assert_called_once_with("Test message")

    def test_mock_sentry_add_breadcrumb(self, mock_sentry: MagicMock) -> None:
        """Проверяет что mock_sentry перехватывает add_breadcrumb."""
        import sentry_sdk

        sentry_sdk.add_breadcrumb(message="Test breadcrumb", category="test")

        mock_sentry.add_breadcrumb.assert_called_once()


class TestLoggingMarkers:
    """Тесты для pytest маркеров логирования."""

    @pytest.mark.quiet_logs()
    def test_quiet_logs_marker(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет работу маркера quiet_logs."""
        logger = logging.getLogger("test")
        logger.info("Should not appear")

        # При quiet_logs уровень должен быть CRITICAL
        assert logging.getLogger().level >= logging.CRITICAL

    @pytest.mark.log_level("DEBUG")
    def test_log_level_marker(self, caplog: pytest.LogCaptureFixture) -> None:
        """Проверяет работу маркера log_level."""
        # Проверяем что уровень установлен корректно
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("test")
        logger.debug("Debug message")

        assert any("Debug message" in r.message for r in caplog.records)
