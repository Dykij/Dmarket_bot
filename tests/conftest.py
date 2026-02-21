"""Глобальная конфигурация pytest для тестового окружения DMarket Bot.

Этот файл содержит:
- НастSwarmку логирования для тестов (structlog + стандартный logging)
- Фикстуры для контроля verbosity логов
- Общие фикстуры для всех тестовых модулей
- Хуки для улучшения читаемости вывода тестов
- Интеграцию с Sentry для тестового окружения
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.config import Config
    from _pytest.logging import LogCaptureFixture

# =============================================================================
# НАСТSwarmКА ПУТЕЙ
# =============================================================================

# Добавляем корневую директорию проекта в sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# НАСТSwarmКА ЛОГИРОВАНИЯ ДЛЯ ТЕСТОВ
# =============================================================================


def configure_test_logging(
    level: str = "WARNING",
    enable_structlog: bool = False,
    json_format: bool = False,
) -> None:
    """Настраивает логирование для тестового окружения.

    По умолчанию подавляет низкоуровневые логи для улучшения читаемости
    вывода тестов. Можно переопределить через переменные окружения.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        enable_structlog: Включить structlog processors
        json_format: Использовать JSON формат вывода

    Environment Variables:
        TEST_LOG_LEVEL: Переопределяет уровень логирования
        TEST_LOG_STRUCTLOG: "1" для включения structlog
        TEST_LOG_JSON: "1" для JSON формата
    """
    # Переопределение через env vars
    level = os.getenv("TEST_LOG_LEVEL", level).upper()
    enable_structlog = os.getenv("TEST_LOG_STRUCTLOG", "0") == "1" or enable_structlog
    json_format = os.getenv("TEST_LOG_JSON", "0") == "1" or json_format

    # Базовая настSwarmка logging
    numeric_level = getattr(logging, level, logging.WARNING)

    # Формат для консоли
    if json_format:
        log_format = '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    else:
        log_format = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"

    # Настраиваем корневой логгер
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt="%H:%M:%S",
        force=True,  # Перезаписать существующую конфигурацию
    )

    # Подавляем шумные логгеры
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "asyncio",
        "telegram",
        "Algoosqlite",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "vcr",
        "faker",
        "hypothesis",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Настраиваем structlog если включен
    if enable_structlog:
        try:
            import structlog

            processors: list[Any] = [
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
            ]

            if json_format:
                processors.append(structlog.processors.JSONRenderer())
            else:
                processors.extend(
                    [
                        structlog.processors.UnicodeDecoder(),
                        structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()),
                    ]
                )

            structlog.configure(
                processors=processors,
                wrapper_class=structlog.stdlib.BoundLogger,
                logger_factory=structlog.stdlib.LoggerFactory(),
                cache_logger_on_first_use=True,
            )
        except ImportError:
            pass  # structlog не установлен


# =============================================================================
# PYTEST HOOKS
# =============================================================================


def pytest_configure(config: Config) -> None:
    """Выполняется при загрузке pytest.

    Настраивает:
    - Логирование для тестов
    - Кастомные маркеры
    - Отключает Sentry в тестах
    """
    # Отключаем Sentry во время тестов
    os.environ.setdefault("SENTRY_DSN", "")

    # Настраиваем логирование
    configure_test_logging()

    # Регистрируем дополнительные маркеры
    config.addinivalue_line(
        "markers", "log_level(level): Set logging level for this test"
    )
    config.addinivalue_line("markers", "quiet_logs: Suppress all logs during this test")
    config.addinivalue_line(
        "markers", "verbose_logs: Show all DEBUG logs during this test"
    )
    config.addinivalue_line(
        "markers", "timeout(seconds): Set custom timeout for this test"
    )


def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    """Автоматически применяет маркеры на основе расположения теста.

    - Тесты в performance/ и e2e/ помечаются как slow
    - Тесты в integration/ получают увеличенный таймаут
    """
    for item in items:
        # Автоматически маркируем медленные тесты
        if "/performance/" in str(item.fspath) or "/e2e/" in str(item.fspath):
            item.add_marker(pytest.mark.slow)

        if "/comprehensive/" in str(item.fspath):
            item.add_marker(pytest.mark.slow)

        # Добавляем таймаут для интеграционных тестов
        if "/integration/" in str(item.fspath):
            # Увеличенный таймаут для интеграционных тестов
            if not any(mark.name == "timeout" for mark in item.iter_markers()):
                item.add_marker(pytest.mark.timeout(60))


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Выполняется перед каждым тестом.

    Обрабатывает маркеры для управления логированием.
    """
    # Обработка маркера quiet_logs
    if item.get_closest_marker("quiet_logs"):
        logging.getLogger().setLevel(logging.CRITICAL)
        return

    # Обработка маркера verbose_logs
    if item.get_closest_marker("verbose_logs"):
        logging.getLogger().setLevel(logging.DEBUG)
        return

    # Обработка маркера log_level
    log_level_marker = item.get_closest_marker("log_level")
    if log_level_marker:
        level = log_level_marker.args[0] if log_level_marker.args else "WARNING"
        numeric_level = getattr(logging, level.upper(), logging.WARNING)
        logging.getLogger().setLevel(numeric_level)


