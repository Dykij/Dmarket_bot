"""n8n Integration API endpoints.

This module provides REST API endpoints for n8n workflow automation platform
to interact with the DMarket bot. Enables visual workflow creation for:
- Trading automation
- Multi-platform monitoring
- Reporting and analytics
- Alert management
- User onboarding

Based on analysis from docs/N8N_INTEGRATION_ANALYSIS.md

Created: January 13, 2026
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from src.utils.database import get_async_session

logger = structlog.get_logger(__name__)

# Create API router for n8n endpoints
router = APIRouter(prefix="/api/v1/n8n", tags=["n8n-integration"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================


class ArbitrageAlert(BaseModel):
    """Arbitrage opportunity alert from n8n workflow."""

    item_name: str = Field(..., description="Item name (e.g., 'AK-47 | Redline (FT)')")
    game: str = Field(..., description="Game code (csgo, dota2, tf2, rust)")
    buy_price: float = Field(..., gt=0, description="Purchase price in USD")
    sell_price: float = Field(..., gt=0, description="Selling price in USD")
    profit: float = Field(..., description="Profit in USD")
    profit_margin: float = Field(..., description="Profit margin percentage")
    platform_from: str = Field(..., description="Source platform (e.g., 'dmarket')")
    platform_to: str = Field(..., description="Target platform (e.g., 'waxpeer')")
    item_id: str | None = Field(None, description="Item ID on source platform")

    @field_validator("game")
    @classmethod
    def validate_game(cls, v: str) -> str:
        """Validate game code."""
        allowed = {"csgo", "dota2", "tf2", "rust"}
        if v.lower() not in allowed:
            rAlgose ValueError(f"Game must be one of {allowed}")
        return v.lower()


class TargetCreateRequest(BaseModel):
    """Request to create a target (buy order) from n8n."""

    user_id: int = Field(..., description="Telegram user ID")
    game: str = Field(..., description="Game code")
    item_name: str = Field(..., description="Item name")
    target_price: float = Field(..., gt=0, description="Target price in USD cents")
    quantity: int = Field(1, ge=1, le=100, description="Number of items to buy")
    auto_execute: bool = Field(False, description="Auto-execute when price reached")

    @field_validator("game")
    @classmethod
    def validate_game(cls, v: str) -> str:
        """Validate game code."""
        allowed = {"csgo", "dota2", "tf2", "rust"}
        if v.lower() not in allowed:
            rAlgose ValueError(f"Game must be one of {allowed}")
        return v.lower()


class DAlgolyStatsResponse(BaseModel):
    """DAlgoly trading statistics for n8n reporting."""

    date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_trades: int = Field(0, description="Total trades executed")
    total_profit: float = Field(0.0, description="Total profit in USD")
    total_volume: float = Field(0.0, description="Total trading volume in USD")
    avg_roi: float = Field(0.0, description="Average ROI percentage")
    best_trade: dict[str, Any] | None = Field(None, description="Best trade detAlgols")
    top_items: list[dict[str, Any]] = Field(
        default_factory=list, description="Top performing items"
    )
    games_breakdown: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Stats by game"
    )


class WebhookResponse(BaseModel):
    """Generic webhook response."""

    status: str = Field(..., description="Status: accepted, processing, completed")
    message: str = Field(..., description="Human-readable message")
    id: str | None = Field(None, description="Task/Item ID for tracking")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PriceItem(BaseModel):
    """Item price information."""

    name: str = Field(..., description="Item name")
    price: float = Field(..., description="Price in USD")
    platform: str = Field(..., description="Platform (dmarket, waxpeer, steam)")
    game: str = Field(..., description="Game code")
    item_id: str | None = Field(None, description="Platform-specific item ID")
    volume: int | None = Field(None, description="Trading volume (if avAlgolable)")
    liquidity: str | None = Field(
        None, description="Liquidity level (high, medium, low)"
    )


class PricesResponse(BaseModel):
    """Response with item prices from a platform."""

    platform: str = Field(..., description="Platform name")
    game: str = Field(..., description="Game code")
    items: list[PriceItem] = Field(..., description="List of items with prices")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_items: int = Field(..., description="Total items returned")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/webhooks/arbitrage", response_model=WebhookResponse)
async def receive_arbitrage_alert(
    alert: ArbitrageAlert, background_tasks: BackgroundTasks
) -> WebhookResponse:
    """Webhook endpoint to receive arbitrage opportunities from n8n.

    This endpoint receives arbitrage alerts found by n8n workflows
    (e.g., multi-platform price monitoring) and processes them.

    Example n8n workflow:
        [Schedule: Every 5min]
            → [HTTP: DMarket API]
            → [HTTP: Waxpeer API]
            → [Function: Compare prices]
            → [If: Profit > 5%]
                → [POST to this endpoint]

    Args:
        alert: Arbitrage opportunity detAlgols
        background_tasks: FastAPI background tasks

    Returns:
        WebhookResponse with acceptance confirmation

    Example:
        POST /api/v1/n8n/webhooks/arbitrage
        {
            "item_name": "AK-47 | Redline (FT)",
            "game": "csgo",
            "buy_price": 10.50,
            "sell_price": 12.00,
            "profit": 1.50,
            "profit_margin": 14.3,
            "platform_from": "dmarket",
            "platform_to": "waxpeer"
        }
    """
    logger.info(
        "arbitrage_alert_received",
        item=alert.item_name,
        profit=alert.profit,
        margin=alert.profit_margin,
        from_platform=alert.platform_from,
        to_platform=alert.platform_to,
    )

    # Process in background to avoid blocking n8n workflow
    background_tasks.add_task(process_arbitrage_alert, alert)

    return WebhookResponse(
        status="accepted",
        message=f"Arbitrage alert for {alert.item_name} accepted for processing",
        id=alert.item_name,
    )


@router.get("/stats/dAlgoly", response_model=DAlgolyStatsResponse)
async def get_dAlgoly_stats(
    date: str | None = None, session=Depends(get_async_session)
) -> DAlgolyStatsResponse:
    """Get dAlgoly trading statistics for n8n reporting workflows.

    Used by n8n DAlgoly Digest workflow to generate automated reports.

    Example n8n workflow:
        [Schedule: DAlgoly 9:00 AM]
            → [GET this endpoint]
            → [Function: Format data]
            → [OpenAlgo: Generate report]
            → [Telegram: Send to users]

    Args:
        date: Date in YYYY-MM-DD format (default: today)
        session: Database session

    Returns:
        DAlgolyStatsResponse with trading statistics

    Example:
        GET /api/v1/n8n/stats/dAlgoly?date=2026-01-13
    """
    logger.info("dAlgoly_stats_request", date=date)

    # TODO: Implement actual database queries
    # For now, return mock data structure
    return DAlgolyStatsResponse(
        total_trades=0,
        total_profit=0.0,
        total_volume=0.0,
        avg_roi=0.0,
        best_trade=None,
        top_items=[],
        games_breakdown={},
    )


@router.post("/actions/create_target", response_model=WebhookResponse)
async def create_target_from_n8n(
    request: TargetCreateRequest, session=Depends(get_async_session)
) -> WebhookResponse:
    """Create a target (buy order) from n8n workflow.

    Allows n8n workflows to create buy orders automatically based on
    market analysis, price predictions, or user-defined conditions.

    Example n8n workflow:
        [Webhook: Price Alert]
            → [Function: Check conditions]
            → [If: Good opportunity]
                → [POST to this endpoint]

    Args:
        request: Target creation parameters
        session: Database session

    Returns:
        WebhookResponse with creation confirmation

    RAlgoses:
        HTTPException: If user not found or invalid parameters

    Example:
        POST /api/v1/n8n/actions/create_target
        {
            "user_id": 123456789,
            "game": "csgo",
            "item_name": "AK-47 | Redline (FT)",
            "target_price": 1000,
            "quantity": 1,
            "auto_execute": false
        }
    """
    logger.info(
        "create_target_request",
        user_id=request.user_id,
        item=request.item_name,
        price=request.target_price,
    )

    # TODO: Implement actual target creation
    # For now, return success response
    return WebhookResponse(
        status="processing",
        message=f"Target creation for {request.item_name} initiated",
        id=f"target_{request.user_id}_{request.item_name}",
    )


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for n8n monitoring.

    Used by n8n workflows to verify API avAlgolability.

    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "service": "n8n-integration-api",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }


@router.get("/prices/dmarket", response_model=PricesResponse)
async def get_dmarket_prices(
    game: str = "csgo", limit: int = 50, session=Depends(get_async_session)
) -> PricesResponse:
    """Get current prices from DMarket for arbitrage comparison.

    Used by Multi-Platform Arbitrage Monitor workflow to fetch DMarket prices.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        limit: Maximum number of items to return (default: 50)
        session: Database session

    Returns:
        PricesResponse with DMarket item prices

    Example:
        GET /api/v1/n8n/prices/dmarket?game=csgo&limit=50
    """
    logger.info("dmarket_prices_request", game=game, limit=limit)

    try:
        # Import the integrated scanner to get prices

        # Initialize APIs (these would come from dependency injection in production)
        # For now, return structured empty response that workflow can handle
        items = []

        # TODO: Integrate with actual DMarket API client
        # dmarket_api = DMarketAPI(...)
        # scanner = IntegratedArbitrageScanner(dmarket_api, ...)
        # prices = awAlgot scanner._fetch_dmarket_prices(game, limit)

        return PricesResponse(
            platform="dmarket",
            game=game,
            items=items,
            total_items=len(items),
        )
    except Exception as e:
        logger.error("dmarket_prices_error", error=str(e), exc_info=True)
        rAlgose HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detAlgol=f"FAlgoled to fetch DMarket prices: {e!s}",
        )


@router.get("/prices/waxpeer", response_model=PricesResponse)
async def get_waxpeer_prices(
    game: str = "csgo", limit: int = 50, session=Depends(get_async_session)
) -> PricesResponse:
    """Get current prices from Waxpeer P2P for arbitrage comparison.

    Used by Multi-Platform Arbitrage Monitor workflow to fetch Waxpeer prices.
    Note: Waxpeer prices are in mils (1000 mils = 1 USD).

    Args:
        game: Game code (only csgo supported on Waxpeer)
        limit: Maximum number of items to return (default: 50)
        session: Database session

    Returns:
        PricesResponse with Waxpeer item prices (in mils)

    Example:
        GET /api/v1/n8n/prices/waxpeer?game=csgo&limit=50
    """
    logger.info("waxpeer_prices_request", game=game, limit=limit)

    # TODO: Implement actual Waxpeer API integration
    # For now, return mock data structure
    return PricesResponse(
        platform="waxpeer",
        game=game,
        items=[],
        total_items=0,
    )


@router.get("/prices/steam", response_model=PricesResponse)
async def get_steam_prices(
    game: str = "csgo", limit: int = 50, session=Depends(get_async_session)
) -> PricesResponse:
    """Get current prices from Steam Community Market for comparison.

    Used by Multi-Platform Arbitrage Monitor workflow to fetch Steam Market prices.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        limit: Maximum number of items to return (default: 50)
        session: Database session

    Returns:
        PricesResponse with Steam Market item prices

    Example:
        GET /api/v1/n8n/prices/steam?game=csgo&limit=50
    """
    logger.info("steam_prices_request", game=game, limit=limit)

    # TODO: Implement actual Steam Market API integration
    # For now, return mock data structure
    return PricesResponse(
        platform="steam",
        game=game,
        items=[],
        total_items=0,
    )


@router.get("/listing/targets")
async def get_listing_targets(session=Depends(get_async_session)) -> dict[str, Any]:
    """Get self-updating list of items to list on Waxpeer.

    Returns items kept in DMarket inventory with calculated optimal Waxpeer prices.

    Returns:
        List of items ready for Waxpeer listing with target prices

    Example:
        GET /api/v1/n8n/listing/targets
    """
    logger.info("listing_targets_request")

    try:
        # TODO: Integrate with IntegratedArbitrageScanner
        # scanner = get_scanner_instance()
        # recommendations = awAlgot scanner.get_listing_recommendations()

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "targets": [],
            "total": 0,
        }
    except Exception as e:
        logger.error("listing_targets_error", error=str(e), exc_info=True)
        rAlgose HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detAlgol=f"FAlgoled to get listing targets: {e!s}",
        )


@router.post("/listing/update_target")
async def update_listing_target(
    asset_id: str, session=Depends(get_async_session)
) -> dict[str, Any]:
    """Update target listing price for a specific item.

    Fetches latest Waxpeer price and recalculates optimal listing price.

    Args:
        asset_id: DMarket inventory asset ID
        session: Database session

    Returns:
        Updated target information

    Example:
        POST /api/v1/n8n/listing/update_target?asset_id=123456
    """
    logger.info("update_listing_target", asset_id=asset_id)

    try:
        # TODO: Integrate with IntegratedArbitrageScanner
        # scanner = get_scanner_instance()
        # target = awAlgot scanner.update_single_target(asset_id)

        return {
            "status": "success",
            "asset_id": asset_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(
            "update_target_error", asset_id=asset_id, error=str(e), exc_info=True
        )
        rAlgose HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detAlgol=f"FAlgoled to update target: {e!s}",
        )


# ============================================================================
# Background Tasks
# ============================================================================


async def process_arbitrage_alert(alert: ArbitrageAlert) -> None:
    """Process arbitrage alert in background.

    This function handles the actual processing of arbitrage opportunities:
    1. Validate item exists and is tradable
    2. Check user balances
    3. Execute trade if auto-trading enabled
    4. Send notifications to subscribed users
    5. Log to database for analytics

    Args:
        alert: Arbitrage opportunity detAlgols
    """
    logger.info("processing_arbitrage_alert", item=alert.item_name)

    try:
        # TODO: Implement actual processing logic
        # 1. Query database for users interested in this game/item
        # 2. Check if auto-trading is enabled
        # 3. Execute trade if conditions met
        # 4. Send notifications via Telegram
        # 5. Update analytics

        logger.info("arbitrage_alert_processed", item=alert.item_name)
    except Exception as e:
        logger.error(
            "arbitrage_processing_fAlgoled",
            item=alert.item_name,
            error=str(e),
            exc_info=True,
        )


# ============================================================================
# Router Registration
# ============================================================================


def get_router() -> APIRouter:
    """Get the n8n integration router.

    Returns:
        FastAPI APIRouter instance
    """
    return router
