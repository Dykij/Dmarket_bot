"""N8N Workflow Automation Client.

This module provides a Python client for programmatic integration
with n8n workflow automation platform.

Features:
- Trigger workflows programmatically
- Send data to webhooks
- List and manage workflows
- Pre-configured trading workflow triggers

Usage:
    ```python
    from src.utils.n8n_client import N8NClient, TradingWorkflows

    async with N8NClient(base_url="http://localhost:5678") as client:
        # Trigger a workflow
        result = await client.trigger_workflow(
            workflow_id="arbitrage-alert",
            data={"item": "AK-47", "profit": 15.5}
        )

        # Use pre-configured triggers
        await TradingWorkflows.trigger_arbitrage_alert(
            client,
            opportunity={"item_name": "AK-47", "profit_percent": 15.5}
        )
    ```

Created: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class N8NWorkflow:
    """Represents an n8n workflow.

    Attributes:
        id: Workflow unique identifier
        name: Workflow display name
        active: Whether the workflow is currently active
        webhook_url: Webhook URL if workflow has webhook trigger
        created_at: When the workflow was created
        updated_at: Last update time
    """

    id: str
    name: str
    active: bool
    webhook_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "active": self.active,
            "webhook_url": self.webhook_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class WorkflowExecutionResult:
    """Result of a workflow execution.

    Attributes:
        success: Whether execution was successful
        execution_id: Execution identifier
        data: Response data from workflow
        error: Error message if failed
    """

    success: bool
    execution_id: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


# ============================================================================
# Workflow Types
# ============================================================================


class WorkflowType(StrEnum):
    """Pre-defined workflow types for trading bot."""

    ARBITRAGE_ALERT = "arbitrage-alert"
    PRICE_ALERT = "price-alert"
    TRADE_NOTIFICATION = "trade-notification"
    DAILY_REPORT = "daily-report"
    BALANCE_UPDATE = "balance-update"
    ERROR_NOTIFICATION = "error-notification"


# ============================================================================
# N8N Client
# ============================================================================


class N8NClient:
    """Client for n8n workflow automation.

    Enables:
    - Triggering workflows programmatically
    - Managing workflow state
    - Sending webhook data
    - Receiving execution results

    The client uses httpx for async HTTP operations and supports
    both direct API calls and webhook triggers.

    Attributes:
        base_url: Base URL of n8n instance
        api_key: Optional API key for authentication

    Example:
        >>> async with N8NClient("http://localhost:5678") as client:
        ...     await client.trigger_workflow("my-workflow", {"data": "value"})
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5678",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize n8n client.

        Args:
            base_url: Base URL of n8n instance
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

        logger.info(
            "n8n_client_initialized",
            base_url=self.base_url,
            has_api_key=api_key is not None,
        )

    async def __aenter__(self) -> N8NClient:  # noqa: PYI034
        """Async context manager entry."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async context manager: "
                "async with N8NClient() as client: ..."
            )
        return self._client

    # =========================================================================
    # Workflow Operations
    # =========================================================================

    async def trigger_workflow(
        self,
        workflow_id: str,
        data: dict[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Trigger a workflow execution.

        This executes a workflow via the n8n API, which requires
        the workflow to be active.

        Args:
            workflow_id: ID or name of the workflow
            data: Optional data to pass to the workflow

        Returns:
            WorkflowExecutionResult with execution details
        """
        client = self._ensure_client()

        try:
            response = await client.post(
                f"/api/v1/workflows/{workflow_id}/execute",
                json=data or {},
            )
            response.raise_for_status()

            result = response.json()

            logger.info(
                "n8n_workflow_triggered",
                workflow_id=workflow_id,
                execution_id=result.get("executionId"),
            )

            return WorkflowExecutionResult(
                success=True,
                execution_id=result.get("executionId"),
                data=result,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                "n8n_workflow_trigger_failed",
                workflow_id=workflow_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            return WorkflowExecutionResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )

        except Exception as e:
            logger.exception(
                "n8n_workflow_trigger_error",
                workflow_id=workflow_id,
                error=str(e),
            )
            return WorkflowExecutionResult(
                success=False,
                error=str(e),
            )

    async def send_webhook(
        self,
        webhook_path: str,
        data: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Send data to an n8n webhook.

        Webhooks are the simplest way to trigger workflows.
        The webhook URL format is: {base_url}/webhook/{path}

        Args:
            webhook_path: Webhook path (after /webhook/)
            data: Data to send

        Returns:
            WorkflowExecutionResult with response data
        """
        client = self._ensure_client()

        try:
            response = await client.post(
                f"/webhook/{webhook_path}",
                json=data,
            )
            response.raise_for_status()

            result = response.json() if response.text else {}

            logger.info(
                "n8n_webhook_sent",
                webhook_path=webhook_path,
            )

            return WorkflowExecutionResult(
                success=True,
                data=result,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                "n8n_webhook_failed",
                webhook_path=webhook_path,
                status_code=e.response.status_code,
            )
            return WorkflowExecutionResult(
                success=False,
                error=f"HTTP {e.response.status_code}",
            )

        except Exception as e:
            logger.exception(
                "n8n_webhook_error",
                webhook_path=webhook_path,
                error=str(e),
            )
            return WorkflowExecutionResult(
                success=False,
                error=str(e),
            )

    async def list_workflows(self, active_only: bool = False) -> list[N8NWorkflow]:
        """List all available workflows.

        Args:
            active_only: Only return active workflows

        Returns:
            List of N8NWorkflow objects
        """
        client = self._ensure_client()

        try:
            response = await client.get("/api/v1/workflows")
            response.raise_for_status()

            data = response.json()
            workflows = []

            for w in data.get("data", []):
                if active_only and not w.get("active", False):
                    continue

                workflows.append(N8NWorkflow(
                    id=w["id"],
                    name=w.get("name", "Unnamed"),
                    active=w.get("active", False),
                    webhook_url=w.get("webhookUrl"),
                ))

            logger.debug(
                "n8n_workflows_listed",
                count=len(workflows),
            )

            return workflows

        except Exception as e:
            logger.exception("n8n_list_workflows_failed", error=str(e))
            return []

    async def get_workflow(self, workflow_id: str) -> N8NWorkflow | None:
        """Get a specific workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            N8NWorkflow or None if not found
        """
        client = self._ensure_client()

        try:
            response = await client.get(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()

            w = response.json()

            return N8NWorkflow(
                id=w["id"],
                name=w.get("name", "Unnamed"),
                active=w.get("active", False),
                webhook_url=w.get("webhookUrl"),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

        except Exception as e:
            logger.exception(
                "n8n_get_workflow_failed",
                workflow_id=workflow_id,
                error=str(e),
            )
            return None

    async def activate_workflow(self, workflow_id: str) -> bool:
        """Activate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if activated successfully
        """
        client = self._ensure_client()

        try:
            response = await client.patch(
                f"/api/v1/workflows/{workflow_id}",
                json={"active": True},
            )
            response.raise_for_status()

            logger.info("n8n_workflow_activated", workflow_id=workflow_id)
            return True

        except Exception as e:
            logger.exception(
                "n8n_activate_workflow_failed",
                workflow_id=workflow_id,
                error=str(e),
            )
            return False

    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deactivated successfully
        """
        client = self._ensure_client()

        try:
            response = await client.patch(
                f"/api/v1/workflows/{workflow_id}",
                json={"active": False},
            )
            response.raise_for_status()

            logger.info("n8n_workflow_deactivated", workflow_id=workflow_id)
            return True

        except Exception as e:
            logger.exception(
                "n8n_deactivate_workflow_failed",
                workflow_id=workflow_id,
                error=str(e),
            )
            return False

    async def health_check(self) -> bool:
        """Check if n8n is available.

        Returns:
            True if n8n is healthy
        """
        client = self._ensure_client()

        try:
            response = await client.get("/healthz")
            return response.status_code == 200
        except Exception:
            return False


# ============================================================================
# Pre-configured Trading Workflows
# ============================================================================


class TradingWorkflows:
    """Pre-configured workflow triggers for trading operations.

    Provides convenience methods for common trading bot workflows.
    Each method sends data in the expected format for the corresponding
    n8n workflow.
    """

    @staticmethod
    async def trigger_arbitrage_alert(
        client: N8NClient,
        opportunity: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Trigger arbitrage alert workflow.

        Args:
            client: N8N client instance
            opportunity: Arbitrage opportunity data

        Returns:
            Workflow execution result
        """
        data = {
            "type": "arbitrage",
            "item_name": opportunity.get("item_name"),
            "profit_percent": opportunity.get("profit_percent"),
            "buy_price": opportunity.get("buy_price"),
            "sell_price": opportunity.get("sell_price"),
            "platform": opportunity.get("platform", "dmarket"),
            "game": opportunity.get("game", "csgo"),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return await client.send_webhook(
            WorkflowType.ARBITRAGE_ALERT,
            data,
        )

    @staticmethod
    async def trigger_price_alert(
        client: N8NClient,
        item_name: str,
        current_price: float,
        target_price: float,
        direction: str = "below",  # "below" or "above"
    ) -> WorkflowExecutionResult:
        """Trigger price alert workflow.

        Args:
            client: N8N client instance
            item_name: Name of the item
            current_price: Current price
            target_price: Target price that triggered alert
            direction: Price direction (below/above target)

        Returns:
            Workflow execution result
        """
        data = {
            "type": "price_alert",
            "item_name": item_name,
            "current_price": current_price,
            "target_price": target_price,
            "direction": direction,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return await client.send_webhook(
            WorkflowType.PRICE_ALERT,
            data,
        )

    @staticmethod
    async def trigger_trade_notification(
        client: N8NClient,
        trade_data: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Trigger trade notification workflow.

        Args:
            client: N8N client instance
            trade_data: Trade details

        Returns:
            Workflow execution result
        """
        data = {
            "type": "trade",
            "action": trade_data.get("action"),  # buy/sell
            "item_name": trade_data.get("item_name"),
            "price": trade_data.get("price"),
            "quantity": trade_data.get("quantity", 1),
            "platform": trade_data.get("platform", "dmarket"),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return await client.send_webhook(
            WorkflowType.TRADE_NOTIFICATION,
            data,
        )

    @staticmethod
    async def trigger_daily_report(
        client: N8NClient,
        report_data: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Trigger daily report workflow.

        Args:
            client: N8N client instance
            report_data: Report summary data

        Returns:
            Workflow execution result
        """
        data = {
            "type": "daily_report",
            "date": datetime.now(UTC).date().isoformat(),
            "total_trades": report_data.get("total_trades", 0),
            "profit": report_data.get("profit", 0),
            "profit_percent": report_data.get("profit_percent", 0),
            "top_items": report_data.get("top_items", []),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return await client.send_webhook(
            WorkflowType.DAILY_REPORT,
            data,
        )

    @staticmethod
    async def trigger_error_notification(
        client: N8NClient,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Trigger error notification workflow.

        Args:
            client: N8N client instance
            error_type: Type of error
            error_message: Error message
            context: Additional context

        Returns:
            Workflow execution result
        """
        data = {
            "type": "error",
            "error_type": error_type,
            "message": error_message,
            "context": context or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return await client.send_webhook(
            WorkflowType.ERROR_NOTIFICATION,
            data,
        )


# ============================================================================
# Factory Functions
# ============================================================================


def create_n8n_client(
    base_url: str | None = None,
    api_key: str | None = None,
) -> N8NClient:
    """Create an n8n client with default settings.

    Args:
        base_url: Optional base URL (default: localhost:5678)
        api_key: Optional API key

    Returns:
        N8NClient instance
    """
    import os

    return N8NClient(
        base_url=base_url or os.getenv("N8N_BASE_URL", "http://localhost:5678"),
        api_key=api_key or os.getenv("N8N_API_KEY"),
    )
