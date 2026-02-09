"""Tests for N8N Client module.

Tests cover:
- N8N client initialization
- Workflow triggering
- Webhook sending
- Workflow management
- Pre-configured trading workflows
- Factory functions

Created: January 2026
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.n8n_client import (
    N8NClient,
    N8NWorkflow,
    TradingWorkflows,
    WorkflowExecutionResult,
    WorkflowType,
    create_n8n_client,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def n8n_client() -> N8NClient:
    """Create an n8n client for testing."""
    return N8NClient(
        base_url="http://localhost:5678",
        api_key="test-api-key",
    )


@pytest.fixture()
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx client."""
    mock = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


# ============================================================================
# Test Data Classes
# ============================================================================


class TestN8NWorkflow:
    """Test N8NWorkflow data class."""

    def test_workflow_creation(self) -> None:
        """Test workflow creation with all fields."""
        workflow = N8NWorkflow(
            id="wf-123",
            name="Test Workflow",
            active=True,
            webhook_url="http://localhost:5678/webhook/test",
        )

        assert workflow.id == "wf-123"
        assert workflow.name == "Test Workflow"
        assert workflow.active is True
        assert workflow.webhook_url is not None

    def test_workflow_to_dict(self) -> None:
        """Test workflow to_dict conversion."""
        workflow = N8NWorkflow(
            id="wf-456",
            name="Dict Test",
            active=False,
        )

        d = workflow.to_dict()

        assert d["id"] == "wf-456"
        assert d["name"] == "Dict Test"
        assert d["active"] is False
        assert d["webhook_url"] is None


