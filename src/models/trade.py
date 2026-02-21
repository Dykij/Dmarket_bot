"""Cross-platform trade models."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Numeric, String
from src.models.base import Base, UUIDType


class CrossPlatformTrade(Base):
    """
    Tracks lifecycle of an item bought on one platform and sold on another.

    Workflow:
    1. Buy on DMarket (status='at_dmarket')
    2. Withdraw to Steam (status='on_transfer')
    3. List on Waxpeer (status='listed_waxpeer')
    4. Sell on Waxpeer (status='sold')
    """

    __tablename__ = "cross_platform_trades"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    item_id = Column(
        String(255), nullable=False, index=True, doc="AssetID from DMarket"
    )
    game = Column(String(50), nullable=False, index=True)
    item_name = Column(String, nullable=False)

    # Buy Platform (Entry)
    buy_platform = Column(String(50), default="dmarket")
    buy_price = Column(Numeric(18, 4), nullable=False)
    buy_fee_percent = Column(Numeric(5, 2), default=0.00)
    buy_time = Column(DateTime, default=datetime.utcnow)

    # Status Tracking
    status = Column(String(50), nullable=False, default="at_dmarket", index=True)
    transfer_time = Column(DateTime, nullable=True)

    # Sell Platform (Exit)
    sell_platform = Column(String(50), default="waxpeer")
    target_sell_price = Column(Numeric(18, 4), nullable=True)
    sold_price = Column(Numeric(18, 4), nullable=True)
    sold_time = Column(DateTime, nullable=True)

    # Performance Metrics
    net_profit = Column(Numeric(18, 4), nullable=True)
    roi_percent = Column(Numeric(10, 2), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CrossPlatformTrade(item='{self.item_name}', status='{self.status}')>"
