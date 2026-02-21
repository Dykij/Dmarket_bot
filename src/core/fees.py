"""
Fee calculator logic.
Uses src.core.config as the source of truth.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from src.core.config import CONFIG


class LiquidityAdjustedFee:
    """
    Calculates profit margins considering:
    - Platform Fees (DMarket, Waxpeer)
    - Cashout Fees (Real money withdraw)
    - Opportunity Cost (Time Value of Money for 7-day holds)
    """

    def __init__(self):
        self.cfg = CONFIG.fees

    def calculate_opportunity_cost(self, capital: Decimal, days: int) -> Decimal:
        """
        Cost of locking capital.
        Formula: Capital * ((1 + daily_rate)^days - 1)
        """
        if days <= 0:
            return Decimal("0")
        compound_factor = (Decimal("1") + self.cfg.DAILY_OPPORTUNITY_COST) ** days
        return (capital * (compound_factor - Decimal("1"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def calculate_gem_profit(
        self,
        buy_price: float | Decimal,
        wax_sell_price: float | Decimal,
        hold_days: int = 7,
    ) -> Dict[str, Decimal]:
        """
        Cross-Market Profit (GEMS).
        """
        buy_price = Decimal(str(buy_price))
        wax_sell_price = Decimal(str(wax_sell_price))

        # Real Cost
        real_cost = buy_price

        # Net Revenue (Sell * (1 - SellFee) * (1 - CashoutFee))
        revenue_multiplier = (Decimal("1") - self.cfg.WAX_SELLING_FEE) * (
            Decimal("1") - self.cfg.WAX_CASHOUT_FEE
        )
        net_revenue = wax_sell_price * revenue_multiplier

        # Time Cost
        opp_cost = self.calculate_opportunity_cost(real_cost, days=hold_days)

        # Profit
        gross_profit = net_revenue - real_cost
        net_profit = gross_profit - opp_cost

        roi = (net_profit / real_cost * 100) if real_cost > 0 else Decimal("0")

        return {
            "real_cost": real_cost,
            "net_revenue": net_revenue.quantize(Decimal("0.01")),
            "opportunity_cost": opp_cost,
            "net_profit": net_profit.quantize(Decimal("0.01")),
            "roi_percent": roi.quantize(Decimal("0.01")),
        }

    def calculate_grind_profit(
        self,
        buy_price: float | Decimal,
        sell_price: float | Decimal,
        fee_rate: Optional[Decimal] = None,
    ) -> Dict[str, Decimal]:
        """
        Internal Flip Profit (GRIND).
        """
        buy_price = Decimal(str(buy_price))
        sell_price = Decimal(str(sell_price))
        fee = fee_rate if fee_rate is not None else self.cfg.DM_FEE_BOT

        net_revenue = sell_price * (Decimal("1") - fee)
        profit = net_revenue - buy_price

        roi = (profit / buy_price * 100) if buy_price > 0 else Decimal("0")

        return {
            "real_cost": buy_price,
            "net_revenue": net_revenue.quantize(Decimal("0.01")),
            "opportunity_cost": Decimal("0"),
            "net_profit": profit.quantize(Decimal("0.01")),
            "roi_percent": roi.quantize(Decimal("0.01")),
        }