class TestWorkflowExecutionResult:
    """Test WorkflowExecutionResult data class."""

    def test_success_result(self) -> None:
        """Test successful execution result."""
        result = WorkflowExecutionResult(
            success=True,
            execution_id="exec-123",
            data={"output": "value"},
        )

        assert result.success is True
        assert result.execution_id == "exec-123"
        assert result.data == {"output": "value"}
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed execution result."""
        result = WorkflowExecutionResult(
            success=False,
            error="Connection refused",
        )

        assert result.success is False
        assert result.error == "Connection refused"
        assert result.execution_id is None


# ============================================================================
# Test N8N Client Initialization
# ============================================================================


class TestN8NClientInit:
    """Test N8N client initialization."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with defaults."""
        client = N8NClient()

        assert client.base_url == "http://localhost:5678"
        assert client.api_key is None
        assert client._client is None

    def test_init_with_custom_url(self) -> None:
        """Test client initialization with custom URL."""
        client = N8NClient(
            base_url="http://n8n.example.com:8080/",
            api_key="my-key",
            timeout=60.0,
        )

        assert client.base_url == "http://n8n.example.com:8080"
        assert client.api_key == "my-key"
        assert client.timeout == 60.0

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slash is stripped from URL."""
        client = N8NClient(base_url="http://localhost:5678///")
        assert client.base_url == "http://localhost:5678"


# ============================================================================
# Test Context Manager
# ============================================================================


class TestContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio()
    async def test_context_manager_creates_client(self) -> None:
        """Test context manager creates httpx client."""
        client = N8NClient()

        async with client as c:
            assert c._client is not None

        assert c._client is None

    @pytest.mark.asyncio()
    async def test_ensure_client_raises_without_context(
        self, n8n_client: N8NClient
    ) -> None:
        """Test _ensure_client raises when not in context."""
        with pytest.raises(RuntimeError, match="not initialized"):
            n8n_client._ensure_client()


# ============================================================================
# Test Workflow Operations
# ============================================================================


class TestWorkflowOperations:
    """Test workflow operations."""

    @pytest.mark.asyncio()
    async def test_trigger_workflow_success(self) -> None:
        """Test successful workflow triggering."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"executionId": "exec-789"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                result = await client.trigger_workflow(
                    workflow_id="test-workflow",
                    data={"key": "value"},
                )

            assert result.success is True
            assert result.execution_id == "exec-789"

    @pytest.mark.asyncio()
    async def test_trigger_workflow_http_error(self) -> None:
        """Test workflow triggering with HTTP error."""
        import httpx

        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Workflow not found"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not found",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                result = await client.trigger_workflow("nonexistent")

            assert result.success is False
            assert "404" in result.error

    @pytest.mark.asyncio()
    async def test_send_webhook_success(self) -> None:
        """Test successful webhook sending."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"received": True}
            mock_response.text = '{"received": true}'
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                result = await client.send_webhook(
                    webhook_path="my-webhook",
                    data={"alert": "test"},
                )

            assert result.success is True
            assert result.data == {"received": True}

    @pytest.mark.asyncio()
    async def test_list_workflows(self) -> None:
        """Test listing workflows."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"id": "wf-1", "name": "Workflow 1", "active": True},
                    {"id": "wf-2", "name": "Workflow 2", "active": False},
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                workflows = await client.list_workflows()

            assert len(workflows) == 2
            assert workflows[0].id == "wf-1"
            assert workflows[0].active is True

    @pytest.mark.asyncio()
    async def test_list_workflows_active_only(self) -> None:
        """Test listing only active workflows."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"id": "wf-1", "name": "Active", "active": True},
                    {"id": "wf-2", "name": "Inactive", "active": False},
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                workflows = await client.list_workflows(active_only=True)

            assert len(workflows) == 1
            assert workflows[0].id == "wf-1"

    @pytest.mark.asyncio()
    async def test_get_workflow(self) -> None:
        """Test getting a specific workflow."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "wf-123",
                "name": "My Workflow",
                "active": True,
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                workflow = await client.get_workflow("wf-123")

            assert workflow is not None
            assert workflow.id == "wf-123"
            assert workflow.name == "My Workflow"

    @pytest.mark.asyncio()
    async def test_activate_workflow(self) -> None:
        """Test activating a workflow."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                result = await client.activate_workflow("wf-123")

            assert result is True
            mock_client.patch.assert_called_once()

    @pytest.mark.asyncio()
    async def test_deactivate_workflow(self) -> None:
        """Test deactivating a workflow."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                result = await client.deactivate_workflow("wf-123")

            assert result is True

    @pytest.mark.asyncio()
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                is_healthy = await client.health_check()

            assert is_healthy is True

    @pytest.mark.asyncio()
    async def test_health_check_failure(self) -> None:
        """Test failed health check."""
        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.aclose = AsyncMock()
            mock_class.return_value = mock_client

            client = N8NClient()
            async with client:
                client._client = mock_client

                is_healthy = await client.health_check()

            assert is_healthy is False


# ============================================================================
# Test Pre-configured Trading Workflows
# ============================================================================


