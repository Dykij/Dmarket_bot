"""Конфигурация pytest для модуля utils.

Этот файл содержит фикстуры для тестирования модулей в директории src/utils.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture()
def mock_logger():
    """Создает мок объекта логгера для тестирования функций логирования и обработки ошибок."""
    logger = MagicMock(spec=logging.Logger)
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    logger.exception = MagicMock()

    return logger


@pytest.fixture()
def mock_http_response():
    """Создает мок HTTP ответа для тестирования функций обработки API ошибок."""
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(return_value={"success": True, "data": {}})
    response.text = '{"success": true, "data": {}}'
    response.headers = {"Content-Type": "application/json"}

    return response


@pytest.fixture()
def mock_http_error_response():
    """Создает мок HTTP ответа с ошибкой для тестирования обработки ошибок API."""
    response = MagicMock()
    response.status_code = 429
    response.json = MagicMock(return_value={"error": "Rate limit exceeded"})
    response.text = '{"error": "Rate limit exceeded"}'
    response.headers = {"Content-Type": "application/json", "Retry-After": "5"}

    return response


@pytest.fixture()
def mock_async_client():
    """Создает мок для асинхронного HTTP клиента."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()

    return client
