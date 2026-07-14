import logging
from datetime import datetime

logger = logging.getLogger("LiquidityManager")

class LiquidityManager:
    """
    Manages revolving liquidity and game-specific budget constraints.
    - CS2: Max 10% of total balance.
    - Daily Spend: Max 15% of total balance (revolving).
    
    v14.9.1: Daily spend persisted to SQLite to survive restarts.
    """
    def __init__(self):
        self.daily_spend_log: dict[str, float] = {}  # date_str -> amount
        self.rust_budget_pct = 0.10
        self.daily_limit_pct = 0.15
        self._db_loaded = False

    def _get_today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _load_from_db(self) -> None:
        """Load daily spend from SQLite on first access."""
        if self._db_loaded:
            return
        self._db_loaded = True
        try:
            from src.db.price_history import price_db
            raw = price_db.get_state("liquidity_daily_spend")
            if raw:
                date_str, amount_str = raw.split(":", 1)
                # Only restore if it's from today
                if date_str == self._get_today():
                    self.daily_spend_log[date_str] = float(amount_str)
                    logger.info(f"Restored daily spend from SQLite: ${float(amount_str):.2f}")
        except Exception as e:
            logger.debug(f"Could not load liquidity state from SQLite: {e}")

    def _save_to_db(self) -> None:
        """Persist daily spend to SQLite."""
        try:
            from src.db.price_history import price_db
            today = self._get_today()
            amount = self.daily_spend_log.get(today, 0.0)
            price_db.save_state("liquidity_daily_spend", f"{today}:{amount:.2f}")
        except Exception as e:
            logger.debug(f"Could not persist liquidity state: {e}")

    def get_today_spend(self) -> float:
        self._load_from_db()
        today = self._get_today()
        return self.daily_spend_log.get(today, 0.0)

    def can_spend(self, amount: float, game_id: str, total_balance: float) -> bool:
        """
        Check if the spend satisfies all quantitative constraints.
        """
        self._load_from_db()
        today = self._get_today()
        current_daily_spend = self.daily_spend_log.get(today, 0.0)
        
        # 1. Check Daily Limit (15%)
        max_daily = total_balance * self.daily_limit_pct
        if (current_daily_spend + amount) > max_daily:
            logger.warning(f"Daily liquidity limit reached ({self.daily_limit_pct*100}%). "
                           f"Spend: ${current_daily_spend:.2f}, New: ${amount:.2f}, Max: ${max_daily:.2f}")
            return False

        # 2. Check Per-Game Budget Limit (10% of balance per trade)
        if game_id in ("rust", "a8db"):  # a8db = CS2
            max_per_trade = total_balance * self.rust_budget_pct
            if amount > max_per_trade:
                logger.warning(
                    f"{game_id.upper()} budget limit exceeded per trade. "
                    f"Req: ${amount:.2f}, Max: ${max_per_trade:.2f}"
                )
                return False

        return True

    def record_spend(self, amount: float):
        self._load_from_db()
        today = self._get_today()
        self.daily_spend_log[today] = self.daily_spend_log.get(today, 0.0) + amount
        self._save_to_db()
        logger.info(f"Recorded spend: ${amount:.2f}. Total today: ${self.daily_spend_log[today]:.2f}")
