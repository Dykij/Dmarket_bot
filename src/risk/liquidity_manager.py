import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger("LiquidityManager")

class LiquidityManager:
    """
    Manages revolving liquidity and game-specific budget constraints.
    - Rust: Max 10% of total balance.
    - Daily Spend: Max 15% of total balance (revolving).
    """
    def __init__(self):
        self.daily_spend_log: Dict[str, float] = {}  # date_str -> amount
        self.rust_budget_pct = 0.10
        self.daily_limit_pct = 0.15

    def _get_today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def get_today_spend(self) -> float:
        today = self._get_today()
        return self.daily_spend_log.get(today, 0.0)

    def can_spend(self, amount: float, game_id: str, total_balance: float) -> bool:
        """
        Check if the spend satisfies all quantitative constraints.
        """
        today = self._get_today()
        current_daily_spend = self.daily_spend_log.get(today, 0.0)
        
        # 1. Check Daily Limit (15%)
        max_daily = total_balance * self.daily_limit_pct
        if (current_daily_spend + amount) > max_daily:
            logger.warning(f"Daily liquidity limit reached ({self.daily_limit_pct*100}%). "
                           f"Spend: ${current_daily_spend:.2f}, New: ${amount:.2f}, Max: ${max_daily:.2f}")
            return False

        # 2. Check Rust Specific Limit (10%)
        if game_id == "rust":
            max_rust = total_balance * self.rust_budget_pct
            # Note: This is a simple per-trade or current-in-market check.
            # Ideally would track current active Rust targets.
            if amount > max_rust:
                logger.warning(f"Rust budget limit exceeded per trade. "
                               f"Req: ${amount:.2f}, Max: ${max_rust:.2f}")
                return False

        return True

    def record_spend(self, amount: float):
        today = self._get_today()
        self.daily_spend_log[today] = self.daily_spend_log.get(today, 0.0) + amount
        logger.info(f"Recorded spend: ${amount:.2f}. Total today: ${self.daily_spend_log[today]:.2f}")
