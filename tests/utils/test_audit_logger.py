"""Тесты для audit_logger.py"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.utils.audit_logger import AuditEventType, AuditLog, AuditLogger, AuditSeverity


class TestAuditLogger:
    """Тесты для AuditLogger."""

    @pytest.fixture()
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture()
    def audit_logger(self, mock_session):
        """Create audit logger."""
        return AuditLogger(mock_session)

    @pytest.mark.asyncio()
    async def test_log_basic(self, audit_logger, mock_session):
        """Тест базового логирования."""
        result = await audit_logger.log(
            event_type=AuditEventType.USER_LOGIN,
            action="User logged in",
            user_id=12345,
            username="test_user",
        )

        assert isinstance(result, AuditLog)
        assert result.event_type == "user_login"
        assert result.user_id == 12345
        assert result.username == "test_user"
        assert result.success == "true"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_log_user_action(self, audit_logger, mock_session):
        """Тест логирования действия пользователя."""
        result = await audit_logger.log_user_action(
            user_id=12345,
            action="Created target",
            event_type=AuditEventType.TARGET_CREATE,
            details={"item_name": "AK-47", "price": 10.50},
        )

        assert result.event_type == "target_create"
        assert result.details == {"item_name": "AK-47", "price": 10.50}
        assert result.severity == AuditSeverity.INFO.value

    @pytest.mark.asyncio()
    async def test_log_security_event(self, audit_logger, mock_session):
        """Тест логирования события безопасности."""
        result = await audit_logger.log_security_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            action="Rate limit exceeded",
            user_id=12345,
            details={"requests": 100, "limit": 30},
            severity=AuditSeverity.WARNING,
        )

        assert result.event_type == "rate_limit_exceeded"
        assert result.severity == AuditSeverity.WARNING.value
        assert result.success == "false"

    @pytest.mark.asyncio()
    async def test_log_system_event(self, audit_logger, mock_session):
        """Тест логирования системного события."""
        result = await audit_logger.log_system_event(
            action="Database connection failed",
            event_type=AuditEventType.SYSTEM_ERROR,
            details={"database": "postgresql"},
            severity=AuditSeverity.CRITICAL,
            error_message="Connection timeout",
        )

        assert result.event_type == "system_error"
        assert result.severity == AuditSeverity.CRITICAL.value
        assert result.error_message == "Connection timeout"

    @pytest.mark.asyncio()
    async def test_get_user_history(self, audit_logger, mock_session):
        """Тест получения истории пользователя."""
        # Mock результатов запроса
        mock_logs = [
            AuditLog(
                id=1,
                event_type="user_login",
                action="Login",
                user_id=12345,
            ),
            AuditLog(
                id=2,
                event_type="target_create",
                action="Create target",
                user_id=12345,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_session.execute.return_value = mock_result

        history = await audit_logger.get_user_history(user_id=12345, limit=10)

        assert len(history) == 2
        assert all(log.user_id == 12345 for log in history)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_security_events(self, audit_logger, mock_session):
        """Тест получения событий безопасности."""
        mock_logs = [
            AuditLog(
                id=1,
                event_type="security_violation",
                action="Unauthorized access attempt",
                severity="warning",
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_session.execute.return_value = mock_result

        events = await audit_logger.get_security_events(limit=10)

        assert len(events) == 1
        assert events[0].event_type == "security_violation"

    @pytest.mark.asyncio()
    async def test_search_logs(self, audit_logger, mock_session):
        """Тест поиска логов."""
        mock_logs = [
            AuditLog(
                id=1,
                event_type="target_create",
                action="Create",
                user_id=12345,
                resource_id="target_123",
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_session.execute.return_value = mock_result

        results = await audit_logger.search_logs(
            user_id=12345,
            event_type=AuditEventType.TARGET_CREATE,
            resource_id="target_123",
        )

        assert len(results) == 1
        assert results[0].resource_id == "target_123"

    def test_audit_log_repr(self):
        """Тест __repr__ метода."""
        log = AuditLog(
            id=1,
            event_type="user_login",
            action="Login",
            user_id=12345,
        )

        repr_str = repr(log)
        assert "AuditLog" in repr_str
        assert "user_login" in repr_str
        assert "12345" in repr_str

    def test_audit_event_type_enum(self):
        """Тест AuditEventType enum."""
        assert AuditEventType.USER_LOGIN.value == "user_login"
        assert AuditEventType.TARGET_CREATE.value == "target_create"
        assert AuditEventType.SYSTEM_ERROR.value == "system_error"

    def test_audit_severity_enum(self):
        """Тест AuditSeverity enum."""
        assert AuditSeverity.DEBUG.value == "debug"
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"


class TestAuditLoggerExtended:
    """Extended tests for AuditLogger to improve coverage."""

    @pytest.fixture()
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture()
    def audit_logger(self, mock_session):
        """Create audit logger."""
        return AuditLogger(mock_session)

    @pytest.mark.asyncio()
    async def test_log_with_string_event_type(self, audit_logger, mock_session):
        """Test log with string event type instead of enum."""
        result = await audit_logger.log(
            event_type="custom_event_type",
            action="Custom action",
            user_id=12345,
        )

        assert result.event_type == "custom_event_type"

    @pytest.mark.asyncio()
    async def test_log_with_ip_address(self, audit_logger, mock_session):
        """Test log with IP address."""
        result = await audit_logger.log(
            event_type=AuditEventType.USER_LOGIN,
            action="Login from IP",
            ip_address="192.168.1.100",
        )

        assert result.ip_address == "192.168.1.100"

    @pytest.mark.asyncio()
    async def test_log_with_resource_info(self, audit_logger, mock_session):
        """Test log with resource type and id."""
        result = await audit_logger.log(
            event_type=AuditEventType.TARGET_CREATE,
            action="Created target",
            resource_type="target",
            resource_id="target_abc123",
        )

        assert result.resource_type == "target"
        assert result.resource_id == "target_abc123"

    @pytest.mark.asyncio()
    async def test_log_with_old_and_new_values(self, audit_logger, mock_session):
        """Test log with old and new values for update operations."""
        result = await audit_logger.log(
            event_type=AuditEventType.SETTINGS_UPDATE,
            action="Updated setting",
            old_value='{"language": "ru"}',
            new_value='{"language": "en"}',
        )

        assert result.old_value == '{"language": "ru"}'
        assert result.new_value == '{"language": "en"}'

    @pytest.mark.asyncio()
    async def test_log_failed_operation(self, audit_logger, mock_session):
        """Test log for failed operation."""
        result = await audit_logger.log(
            event_type=AuditEventType.ITEM_BUY,
            action="Attempted to buy item",
            success=False,
            error_message="Insufficient funds",
        )

        assert result.success == "false"
        assert result.error_message == "Insufficient funds"

    @pytest.mark.asyncio()
    async def test_log_with_severity(self, audit_logger, mock_session):
        """Test log with specific severity."""
        result = await audit_logger.log(
            event_type=AuditEventType.SYSTEM_WARNING,
            action="High memory usage",
            severity=AuditSeverity.WARNING,
        )

        assert result.severity == "warning"

    @pytest.mark.asyncio()
    async def test_log_user_action_with_ip(self, audit_logger, mock_session):
        """Test log_user_action with IP address."""
        result = await audit_logger.log_user_action(
            user_id=123,
            action="Login",
            event_type=AuditEventType.USER_LOGIN,
            ip_address="10.0.0.1",
        )

        assert result.ip_address == "10.0.0.1"

    @pytest.mark.asyncio()
    async def test_log_user_action_failed(self, audit_logger, mock_session):
        """Test log_user_action with failure."""
        result = await audit_logger.log_user_action(
            user_id=123,
            action="Failed operation",
            event_type=AuditEventType.ITEM_BUY,
            success=False,
        )

        assert result.success == "false"

    @pytest.mark.asyncio()
    async def test_get_user_history_with_event_type(self, audit_logger, mock_session):
        """Test get_user_history with event type filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await audit_logger.get_user_history(
            user_id=12345,
            event_type=AuditEventType.USER_LOGIN,
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_user_history_with_string_event_type(
        self, audit_logger, mock_session
    ):
        """Test get_user_history with string event type."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Using a string that's not an enum value
        await audit_logger.get_user_history(
            user_id=12345,
            event_type="custom_event",
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_security_events_with_severity_filter(
        self, audit_logger, mock_session
    ):
        """Test get_security_events with severity filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await audit_logger.get_security_events(
            limit=50,
            severity=AuditSeverity.CRITICAL,
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_search_logs_with_string_event_type(self, audit_logger, mock_session):
        """Test search_logs with string event type."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await audit_logger.search_logs(
            event_type="custom_event",
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_search_logs_with_date_range(self, audit_logger, mock_session):
        """Test search_logs with date range."""
        from datetime import UTC, datetime, timedelta

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        await audit_logger.search_logs(
            start_date=start,
            end_date=end,
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio()
    async def test_search_logs_no_filters(self, audit_logger, mock_session):
        """Test search_logs with no filters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await audit_logger.search_logs()

        mock_session.execute.assert_called_once()


class TestAuditDecorator:
    """Tests for audit_decorator."""

    @pytest.mark.asyncio()
    async def test_decorator_wraps_function(self):
        """Test that decorator properly wraps function."""
        from src.utils.audit_logger import audit_decorator

        @audit_decorator(AuditEventType.TARGET_CREATE, "Create target")
        async def create_target(user_id: int, name: str):
            return {"id": 1, "name": name, "user_id": user_id}

        result = await create_target(user_id=123, name="test")

        assert result["name"] == "test"
        assert result["user_id"] == 123

    @pytest.mark.asyncio()
    async def test_decorator_reraises_exception(self):
        """Test that decorator re-raises exceptions."""
        from src.utils.audit_logger import audit_decorator

        @audit_decorator(AuditEventType.ITEM_BUY, "Buy item")
        async def failing_function(user_id: int):
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_function(user_id=123)

    @pytest.mark.asyncio()
    async def test_decorator_extracts_user_from_kwargs(self):
        """Test decorator extracts user_id from kwargs."""
        from src.utils.audit_logger import audit_decorator

        @audit_decorator(AuditEventType.SETTINGS_UPDATE, "Update settings")
        async def update_settings(setting: str, user_id: int):
            return {"setting": setting, "user_id": user_id}

        result = await update_settings(setting="lang", user_id=456)

        assert result["user_id"] == 456

    @pytest.mark.asyncio()
    async def test_decorator_extracts_user_from_args(self):
        """Test decorator extracts user_id from first positional arg."""
        from src.utils.audit_logger import audit_decorator

        @audit_decorator(AuditEventType.USER_UPDATE, "Update user")
        async def update_user(user_id: int, data: dict):
            return {"user_id": user_id, "data": data}

        result = await update_user(789, {"name": "test"})

        assert result["user_id"] == 789


class TestAuditEventTypeComplete:
    """Complete tests for AuditEventType enum values."""

    def test_api_key_events(self):
        """Test API key related events."""
        assert AuditEventType.API_KEY_ADD.value == "api_key_add"
        assert AuditEventType.API_KEY_UPDATE.value == "api_key_update"
        assert AuditEventType.API_KEY_DELETE.value == "api_key_delete"
        assert AuditEventType.API_KEY_VIEW.value == "api_key_view"

    def test_trading_events(self):
        """Test trading related events."""
        assert AuditEventType.TARGET_DELETE.value == "target_delete"
        assert AuditEventType.TARGET_UPDATE.value == "target_update"
        assert AuditEventType.ITEM_BUY.value == "item_buy"
        assert AuditEventType.ITEM_SELL.value == "item_sell"

    def test_arbitrage_events(self):
        """Test arbitrage related events."""
        assert AuditEventType.ARBITRAGE_SCAN.value == "arbitrage_scan"
        assert AuditEventType.ARBITRAGE_OPPORTUNITY.value == "arbitrage_opportunity"

    def test_settings_events(self):
        """Test settings related events."""
        assert AuditEventType.SETTINGS_UPDATE.value == "settings_update"
        assert AuditEventType.LANGUAGE_CHANGE.value == "language_change"

    def test_admin_events(self):
        """Test admin related events."""
        assert AuditEventType.ADMIN_USER_BAN.value == "admin_user_ban"
        assert AuditEventType.ADMIN_USER_UNBAN.value == "admin_user_unban"
        assert AuditEventType.ADMIN_RATE_LIMIT_CHANGE.value == "admin_rate_limit_change"
        assert (
            AuditEventType.ADMIN_FEATURE_FLAG_CHANGE.value
            == "admin_feature_flag_change"
        )

    def test_user_events(self):
        """Test user related events."""
        assert AuditEventType.USER_LOGOUT.value == "user_logout"
        assert AuditEventType.USER_REGISTER.value == "user_register"
        assert AuditEventType.USER_UPDATE.value == "user_update"
        assert AuditEventType.USER_DELETE.value == "user_delete"

    def test_system_events(self):
        """Test system related events."""
        assert AuditEventType.SYSTEM_WARNING.value == "system_warning"
        assert AuditEventType.SECURITY_VIOLATION.value == "security_violation"
