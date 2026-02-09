"""Trade State Machine for robust transaction handling.

Implements a Finite State Machine (FSM) for DMarket trading operations.
Ensures atomic transitions, persistent state tracking, and crash recovery.
"""

import logging
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.pending_trade import PendingTrade, PendingTradeStatus
from src.utils.database import get_db_session

logger = logging.getLogger(__name__)

class TradeState(StrEnum):
    """FSM States for trading cycle."""
    SEARCHING = "searching"     # Looking for arbitrage opportunities
    ANALYZING = "analyzing"     # Deep analysis of potential item
    EXECUTING = "executing"     # Sending buy request to API
    VERIFYING = "verifying"     # Checking purchase confirmation
    COMPLETED = "completed"     # Trade successfully finished (bought)
    FAILED = "failed"           # Trade failed

class TradeStateMachine:
    """Manages the state transitions of a single trade operation."""

    def __init__(self, item_data: dict[str, Any] = None, session_id: str = None):
        """Initialize FSM.
        
        Args:
            item_data: Dictionary with item details (title, price, etc.)
            session_id: Optional unique ID for this trade session
        """
        self.item_data = item_data or {}
        self.current_state = TradeState.SEARCHING
        self.trade_id = None  # DB ID of the PendingTrade record
        self._db_session: AsyncSession | None = None

    async def transition_to(self, new_state: TradeState, context: dict[str, Any] = None) -> None:
        """Execute transition to a new state with DB persistence."""
        if new_state == self.current_state:
            return

        logger.info(f"🔄 Trade State Transition: {self.current_state} -> {new_state}")
        
        # Pre-transition logic
        if new_state == TradeState.EXECUTING:
            await self._persist_execution_start()
        
        elif new_state == TradeState.VERIFYING:
            await self._update_status(PendingTradeStatus.BOUGHT, context) # Or specific internal status if model supported it
            
        elif new_state == TradeState.COMPLETED:
            await self._finalize_trade(PendingTradeStatus.BOUGHT) # Ready for listing
            
        elif new_state == TradeState.FAILED:
            await self._finalize_trade(PendingTradeStatus.FAILED)

        self.current_state = new_state

    async def _persist_execution_start(self) -> None:
        """Create initial DB record when execution starts (Critical Section)."""
        if not self.item_data:
            logger.warning("⚠️ No item data to persist for execution state")
            return

        try:
            async with get_db_session() as session:
                # Check if already exists (deduplication)
                asset_id = self.item_data.get("extra", {}).get("assetId") or self.item_data.get("itemId")
                
                # Basic calculation for min_sell_price (required field)
                buy_price = float(self.item_data.get("price", {}).get("USD", 0)) / 100
                min_sell = PendingTrade.calculate_min_sell_price(buy_price)

                trade = PendingTrade(
                    asset_id=str(asset_id),
                    title=self.item_data.get("title", "Unknown Item"),
                    game=self.item_data.get("gameId", "csgo"),
                    buy_price=buy_price,
                    min_sell_price=min_sell,
                    status="executing", # Storing raw state if model allows, or map to BOUGHT pending verify
                    created_at=datetime.utcnow()
                )
                session.add(trade)
                await session.commit()
                await session.refresh(trade)
                self.trade_id = trade.id
                logger.info(f"💾 Persisted trade execution start. DB ID: {self.trade_id}")
        except Exception as e:
            logger.error(f"❌ Failed to persist trade state: {e}")

    async def _update_status(self, db_status: str, context: dict = None) -> None:
        """Update existing DB record status."""
        if not self.trade_id:
            return

        try:
            async with get_db_session() as session:
                trade = await session.get(PendingTrade, self.trade_id)
                if trade:
                    trade.status = db_status
                    if context and "offer_id" in context:
                        trade.offer_id = context["offer_id"]
                    trade.updated_at = datetime.utcnow()
                    await session.commit()
        except Exception as e:
            logger.error(f"❌ Failed to update trade status: {e}")

    async def _finalize_trade(self, final_status: str) -> None:
        """Finalize the trade record."""
        await self._update_status(final_status)

    @staticmethod
    async def recover_stuck_trades(api_client) -> None:
        """Recover trades stuck in EXECUTING state on startup."""
        logger.info("🚑 FSM Recovery: Checking for stuck trades...")
        try:
            async with get_db_session() as session:
                # Find trades that started executing but never verified
                stmt = select(PendingTrade).where(PendingTrade.status == "executing")
                result = await session.execute(stmt)
                stuck_trades = result.scalars().all()

                for trade in stuck_trades:
                    logger.warning(f"⚠️ Recovering stuck trade {trade.id} ({trade.title})...")
                    # Logic: Check inventory to see if we actually own it
                    inventory = await api_client.get_user_inventory(game=trade.game)
                    found = False
                    for item in inventory.get("objects", []):
                        if item.get("itemId") == trade.asset_id:
                            found = True
                            break
                    
                    if found:
                        logger.info(f"✅ Trade {trade.id} was successful! Moving to BOUGHT.")
                        trade.status = PendingTradeStatus.BOUGHT
                    else:
                        logger.warning(f"❌ Trade {trade.id} failed (item not in inventory). Moving to FAILED.")
                        trade.status = PendingTradeStatus.FAILED
                    
                    await session.commit()
        except Exception as e:
            logger.error(f"❌ Recovery failed: {e}")

# Imports needed at module level
from datetime import datetime
