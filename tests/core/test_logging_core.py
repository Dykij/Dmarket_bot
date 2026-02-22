"""Расширенные тесты для утилит логирования.

Покрывают logging_utils:
- JSONFormatter
- ColoredFormatter
- Функции setup_logging
- Структурированное логирование
"""

import json
import logging

from src.utils.canonical_logging import ColoredFormatter, JSONFormatter


class TestJSONFormatter:
    """Тесты JSON форматера логов."""

    def test_json_formatter_basic_message(self):
        """Тест форматирования базового сообщения."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"

    def test_json_formatter_with_extra_fields(self):
        """Тест добавления дополнительных полей."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=20,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.user_id = 12345
        record.request_id = "abc-123"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["user_id"] == 12345
        assert log_data["request_id"] == "abc-123"

    def test_json_formatter_with_exception(self):
        """Тест форматирования с исключением."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=30,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]

    def test_json_formatter_includes_metadata(self):
        """Тест включения метаданных."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=40,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert "timestamp" in log_data
        assert "module" in log_data
        assert "function" in log_data
        assert "line" in log_data


class TestColoredFormatter:
    """Тесты цветного форматера логов."""

    def test_colored_formatter_debug_level(self):
        """Тест форматирования DEBUG уровня."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=10,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Проверяем что результат содержит сообщение
        assert "Debug message" in result

    def test_colored_formatter_info_level(self):
        """Тест форматирования INFO уровня."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=20,
            msg="Info message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Info message" in result

    def test_colored_formatter_warning_level(self):
        """Тест форматирования WARNING уровня."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=30,
            msg="Warning message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Warning message" in result

    def test_colored_formatter_error_level(self):
        """Тест форматирования ERROR уровня."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=40,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Error message" in result

    def test_colored_formatter_critical_level(self):
        """Тест форматирования CRITICAL уровня."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.CRITICAL,
            pathname="test.py",
            lineno=50,
            msg="Critical message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Critical message" in result


class TestLoggingUtilsIntegration:
    """Интеграционные тесты утилит логирования."""

    def test_formatters_work_together(self):
        """Тест совместной работы форматеров."""
        json_formatter = JSONFormatter()
        colored_formatter = ColoredFormatter("%(levelname)s - %(message)s")

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        json_result = json_formatter.format(record)
        colored_result = colored_formatter.format(record)

        # Оба форматера должны работать
        assert json_result is not None
        assert colored_result is not None

        # JSON должен быть валидным
        json.loads(json_result)
