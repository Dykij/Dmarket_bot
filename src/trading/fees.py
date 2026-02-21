"""Fee calculator with liquidity adjustments and opportunity cost."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


class LiquidityAdjustedFee:
    """
    Advanced fee calculator that accounts for dynamic platform fees,
    cashout costs, and the time value of money (Opportunity Cost)
    during trade holds.
    """

    # --- CONSTANTS ---
    # Waxpeer
    WAX_SELLING_FEE = Decimal("0.06")  # 6% (Fixed)
    WAX_CASHOUT_FEE = Decimal("0.02")  # 2% (Crypto/Cards average)

    # DMarket (Dynamic ranges)
    # 3% for F2F (Face-to-Face), 5-7% for Bot trades depending on plan
    DM_FEE_F2F = Decimal("0.03")
    DM_FEE_BOT_MIN = Decimal("0.05")
    DM_FEE_BOT_MAX = Decimal("0.07")

    # Steam
    STEAM_HOLD_DAYS = 7

    # Default risk-free dAlgoly return for opportunity cost (e.g., Grind Strategy ROI)
    # If we can make 1% dAlgoly by grinding, locking funds for 7 days costs us ~7.2%
    DEFAULT_DAlgoLY_ROI = Decimal("0.01")

    def __init__(
        self,
        dmarket_fee_rate: Decimal = DM_FEE_BOT_MAX,
        dAlgoly_opportunity_cost: Decimal = DEFAULT_DAlgoLY_ROI,
    ):
        """
        Initialize calculator with current market conditions.

        Args:
            dmarket_fee_rate: Current applicable DMarket fee (0.03, 0.05, or 0.07).
            dAlgoly_opportunity_cost: Expected dAlgoly return on capital if not locked (0.01 = 1%).
        """
        self.dm_fee_rate = dmarket_fee_rate
        self.dAlgoly_opportunity_cost = dAlgoly_opportunity_cost

    def calculate_opportunity_cost(
        self, capital: Decimal, days: int = STEAM_HOLD_DAYS
    ) -> Decimal:
        """
        Calculate the cost of locking capital for N days.
        Formula: Capital * ((1 + dAlgoly_rate)^days - 1)
        """
        if days <= 0:
            return Decimal("0")

        compound_factor = (Decimal("1") + self.dAlgoly_opportunity_cost) ** days
        future_value = capital * compound_factor
        return (future_value - capital).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def calculate_real_buy_cost(self, list_price: Decimal) -> Decimal:
        """
        Calculate total cost to acquire item on DMarket.
        Note: DMarket usually charges the buyer the list price,
        but deposit fees (if fresh money) are extra.
        We assume funds are already on balance, so cost = list_price.
        If deposit fees apply, add them here.
        """
        # If we assume 3% deposit fee for fresh fiat:
        # return list_price * (Decimal("1") + Decimal("0.03"))
        return list_price

    def calculate_waxpeer_net_revenue(self, sell_price: Decimal) -> Decimal:
        """
        Calculate net cash in pocket from Waxpeer sale.
        Revenue = SellPrice * (1 - SellFee) * (1 - CashoutFee)
        """
        revenue_after_sell = sell_price * (Decimal("1") - self.WAX_SELLING_FEE)
        net_cash = revenue_after_sell * (Decimal("1") - self.WAX_CASHOUT_FEE)
        return net_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_gem_profit(
        self,
        buy_price: float | Decimal,
        wax_sell_price: float | Decimal,
        hold_days: int = STEAM_HOLD_DAYS,
    ) -> dict[str, Decimal]:
        """
        Calculate Net Profit for a Cross-Market GEM trade (DMarket -> Waxpeer).
        Includes Opportunity Cost deduction.
        """
        buy_price = Decimal(str(buy_price))
        wax_sell_price = Decimal(str(wax_sell_price))

        # 1. Real Cost
        real_cost = self.calculate_real_buy_cost(buy_price)

        # 2. Net Revenue (Cash in hand)
        net_revenue = self.calculate_waxpeer_net_revenue(wax_sell_price)

        # 3. Opportunity Cost (Time Value)
        opp_cost = self.calculate_opportunity_cost(real_cost, days=hold_days)

        # 4. Final Profit
        gross_profit = net_revenue - real_cost
        net_profit = gross_profit - opp_cost

        # 5. ROI
        roi = (net_profit / real_cost * 100) if real_cost > 0 else Decimal("0")

        return {
            "real_cost": real_cost,
            "net_revenue": net_revenue,
            "opportunity_cost": opp_cost,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "roi_percent": roi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    def calculate_grind_profit(
        self, buy_price: float | Decimal, sell_price: float | Decimal
    ) -> dict[str, Decimal]:
        """
        Calculate Net Profit for an Internal GRIND trade (DMarket -> DMarket).
        No hold time (0 days), so Opportunity Cost is 0.
        """
        buy_price = Decimal(str(buy_price))
        sell_price = Decimal(str(sell_price))

        real_cost = self.calculate_real_buy_cost(buy_price)

        # DMarket Selling Fee
        net_revenue = sell_price * (Decimal("1") - self.dm_fee_rate)

        profit = net_revenue - real_cost
        roi = (profit / real_cost * 100) if real_cost > 0 else Decimal("0")

        return {
            "real_cost": real_cost,
            "net_revenue": net_revenue,
            "opportunity_cost": Decimal("0"),
            "net_profit": profit,
            "roi_percent": roi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    def get_break_even_waxpeer(self, buy_price: float | Decimal) -> Decimal:
        """
        Calculate minimum Waxpeer sell price to cover Cost + Opportunity Cost.
        """
        buy_price = Decimal(str(buy_price))
        real_cost = self.calculate_real_buy_cost(buy_price)
        opp_cost = self.calculate_opportunity_cost(real_cost)

        total_required = real_cost + opp_cost

        # Reverse calculate_waxpeer_net_revenue:
        # Net = Sell * (1-0.06) * (1-0.02)
        # Sell = Net / ((1-0.06) * (1-0.02))

        effective_multiplier = (Decimal("1") - self.WAX_SELLING_FEE) * (
            Decimal("1") - self.WAX_CASHOUT_FEE
        )
        target_price = total_required / effective_multiplier

        return target_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