class TestTradingWorkflows:
    """Test pre-configured trading workflows."""

    @pytest.mark.asyncio()
    async def test_trigger_arbitrage_alert(self) -> None:
        """Test arbitrage alert trigger."""
        mock_client = AsyncMock(spec=N8NClient)
        mock_client.send_webhook = AsyncMock(
            return_value=WorkflowExecutionResult(success=True)
        )

        result = await TradingWorkflows.trigger_arbitrage_alert(
            mock_client,
            opportunity={
                "item_name": "AK-47 | Redline",
                "profit_percent": 15.5,
                "buy_price": 10.0,
                "sell_price": 11.55,
            },
        )

        assert result.success is True
        mock_client.send_webhook.assert_called_once()

        # Check the data sent
        call_args = mock_client.send_webhook.call_args
        assert call_args[0][0] == WorkflowType.ARBITRAGE_ALERT
        assert call_args[0][1]["item_name"] == "AK-47 | Redline"
        assert call_args[0][1]["profit_percent"] == 15.5

    @pytest.mark.asyncio()
    async def test_trigger_price_alert(self) -> None:
        """Test price alert trigger."""
        mock_client = AsyncMock(spec=N8NClient)
        mock_client.send_webhook = AsyncMock(
            return_value=WorkflowExecutionResult(success=True)
        )

        result = await TradingWorkflows.trigger_price_alert(
            mock_client,
            item_name="AWP | Dragon Lore",
            current_price=1500.0,
            target_price=1600.0,
            direction="below",
        )

        assert result.success is True

        call_args = mock_client.send_webhook.call_args
        assert call_args[0][1]["item_name"] == "AWP | Dragon Lore"
        assert call_args[0][1]["current_price"] == 1500.0

    @pytest.mark.asyncio()
    async def test_trigger_trade_notification(self) -> None:
        """Test trade notification trigger."""
        mock_client = AsyncMock(spec=N8NClient)
        mock_client.send_webhook = AsyncMock(
            return_value=WorkflowExecutionResult(success=True)
        )

        result = await TradingWorkflows.trigger_trade_notification(
            mock_client,
            trade_data={
                "action": "buy",
                "item_name": "Glock-18 | Fade",
                "price": 100.0,
            },
        )

        assert result.success is True

        call_args = mock_client.send_webhook.call_args
        assert call_args[0][1]["action"] == "buy"

    @pytest.mark.asyncio()
    async def test_trigger_daily_report(self) -> None:
        """Test daily report trigger."""
        mock_client = AsyncMock(spec=N8NClient)
        mock_client.send_webhook = AsyncMock(
            return_value=WorkflowExecutionResult(success=True)
        )

        result = await TradingWorkflows.trigger_daily_report(
            mock_client,
            report_data={
                "total_trades": 25,
                "profit": 150.0,
                "profit_percent": 5.5,
            },
        )

        assert result.success is True

        call_args = mock_client.send_webhook.call_args
        assert call_args[0][1]["total_trades"] == 25

    @pytest.mark.asyncio()
    async def test_trigger_error_notification(self) -> None:
        """Test error notification trigger."""
        mock_client = AsyncMock(spec=N8NClient)
        mock_client.send_webhook = AsyncMock(
            return_value=WorkflowExecutionResult(success=True)
        )

        result = await TradingWorkflows.trigger_error_notification(
            mock_client,
            error_type="api_error",
            error_message="Rate limit exceeded",
            context={"endpoint": "/api/items"},
        )

        assert result.success is True

        call_args = mock_client.send_webhook.call_args
        assert call_args[0][1]["error_type"] == "api_error"
        assert call_args[0][1]["message"] == "Rate limit exceeded"


# ============================================================================
# Test Factory Functions
# ============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_n8n_client_default(self) -> None:
        """Test creating client with defaults."""
        with patch.dict("os.environ", {}, clear=True):
            client = create_n8n_client()

            assert client.base_url == "http://localhost:5678"
            assert client.api_key is None

    def test_create_n8n_client_from_env(self) -> None:
        """Test creating client from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "N8N_BASE_URL": "http://n8n.prod.example.com",
                "N8N_API_KEY": "prod-key-123",
            },
        ):
            client = create_n8n_client()

            assert client.base_url == "http://n8n.prod.example.com"
            assert client.api_key == "prod-key-123"

    def test_create_n8n_client_with_overrides(self) -> None:
        """Test creating client with explicit overrides."""
        with patch.dict(
            "os.environ",
            {
                "N8N_BASE_URL": "http://from-env.com",
                "N8N_API_KEY": "env-key",
            },
        ):
            client = create_n8n_client(
                base_url="http://override.com",
                api_key="override-key",
            )

            assert client.base_url == "http://override.com"
            assert client.api_key == "override-key"


# ============================================================================
# Test Workflow Types
# ============================================================================


class TestWorkflowTypes:
    """Test workflow type enum."""

    def test_workflow_types_values(self) -> None:
        """Test workflow type values."""
        assert WorkflowType.ARBITRAGE_ALERT == "arbitrage-alert"
        assert WorkflowType.PRICE_ALERT == "price-alert"
        assert WorkflowType.TRADE_NOTIFICATION == "trade-notification"
        assert WorkflowType.DAILY_REPORT == "daily-report"
        assert WorkflowType.ERROR_NOTIFICATION == "error-notification"
