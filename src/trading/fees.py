"""Fee calculator for cross-platform trading."""

from decimal import Decimal, ROUND_HALF_UP

class FeeCalculator:
    """Calculates fees, costs, and break-even prices for arbitrage."""

    # Constants (Fixed 2026 Rates)
    DM_DEPOSIT_FEE = Decimal("0.03")   # 3% deposit fee
    WAX_SELL_FEE = Decimal("0.06")     # 6% sales commission
    WAX_CASHOUT_FEE = Decimal("0.02")  # 2% cashout fee (crypto/cards)
    
    # Risk Premiums (Minimum ROI required to justify trade)
    RISK_PREMIUMS = {
        "csgo": Decimal("0.03"),  # 3% for 7-day trade lock risk
        "cs2": Decimal("0.03"),   # Alias
        "dota2": Decimal("0.00"), # No trade lock
        "rust": Decimal("0.00"),
        "tf2": Decimal("0.00"),
    }

    # Effective Multipliers
    # Cost Multiplier: 1 + 0.03 = 1.03
    COST_MULTIPLIER = Decimal("1") + DM_DEPOSIT_FEE
    
    # Revenue Multiplier: (1 - 0.06) * (1 - 0.02) = 0.94 * 0.98 = 0.9212
    REVENUE_MULTIPLIER = (Decimal("1") - WAX_SELL_FEE) * (Decimal("1") - WAX_CASHOUT_FEE)

    @classmethod
    def calculate_real_cost(cls, buy_price: float | Decimal) -> Decimal:
        """Calculate total cost to acquire item including deposit fees."""
        price = Decimal(str(buy_price))
        return price * cls.COST_MULTIPLIER

    @classmethod
    def calculate_net_revenue(cls, sell_price: float | Decimal) -> Decimal:
        """Calculate net cash in pocket after all sell/cashout fees."""
        price = Decimal(str(sell_price))
        return price * cls.REVENUE_MULTIPLIER

    @classmethod
    def calculate_profit(cls, buy_price: float | Decimal, sell_price: float | Decimal) -> Decimal:
        """Calculate pure profit (Net Revenue - Real Cost)."""
        real_cost = cls.calculate_real_cost(buy_price)
        net_revenue = cls.calculate_net_revenue(sell_price)
        return net_revenue - real_cost

    @classmethod
    def calculate_break_even(cls, buy_price: float | Decimal, game: str = "csgo") -> Decimal:
        """
        Calculate minimum sell price on Waxpeer to break even (0 profit).
        
        Note: Game parameter is kept for interface consistency but strict 
        break-even is mathematically game-agnostic. 
        Use calculate_target_price for risk-adjusted targets.
        """
        real_cost = cls.calculate_real_cost(buy_price)
        # Break Even: Net Revenue = Real Cost
        # Sell * 0.9212 = Real Cost
        # Sell = Real Cost / 0.9212
        return (real_cost / cls.REVENUE_MULTIPLIER).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_target_price(cls, buy_price: float | Decimal, game: str = "csgo", min_profit: float = 0.0) -> Decimal:
        """
        Calculate target sell price including risk premium and desired profit.
        
        Args:
            buy_price: Purchase price on DMarket
            game: Game identifier (affects risk premium)
            min_profit: Additional desired profit % (e.g. 0.05 for 5%)
        """
        real_cost = cls.calculate_real_cost(buy_price)
        risk = cls.RISK_PREMIUMS.get(game.lower(), Decimal("0.00"))
        
        # We need to cover Cost + Risk + Desired Profit
        # Target Revenue = Cost * (1 + Risk + Profit)
        target_revenue = real_cost * (Decimal("1") + risk + Decimal(str(min_profit)))
        
        return (target_revenue / cls.REVENUE_MULTIPLIER).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
