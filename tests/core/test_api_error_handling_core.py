"""Тесты для утилит обработки API ошибок.

Покрывают api_error_handling:
- Функцию handle_response
- Обработку различных статус-кодов
- Совместимость с exceptions модулем
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.api_error_handling import (
    APIError,
    AuthenticationError,
    ErrorCode,
    NetworkError,
    RateLimitError,
    ValidationError,
    handle_response,
)


class TestAPIErrorHandling:
    """Тесты обработки API ошибок."""

    @pytest.mark.asyncio()
    async def test_handle_response_success_200(self):
        """Тест обработки успешного ответа 200."""
        response = MagicMock()
        response.status = 200  # Используем status вместо status_code
        response.json = AsyncMock(return_value={"result": "success"})

        result = await handle_response(response)

        assert result == {"result": "success"}

    @pytest.mark.asyncio()
    async def test_handle_response_success_201(self):
        """Тест обработки успешного ответа 201."""
        response = MagicMock()
        response.status = 201
        response.json = AsyncMock(return_value={"created": True})

        result = await handle_response(response)

        assert result == {"created": True}

    @pytest.mark.asyncio()
    async def test_handle_response_error_400(self):
        """Тест обработки ошибки 400."""
        response = MagicMock()
        response.status = 400
        response.text = "Bad request"

        with pytest.raises(APIError):
            await handle_response(response)

    @pytest.mark.asyncio()
    async def test_handle_response_error_500(self):
        """Тест обработки ошибки 500."""
        response = MagicMock()
        response.status = 500
        response.text = "Internal server error"

        with pytest.raises(APIError):
            await handle_response(response)


class TestErrorCodeEnum:
    """Тесты перечисления кодов ошибок."""

    def test_error_code_values(self):
        """Тест значений кодов ошибок."""
        assert ErrorCode.UNKNOWN_ERROR.value == 1000
        assert ErrorCode.API_ERROR.value == 2000
        assert ErrorCode.VALIDATION_ERROR.value == 3000
        assert ErrorCode.AUTH_ERROR.value == 4000

    def test_error_code_enum_members(self):
        """Тест членов перечисления."""
        assert ErrorCode.UNKNOWN_ERROR in ErrorCode
        assert ErrorCode.API_ERROR in ErrorCode
        assert ErrorCode.NETWORK_ERROR in ErrorCode


class TestAPIErrorClasses:
    """Тесты классов ошибок API."""

    def test_api_error_creation(self):
        """Тест создания APIError."""
        error = APIError("Test error", status_code=404)

        assert isinstance(error, Exception)
        assert error.status_code == 404

    def test_authentication_error_creation(self):
        """Тест создания AuthenticationError."""
        error = AuthenticationError("Invalid token")

        assert isinstance(error, APIError)
        assert error.status_code == 401

    def test_rate_limit_error_creation(self):
        """Тест создания RateLimitError."""
        error = RateLimitError("Too many requests")

        assert isinstance(error, APIError)
        assert error.status_code == 429

    def test_validation_error_creation(self):
        """Тест создания ValidationError."""
        error = ValidationError("Invalid input")

        assert isinstance(error, Exception)

    def test_network_error_creation(self):
        """Тест создания NetworkError."""
        error = NetworkError("Connection failed")

        assert isinstance(error, Exception)


class TestErrorInheritance:
    """Тесты наследования ошибок."""

    def test_authentication_error_inherits_api_error(self):
        """Тест что AuthenticationError наследует APIError."""
        assert issubclass(AuthenticationError, APIError)

    def test_rate_limit_error_inherits_api_error(self):
        """Тест что RateLimitError наследует APIError."""
        assert issubclass(RateLimitError, APIError)

    def test_all_errors_inherit_exception(self):
        """Тест что все ошибки наследуют Exception."""
        assert issubclass(APIError, Exception)
        assert issubclass(ValidationError, Exception)
        assert issubclass(NetworkError, Exception)
