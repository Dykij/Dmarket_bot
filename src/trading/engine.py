"""Trading Engine: Core Business Logic for Deal Evaluation.

This module implements the Service Layer pattern, separating decision making
from execution. It analyzes market items and determines if they meet
purchasing criteria based on ROI, liquidity, and configuration.
"""

from typing import Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DealEvaluation:
    """Result of deal analysis."""
    should_buy: bool
    reason: str
    discount_percent: float = 0.0
    profit_potential: float = 0.0

class TradingConfig:
    """Configuration for trading decisions."""
    def __init__(
        self,
        min_discount_percent: float = 30.0,
        max_price_usd: float = 100.0,
        check_sales_history: bool = True,
        check_trade_lock: bool = True,
        max_trade_lock_hours: int = 168,
    ):
        self.min_discount_percent = min_discount_percent
        self.max_price_usd = max_price_usd
        self.check_sales_history = check_sales_history
        self.check_trade_lock = check_trade_lock
        self.max_trade_lock_hours = max_trade_lock_hours

class TradingEngine:
    """Pure logic service for evaluating market opportunities."""
    
    def __init__(self, config: TradingConfig | None = None):
        self.config = config or TradingConfig()

    def evaluate_deal(self, item_data: dict[str, Any]) -> DealEvaluation:
        """Analyze if an item is worth buying.
        
        Args:
            item_data: Raw item dictionary from DMarket API (or Pydantic model dict)
            
        Returns:
            DealEvaluation object with decision and metrics.
        """
        # 1. Extract Prices
        try:
            price_usd = float(item_data.get("price", {}).get("USD", 0)) / 100
            suggested_raw = item_data.get("suggestedPrice", {})
            
            # Handle different suggestedPrice formats (dict or direct value)
            if isinstance(suggested_raw, dict):
                suggested_price_usd = float(suggested_raw.get("USD", 0)) / 100
            else:
                suggested_price_usd = float(suggested_raw) / 100 if suggested_raw else 0.0
                
        except (ValueError, TypeError, AttributeError):
            return DealEvaluation(False, "Invalid price data")

        # 2. Basic Validation
        if suggested_price_usd <= 0:
            return DealEvaluation(False, "No suggested price")
            
        if price_usd <= 0:
            return DealEvaluation(False, "Free item?")

        # 3. Calculate Metrics
        discount = ((suggested_price_usd - price_usd) / suggested_price_usd) * 100
        
        # 4. Apply Business Rules
        
        # Rule: Max Price
        if price_usd > self.config.max_price_usd:
            return DealEvaluation(False, f"Price ${price_usd:.2f} > ${self.config.max_price_usd}")
            
        # Rule: Min Discount
        if discount < self.config.min_discount_percent:
            return DealEvaluation(
                False, 
                f"Discount {discount:.1f}% < {self.config.min_discount_percent}%",
                discount_percent=discount
            )

        # Rule: Trade Lock
        if self.config.check_trade_lock:
            trade_lock = item_data.get("extra", {}).get("tradeLockDuration", 0)
            if trade_lock > self.config.max_trade_lock_hours * 3600:
                return DealEvaluation(
                    False, 
                    f"Lock {trade_lock/3600:.1f}h > {self.config.max_trade_lock_hours}h",
                    discount_percent=discount
                )

        # 5. Success
        return DealEvaluation(
            should_buy=True,
            reason=f"Discount {discount:.1f}% >= {self.config.min_discount_percent}%",
            discount_percent=discount,
            profit_potential=suggested_price_usd - price_usd
        )

    async def check_liquidity(self, api_client, title: str) -> bool:
        """Check if item has enough sales volume.
        
        Note: This requires an async call, so it's kept separate from the synchronous evaluate_deal.
        """
        if not self.config.check_sales_history:
            return True
            
        try:
            # We import here to avoid circular dependencies if sales_history depends on something else
            from src.dmarket.sales_history import get_item_sales_history
            
            history = await get_item_sales_history(api_client, item_title=title, days=7)
            
            if not history:
                return True # Optimistic strategy: assume liquid if no data (or configurable)
                
            daily_sales = len(history) / 7
            return daily_sales >= 5
            
        except ImportError:
            return True
        except Exception as e:
            logger.error(f"Liquidity check failed: {e}")
            return True
