"""
Pydantic Models for DMarket API Responses.
Provides type-safe validation for all API interactions.

Usage:
    from src.models import AggregatedPriceItem, TargetItem, InventoryItem

All models use `extra="ignore"` for forward compatibility:
if DMarket adds new fields, the bot won't crash.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator


# --- Aggregated Prices (Scanner) ---


class AggregatedPriceItem(BaseModel):
    """Single item from /marketplace-api/v1/aggregated-prices response."""

    model_config = ConfigDict(extra="ignore")

    title: str = "Unknown"
    orderBestPrice: Union[int, Dict[str, Any], str, None] = 0
    offerBestPrice: Union[int, Dict[str, Any], str, None] = 0

    @field_validator("orderBestPrice", "offerBestPrice", mode="before")
    @classmethod
    def normalize_price(cls, v: Any) -> int:
        """Normalize price to integer cents regardless of API format."""
        if isinstance(v, dict):
            return int(v.get("Amount", 0))
        elif isinstance(v, (int, float)):
            return int(v)
        elif isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 0
        return 0


class AggregatedPricesResponse(BaseModel):
    """Response from /marketplace-api/v1/aggregated-prices."""

    model_config = ConfigDict(extra="ignore")

    aggregatedPrices: List[AggregatedPriceItem] = []


# --- Targets (Trader) ---


class TargetPrice(BaseModel):
    """Price object inside a Target."""

    model_config = ConfigDict(extra="ignore")

    Amount: int = 0
    Currency: str = "USD"


class TargetItem(BaseModel):
    """Single target (buy order) from the API."""

    model_config = ConfigDict(extra="ignore")

    TargetID: Optional[str] = None
    Title: str = ""
    Amount: int = 1
    Price: Optional[TargetPrice] = None
    Status: Optional[str] = None

    # Handle alternative field names from API
    id: Optional[str] = None

    @property
    def target_id(self) -> str:
        """Unified access to target ID regardless of API format."""
        return self.TargetID or self.id or ""


class TargetsResponse(BaseModel):
    """Response from /marketplace-api/v1/user-targets."""

    model_config = ConfigDict(extra="ignore")

    Targets: List[TargetItem] = []
    targets: List[TargetItem] = []
    Cursor: Optional[str] = None
    cursor: Optional[str] = None

    @property
    def all_targets(self) -> List[TargetItem]:
        """Unified access to targets regardless of casing."""
        return self.Targets or self.targets


# --- Inventory ---


class InventoryItemPrice(BaseModel):
    """Price info for inventory item."""

    model_config = ConfigDict(extra="ignore")

    Amount: int = 0
    Currency: str = "USD"


class InventoryItem(BaseModel):
    """Single item from user inventory."""

    model_config = ConfigDict(extra="ignore")

    itemId: Optional[str] = None
    title: str = ""
    price: Optional[InventoryItemPrice] = None
    status: Optional[str] = None
    inMarket: bool = False
    gameId: Optional[str] = None


class InventoryResponse(BaseModel):
    """Response from /exchange/v1/user/items."""

    model_config = ConfigDict(extra="ignore")

    objects: List[InventoryItem] = []
    Items: List[InventoryItem] = []
    cursor: Optional[str] = None
    Cursor: Optional[str] = None

    @property
    def all_items(self) -> List[InventoryItem]:
        """Unified access to items regardless of casing."""
        return self.objects or self.Items

    @property
    def next_cursor(self) -> str:
        """Unified cursor access."""
        return self.cursor or self.Cursor or ""


# --- Balance ---


class BalanceResponse(BaseModel):
    """Response from /account/v1/balance."""

    model_config = ConfigDict(extra="ignore")

    usd: Optional[str] = "0"
    dmc: Optional[str] = "0"

    @property
    def usd_cents(self) -> int:
        """Balance in cents."""
        try:
            return int(self.usd or "0")
        except ValueError:
            return 0

    @property
    def usd_dollars(self) -> float:
        """Balance in dollars."""
        return self.usd_cents / 100.0


# --- Market Depth (for Sales) ---


class MarketOffer(BaseModel):
    """Single market offer (listing)."""

    model_config = ConfigDict(extra="ignore")

    price: Optional[Dict[str, Any]] = None
    title: str = ""

    @property
    def price_cents(self) -> int:
        if self.price and isinstance(self.price, dict):
            return int(self.price.get("Amount", 0))
        return 0


class MarketItemsResponse(BaseModel):
    """Response from /exchange/v1/market/items."""

    model_config = ConfigDict(extra="ignore")

    objects: List[MarketOffer] = []
    total: Optional[str] = None
    cursor: Optional[str] = None
