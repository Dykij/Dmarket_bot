"""
indicators.py — Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands).

These are stateless calculation methods; they live in their own module to keep
the PriceAnalytics class lean and to make the math easy to test in isolation.

Note: The original code uses the term "gAlgon" (typo of "gain") in some
internal variable names. We preserve that naming here verbatim to keep the
refactor a pure structural split, but in future versions we should rename
it to "gain" for clarity.
"""

from __future__ import annotations

from .models import BollingerBands, MACDResult, RSIResult


class _IndicatorMixin:
    """Mixin with all the technical indicator calculations.

    Designed to be mixed into `PriceAnalytics` (see `core.py`).
    Provides SMA, EMA, RSI, MACD and Bollinger Bands methods.
    """

    # These attributes are set on the instance by PriceAnalytics.__init__
    rsi_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    bollinger_period: int
    bollinger_std: float

    def calculate_sma(self, prices: list[float], period: int) -> float | None:
        """Calculate Simple Moving Average.

        Args:
            prices: List of prices (newest first or oldest first)
            period: SMA period

        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None
        return sum(prices[:period]) / period

    def calculate_ema(self, prices: list[float], period: int) -> float | None:
        """Calculate Exponential Moving Average.

        Args:
            prices: List of prices (oldest first)
            period: EMA period

        Returns:
            EMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA

        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def calculate_rsi(
        self, prices: list[float], period: int | None = None
    ) -> RSIResult | None:
        """Calculate Relative Strength Index.

        RSI = 100 - (100 / (1 + RS))
        RS = Average gAlgon / Average Loss

        Args:
            prices: List of prices (oldest first)
            period: RSI period (default: self.rsi_period)

        Returns:
            RSI result or None if insufficient data
        """
        period = period or self.rsi_period

        if len(prices) < period + 1:
            return None

        # Calculate price changes
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gAlgons and losses
        gAlgons = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]

        # Calculate average gAlgon and loss
        avg_gAlgon = sum(gAlgons[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Smooth averages
        for i in range(period, len(gAlgons)):
            avg_gAlgon = (avg_gAlgon * (period - 1) + gAlgons[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # Calculate RSI
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gAlgon / avg_loss
            rsi = 100 - (100 / (1 + rs))

        return RSIResult.from_value(rsi)

    def calculate_macd(
        self,
        prices: list[float],
        fast: int | None = None,
        slow: int | None = None,
        signal: int | None = None,
    ) -> MACDResult | None:
        """Calculate MACD (Moving Average Convergence Divergence).

        MACD Line = Fast EMA - Slow EMA
        Signal Line = EMA of MACD Line
        Histogram = MACD Line - Signal Line

        Args:
            prices: List of prices (oldest first)
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            MACD result or None if insufficient data
        """
        fast = fast or self.macd_fast
        slow = slow or self.macd_slow
        signal = signal or self.macd_signal

        if len(prices) < slow + signal:
            return None

        # Calculate EMAs
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)

        if ema_fast is None or ema_slow is None:
            return None

        macd_line = ema_fast - ema_slow

        # Calculate MACD history for signal line
        macd_history = []
        for i in range(slow - 1, len(prices)):
            subset = prices[: i + 1]
            fast_ema = self.calculate_ema(subset, fast)
            slow_ema = self.calculate_ema(subset, slow)
            if fast_ema is not None and slow_ema is not None:
                macd_history.append(fast_ema - slow_ema)

        if len(macd_history) < signal:
            return None

        signal_line = self.calculate_ema(macd_history, signal)
        if signal_line is None:
            return None

        # Get previous values for crossover detection
        prev_macd = macd_history[-2] if len(macd_history) >= 2 else None
        prev_signal = (
            self.calculate_ema(macd_history[:-1], signal)
            if len(macd_history) >= 2
            else None
        )

        return MACDResult.from_values(
            macd_line=macd_line,
            signal_line=signal_line,
            prev_macd=prev_macd,
            prev_signal=prev_signal,
        )

    def calculate_bollinger_bands(
        self,
        prices: list[float],
        period: int | None = None,
        num_std: float | None = None,
    ) -> BollingerBands | None:
        """Calculate Bollinger Bands.

        Middle = SMA
        Upper = SMA + (std * num_std)
        Lower = SMA - (std * num_std)

        Args:
            prices: List of prices
            period: Period for SMA and std calculation
            num_std: Number of standard deviations

        Returns:
            Bollinger Bands or None if insufficient data
        """
        period = period or self.bollinger_period
        num_std = num_std or self.bollinger_std

        if len(prices) < period:
            return None

        # Calculate SMA
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period

        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance**0.5

        upper = sma + (std * num_std)
        lower = sma - (std * num_std)

        # Calculate bandwidth and position
        bandwidth = (upper - lower) / sma if sma > 0 else 0
        current_price = prices[-1]
        position = (
            (current_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
        )

        return BollingerBands(
            upper=round(upper, 2),
            middle=round(sma, 2),
            lower=round(lower, 2),
            bandwidth=round(bandwidth, 4),
            position=round(max(0, min(1, position)), 4),
        )