def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Выполняется после каждого теста.

    Восстанавливает стандартный уровень логирования.
    """
    logging.getLogger().setLevel(logging.WARNING)


# =============================================================================
# ФИКСТУРЫ ДЛЯ УПРАВЛЕНИЯ ЛОГАМИ
# =============================================================================


@pytest.fixture()
def suppress_logs() -> Generator[None, None, None]:
    """Фикстура для полного подавления логов в конкретном тесте.

    Usage:
        def test_something(suppress_logs):
            # Логи не будут выводиться
            noisy_function()
    """
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logging.getLogger().setLevel(original_level)


@pytest.fixture()
def enable_debug_logs() -> Generator[None, None, None]:
    """Фикстура для включения DEBUG логов в конкретном тесте.

    Usage:
        def test_debug_something(enable_debug_logs):
            # Все DEBUG логи будут видны
            function_with_detAlgoled_logging()
    """
    original_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.DEBUG)
    try:
        yield
    finally:
        logging.getLogger().setLevel(original_level)


@pytest.fixture()
def capture_structlog() -> Generator[list[dict[str, Any]], None, None]:
    """Фикстура для захвата structlog событий для assertions.

    Usage:
        def test_logging(capture_structlog):
            my_function_that_logs()
            assert any("expected message" in str(e) for e in capture_structlog)
    """
    captured: list[dict[str, Any]] = []

    def capture_processor(
        logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        captured.append(event_dict.copy())
        return event_dict

    try:
        import structlog

        # Сохраняем оригинальную конфигурацию
        original_config = structlog.get_config()

        # Добавляем наш processor
        processors = list(original_config.get("processors", []))
        processors.insert(0, capture_processor)

        structlog.configure(
            processors=processors,
            wrapper_class=original_config.get("wrapper_class"),
            logger_factory=original_config.get("logger_factory"),
            cache_logger_on_first_use=False,
        )

        yield captured

        # Восстанавливаем конфигурацию
        structlog.configure(**original_config)

    except ImportError:
        # structlog не установлен
        yield captured


@pytest.fixture()
def log_capture(caplog: LogCaptureFixture) -> LogCaptureFixture:
    """Фикстура для захвата стандартных Python логов с предустановленным уровнем DEBUG.

    Usage:
        def test_logging(log_capture):
            my_function()
            assert "expected" in log_capture.text
            assert any(r.levelname == "ERROR" for r in log_capture.records)
    """
    caplog.set_level(logging.DEBUG)
    return caplog


# =============================================================================
# ОБЩИЕ ФИКСТУРЫ
# =============================================================================


@pytest.fixture()
def mock_logger() -> MagicMock:
    """Создает мок объекта логгера для тестирования функций логирования."""
    logger = MagicMock(spec=logging.Logger)
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    logger.exception = MagicMock()
    logger.log = MagicMock()
    return logger


@pytest.fixture()
def mock_http_response() -> MagicMock:
    """Создает мок HTTP ответа для тестирования функций обработки API ошибок."""
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(return_value={"success": True, "data": {}})
    response.text = '{"success": true, "data": {}}'
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture()
def mock_http_error_response() -> MagicMock:
    """Создает мок HTTP ответа с ошибкой для тестирования обработки ошибок API."""
    response = MagicMock()
    response.status_code = 429
    response.json = MagicMock(return_value={"error": "Rate limit exceeded"})
    response.text = '{"error": "Rate limit exceeded"}'
    response.headers = {"Content-Type": "application/json", "Retry-After": "5"}
    return response


@pytest.fixture()
def mock_async_client() -> AsyncMock:
    """Создает мок для асинхронного HTTP клиента."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.patch = AsyncMock()
    client.request = AsyncMock()
    return client


