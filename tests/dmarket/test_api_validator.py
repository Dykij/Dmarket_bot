"""Unit tests for src/dmarket/api_validator.py.

Tests for API validation utilities including:
- send_api_change_notification function
- validate_response decorator
- validate_and_log function
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ValidationError


class TestSendApiChangeNotification:
    """Tests for send_api_change_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_with_notifier(self):
        """Test that notification is sent when notifier is provided."""
        from src.dmarket.api_validator import send_api_change_notification

        # Create a mock validation error
        class TestModel(BaseModel):
            field1: str
            field2: int

        try:
            TestModel(field1=123, field2="invalid")
        except ValidationError as e:
            validation_error = e

        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock()

        await send_api_change_notification(
            endpoint="/test/endpoint",
            validation_error=validation_error,
            response_data={"field1": 123, "field2": "invalid"},
            notifier=mock_notifier,
        )

        mock_notifier.send_message.assert_called_once()
        call_args = mock_notifier.send_message.call_args
        assert "КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ DMarket API" in call_args.kwargs["message"]
        assert call_args.kwargs["priority"] == "critical"
        assert call_args.kwargs["category"] == "system"

    @pytest.mark.asyncio()
    async def test_logs_critical_without_notifier(self):
        """Test that critical log is written when no notifier is provided."""
        from src.dmarket.api_validator import send_api_change_notification

        class TestModel(BaseModel):
            field1: str

        try:
            TestModel(field1=123)
        except ValidationError as e:
            validation_error = e

        with patch("src.dmarket.api_validator.logger") as mock_logger:
            await send_api_change_notification(
                endpoint="/test/endpoint",
                validation_error=validation_error,
                response_data={"field1": 123},
                notifier=None,
            )

            mock_logger.critical.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handles_notifier_exception(self):
        """Test that exceptions from notifier are handled gracefully."""
        from src.dmarket.api_validator import send_api_change_notification

        class TestModel(BaseModel):
            field1: str

        try:
            TestModel(field1=123)
        except ValidationError as e:
            validation_error = e

        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise exception
        await send_api_change_notification(
            endpoint="/test/endpoint",
            validation_error=validation_error,
            response_data={"field1": 123},
            notifier=mock_notifier,
        )

    @pytest.mark.asyncio()
    async def test_formats_multiple_errors(self):
        """Test formatting when there are multiple validation errors."""
        from src.dmarket.api_validator import send_api_change_notification

        class TestModel(BaseModel):
            field1: str
            field2: int
            field3: bool
            field4: float

        try:
            TestModel(
                field1=123, field2="invalid", field3="not_bool", field4="not_float"
            )
        except ValidationError as e:
            validation_error = e

        mock_notifier = AsyncMock()
        mock_notifier.send_message = AsyncMock()

        await send_api_change_notification(
            endpoint="/test/endpoint",
            validation_error=validation_error,
            response_data={"field1": 123},
            notifier=mock_notifier,
        )

        # Should show first 3 errors only
        call_args = mock_notifier.send_message.call_args
        message = call_args.kwargs["message"]
        assert "Первые ошибки:" in message


class TestValidateResponseDecorator:
    """Tests for validate_response decorator."""

    @pytest.mark.asyncio()
    async def test_passes_valid_response_through(self):
        """Test that valid responses pass through successfully."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str
            value: int

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"status": "ok", "value": 42}

        result = await test_func()
        assert result == {"status": "ok", "value": 42}

    @pytest.mark.asyncio()
    async def test_returns_error_response_without_validation(self):
        """Test that error responses are returned without validation."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str
            value: int

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"error": "Something went wrong"}

        result = await test_func()
        assert result == {"error": "Something went wrong"}

    @pytest.mark.asyncio()
    async def test_returns_unvalidated_data_on_validation_error(self):
        """Test that unvalidated data is returned when validation fails."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str
            value: int

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"status": 123, "value": "invalid"}  # Invalid types

        with patch(
            "src.dmarket.api_validator.send_api_change_notification",
            new_callable=AsyncMock,
        ):
            result = await test_func()
            # Should return original data for backward compatibility
            assert result == {"status": 123, "value": "invalid"}

    @pytest.mark.asyncio()
    async def test_logs_validation_success(self):
        """Test that successful validation is logged."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"status": "ok"}

        with patch("src.dmarket.api_validator.logger") as mock_logger:
            await test_func()
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio()
    async def test_gets_notifier_from_instance(self):
        """Test that notifier is obtained from instance if available."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str
            value: int

        class TestClass:
            def __init__(self):
                self.notifier = AsyncMock()
                self.notifier.send_message = AsyncMock()

            @validate_response(TestModel, endpoint="/test")
            async def test_method(self) -> dict[str, Any]:
                return {"status": 123, "value": "invalid"}

        obj = TestClass()
        with patch(
            "src.dmarket.api_validator.send_api_change_notification",
            new_callable=AsyncMock,
        ) as mock_notify:
            await obj.test_method()
            # Should have been called with the notifier from instance
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args.kwargs["notifier"] is obj.notifier

    @pytest.mark.asyncio()
    async def test_handles_notification_failure(self):
        """Test that notification failures don't break the function."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str
            value: int

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"status": 123, "value": "invalid"}

        with patch(
            "src.dmarket.api_validator.send_api_change_notification",
            new_callable=AsyncMock,
            side_effect=Exception("Notification error"),
        ):
            # Should not raise, should return data anyway
            result = await test_func()
            assert result == {"status": 123, "value": "invalid"}