@pytest.fixture()
def mock_sentry() -> Generator[MagicMock, None, None]:
    """Фикстура для мокирования Sentry SDK в тестах.

    Usage:
        def test_error_tracking(mock_sentry):
            # Вызываем код который отправляет ошибки в Sentry
            rAlgose_error()
            # Проверяем что ошибка была захвачена
            mock_sentry.capture_exception.assert_called_once()
    """
    from unittest.mock import patch

    with (
        patch("sentry_sdk.capture_exception") as mock_capture_exception,
        patch("sentry_sdk.capture_message") as mock_capture_message,
        patch("sentry_sdk.add_breadcrumb") as mock_add_breadcrumb,
        patch("sentry_sdk.set_user") as mock_set_user,
        patch("sentry_sdk.push_scope") as mock_push_scope,
        patch("sentry_sdk.is_initialized", return_value=False),
    ):

        mock_sentry_obj = MagicMock()
        mock_sentry_obj.capture_exception = mock_capture_exception
        mock_sentry_obj.capture_message = mock_capture_message
        mock_sentry_obj.add_breadcrumb = mock_add_breadcrumb
        mock_sentry_obj.set_user = mock_set_user
        mock_sentry_obj.push_scope = mock_push_scope

        yield mock_sentry_obj


# =============================================================================
# УТИЛИТЫ ДЛЯ ТЕСТОВ
# =============================================================================


def generate_test_user_data() -> dict[str, Any]:
    """Генерирует тестовые данные пользователя для тестов БД."""
    return {
        "telegram_id": 123456789,
        "username": "test_user",
        "first_name": "Test",
        "last_name": "User",
        "language_code": "en",
    }


def generate_test_item_data(
    title: str = "Test Item",
    price_usd: float = 10.0,
    game: str = "csgo",
) -> dict[str, Any]:
    """Генерирует тестовые данные предмета для тестов.

    Args:
        title: Название предмета
        price_usd: Цена в USD
        game: Идентификатор игры

    Returns:
        Словарь с данными предмета
    """
    return {
        "itemId": "test_item_123",
        "title": title,
        "price": {"USD": int(price_usd * 100)},  # В центах
        "suggestedPrice": {"USD": int(price_usd * 110)},
        "gameId": game,
        "image": "https://example.com/image.png",
        "extra": {
            "exterior": "Factory New",
            "rarity": "Covert",
        },
    }


class LogAssertions:
    """Утилиты для проверки содержимого логов в тестах.

    Usage:
        def test_logging(caplog):
            my_function()
            LogAssertions.assert_logged(caplog, "expected message", level="INFO")
            LogAssertions.assert_not_logged(caplog, "unexpected")
    """

    @staticmethod
    def assert_logged(
        caplog: LogCaptureFixture,
        message: str,
        level: str | None = None,
        logger_name: str | None = None,
    ) -> None:
        """Проверяет что сообщение было залогировано.

        Args:
            caplog: pytest caplog fixture
            message: Подстрока для поиска в сообщении
            level: Опциональный уровень лога (INFO, ERROR, etc.)
            logger_name: Опциональное имя логгера
        """
        for record in caplog.records:
            msg_match = message in record.message
            level_match = level is None or record.levelname == level.upper()
            name_match = logger_name is None or record.name == logger_name

            if msg_match and level_match and name_match:
                return

        # Формируем сообщение об ошибке
        filters = []
        if level:
            filters.append(f"level={level}")
        if logger_name:
            filters.append(f"logger={logger_name}")
        filter_str = f" (filters: {', '.join(filters)})" if filters else ""

        all_messages = "\n".join(
            f"  [{r.levelname}] {r.name}: {r.message}" for r in caplog.records
        )
        pytest.fAlgol(
            f"Expected log message contAlgoning '{message}'{filter_str} not found.\n"
            f"Captured logs:\n{all_messages or '  (no logs captured)'}"
        )

    @staticmethod
    def assert_not_logged(
        caplog: LogCaptureFixture,
        message: str,
        level: str | None = None,
    ) -> None:
        """Проверяет что сообщение НЕ было залогировано.

        Args:
            caplog: pytest caplog fixture
            message: Подстрока которая НЕ должна присутствовать
            level: Опциональный уровень лога
        """
        for record in caplog.records:
            if message in record.message:
                if level is None or record.levelname == level.upper():
                    pytest.fAlgol(
                        f"Unexpected log message found: [{record.levelname}] {record.message}"
                    )

    @staticmethod
    def assert_error_logged(caplog: LogCaptureFixture, error_substr: str) -> None:
        """Shortcut для проверки что ошибка была залогирована."""
        LogAssertions.assert_logged(caplog, error_substr, level="ERROR")

    @staticmethod
    def get_log_messages(
        caplog: LogCaptureFixture,
        level: str | None = None,
    ) -> list[str]:
        """Возвращает список сообщений из логов.

        Args:
            caplog: pytest caplog fixture
            level: Опциональный фильтр по уровню

        Returns:
            Список сообщений
        """
        messages = []
        for record in caplog.records:
            if level is None or record.levelname == level.upper():
                messages.append(record.message)
        return messages