class TestValidateAndLog:
    """Tests for validate_and_log function."""

    def test_returns_validated_model_on_success(self):
        """Test that validated model is returned on success."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            status: str
            value: int

        result = validate_and_log(
            data={"status": "ok", "value": 42},
            schema=TestModel,
            endpoint="/test",
        )

        assert isinstance(result, TestModel)
        assert result.status == "ok"
        assert result.value == 42

    def test_returns_original_data_on_validation_error(self):
        """Test that original data is returned when validation fails."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            status: str
            value: int

        result = validate_and_log(
            data={"status": 123, "value": "invalid"},
            schema=TestModel,
            endpoint="/test",
        )

        # Should return original dict, not model
        assert isinstance(result, dict)
        assert result == {"status": 123, "value": "invalid"}

    def test_logs_success_on_valid_data(self):
        """Test that success is logged for valid data."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            status: str

        with patch("src.dmarket.api_validator.logger") as mock_logger:
            validate_and_log(
                data={"status": "ok"},
                schema=TestModel,
                endpoint="/test",
            )
            mock_logger.debug.assert_called()

    def test_logs_warning_on_validation_error(self):
        """Test that warning is logged when validation fails."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            status: str

        with patch("src.dmarket.api_validator.logger") as mock_logger:
            validate_and_log(
                data={"status": 123},
                schema=TestModel,
                endpoint="/test",
            )
            mock_logger.warning.assert_called()

    def test_truncates_long_data_in_log(self):
        """Test that long data is truncated in log messages."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            status: str

        long_data = {"status": "x" * 1000}

        with patch("src.dmarket.api_validator.logger") as mock_logger:
            validate_and_log(
                data=long_data,
                schema=TestModel,
                endpoint="/test",
            )
            # The log should be called, data sample should be truncated
            mock_logger.debug.assert_called()


class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    @pytest.mark.asyncio()
    async def test_handles_empty_response(self):
        """Test handling of empty response."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str | None = None

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {}

        result = await test_func()
        assert result == {}

    @pytest.mark.asyncio()
    async def test_handles_none_response(self):
        """Test handling of None response fields."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str | None = None

        @validate_response(TestModel, endpoint="/test")
        async def test_func() -> dict[str, Any]:
            return {"status": None}

        result = await test_func()
        assert result == {"status": None}

    def test_validate_and_log_with_nested_model(self):
        """Test validation with nested Pydantic models."""
        from src.dmarket.api_validator import validate_and_log

        class NestedModel(BaseModel):
            value: int

        class TestModel(BaseModel):
            nested: NestedModel
            name: str

        result = validate_and_log(
            data={"nested": {"value": 42}, "name": "test"},
            schema=TestModel,
            endpoint="/test",
        )

        assert isinstance(result, TestModel)
        assert result.nested.value == 42

    def test_validate_and_log_with_list_field(self):
        """Test validation with list fields."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            items: list[str]

        result = validate_and_log(
            data={"items": ["a", "b", "c"]},
            schema=TestModel,
            endpoint="/test",
        )

        assert isinstance(result, TestModel)
        assert result.items == ["a", "b", "c"]

    def test_validate_and_log_with_optional_fields(self):
        """Test validation with optional fields."""
        from src.dmarket.api_validator import validate_and_log

        class TestModel(BaseModel):
            required: str
            optional: str | None = None

        result = validate_and_log(
            data={"required": "value"},
            schema=TestModel,
            endpoint="/test",
        )

        assert isinstance(result, TestModel)
        assert result.required == "value"
        assert result.optional is None


class TestDecoratorPreservesFunction:
    """Tests that decorator preserves function metadata."""

    @pytest.mark.asyncio()
    async def test_preserves_function_name(self):
        """Test that decorated function preserves its name."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str

        @validate_response(TestModel, endpoint="/test")
        async def my_special_function() -> dict[str, Any]:
            """My docstring."""
            return {"status": "ok"}

        assert my_special_function.__name__ == "my_special_function"

    @pytest.mark.asyncio()
    async def test_preserves_function_docstring(self):
        """Test that decorated function preserves its docstring."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str

        @validate_response(TestModel, endpoint="/test")
        async def my_special_function() -> dict[str, Any]:
            """My docstring."""
            return {"status": "ok"}

        assert my_special_function.__doc__ == "My docstring."

    @pytest.mark.asyncio()
    async def test_passes_arguments_correctly(self):
        """Test that decorator passes arguments to wrapped function."""
        from src.dmarket.api_validator import validate_response

        class TestModel(BaseModel):
            status: str

        @validate_response(TestModel, endpoint="/test")
        async def my_func(
            arg1: str, arg2: int, *, kwarg1: str = "default"
        ) -> dict[str, Any]:
            return {"status": f"{arg1}-{arg2}-{kwarg1}"}

        result = await my_func("hello", 42, kwarg1="world")
        assert result == {"status": "hello-42-world"}