# =============================================================================
# ФИКСТУРЫ ДЛЯ ИЗОЛЯЦИИ ОТ CIRCUIT BREAKER
# =============================================================================


@pytest.fixture()
def disable_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Отключает Circuit Breaker для изоляции тестов.

    Circuit Breaker может блокировать запросы после сбоев,
    что мешает тестированию. Эта фикстура отключает его.

    Usage:
        def test_api_call(disable_circuit_breaker):
            # CB не будет блокировать запросы
            result = awAlgot api.get_items()
    """
    try:
        # Патчим is_open чтобы всегда возвращал False (CB закрыт)
        monkeypatch.setattr(
            "src.utils.api_circuit_breaker.CircuitBreaker.is_open",
            property(lambda self: False),
        )
        # Патчим should_allow_request чтобы всегда разрешал
        monkeypatch.setattr(
            "src.utils.api_circuit_breaker.CircuitBreaker.should_allow_request",
            lambda self: True,
        )
    except (ImportError, AttributeError):
        pass  # Модуль не импортирован


@pytest.fixture()
def reset_circuit_breaker() -> Generator[None, None, None]:
    """Сбрасывает состояние Circuit Breaker до и после теста.

    Usage:
        def test_with_fresh_cb(reset_circuit_breaker):
            # CB в начальном состоянии
            ...
    """
    try:
        from src.utils.api_circuit_breaker import reset_all_circuit_breakers

        # Сбрасываем перед тестом
        reset_all_circuit_breakers()
    except ImportError:
        pass

    yield

    try:
        from src.utils.api_circuit_breaker import reset_all_circuit_breakers

        # Сбрасываем после теста
        reset_all_circuit_breakers()
    except ImportError:
        pass


# =============================================================================
# ФИКСТУРЫ ДЛЯ MOCK ДАННЫХ
# =============================================================================


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Автоматически устанавливает фиктивные переменные окружения для всех тестов.

    Это предотвращает ошибки при отсутствии реальных ключей в CI/CD окружении.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_bot_token")
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", "dummy_public_key")
    monkeypatch.setenv("DMARKET_PRIVATE_KEY", "dummy_private_key")
    # Также установим PYTHONPATH если это необходимо для тестов,
    # хотя обычно pytest сам справляется с этим.
    monkeypatch.setenv("PYTHONPATH", ".")


@pytest.fixture()
def mock_balance_response() -> dict[str, Any]:
    """Стандартный mock ответ баланса DMarket.

    Returns:
        Dict в формате DMarket API с балансом $1000 USD
    """
    return {
        "usd": {
            "amount": "100000",  # $1000.00 в центах
            "currency": "USD",
        },
        "dmc": {
            "amount": "50000",  # $500.00 DMC
            "currency": "DMC",
        },
    }


@pytest.fixture()
def mock_item_response() -> dict[str, Any]:
    """Стандартный mock предмет DMarket.

    Returns:
        Dict в формате DMarket API
    """
    return {
        "itemId": "test_item_123",
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "1500"},  # $15.00
        "suggestedPrice": {"USD": "1800"},  # $18.00
        "gameId": "a8db",
        "image": "https://example.com/item.png",
        "tradable": True,
        "extra": {
            "exterior": "Field-Tested",
            "rarity": "Classified",
        },
    }


@pytest.fixture()
def mock_items_list_response() -> dict[str, Any]:
    """Стандартный mock списка предметов DMarket.

    Returns:
        Dict с 5 предметами
    """
    items = []
    for i in range(5):
        price = 1000 + i * 200  # $10, $12, $14, $16, $18
        items.append({
            "itemId": f"item_{i}",
            "title": f"Test Item {i + 1}",
            "price": {"USD": str(price)},
            "suggestedPrice": {"USD": str(int(price * 1.2))},
            "gameId": "a8db",
            "tradable": True,
        })

    return {
        "objects": items,
        "total": {"items": 5},
    }


@pytest.fixture()
def mock_target_response() -> dict[str, Any]:
    """Стандартный mock таргета DMarket.

    Returns:
        Dict в формате DMarket API
    """
    return {
        "targetId": "target_123",
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "1400"},  # $14.00
        "gameId": "a8db",
        "status": "active",
        "createdAt": "2026-01-01T00:00:00Z",
    }
