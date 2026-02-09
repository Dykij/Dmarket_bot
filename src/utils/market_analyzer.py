"""Advanced market analysis module for DMarket items.

This module provides tools for analyzing market data to detect trends, patterns, and
opportunities in DMarket prices, volumes, and sales history.
"""

import logging
import math
import operator
from datetime import datetime
from typing import Any

import numpy as np

# Logger
logger = logging.getLogger(__name__)

# Define classification constants
TREND_UP = "up"  # Upward price trend
TREND_DOWN = "down"  # Downward price trend
TREND_STABLE = "stable"  # Stable price trend
TREND_VOLATILE = "volatile"  # Volatile price trend

# Volatility levels
VOL_LOW = "low"
VOL_MEDIUM = "medium"
VOL_HIGH = "high"

# Market patterns
PATTERN_BREAKOUT = "breakout"  # Price breaking out of range
PATTERN_SUPPORT = "support"  # Price finding support level
PATTERN_RESISTANCE = "resistance"  # Price finding resistance level
PATTERN_REVERSAL = "reversal"  # Price trend reversal
PATTERN_FOMO = "fomo"  # Fear of missing out (rapid rise)
PATTERN_PANIC = "panic"  # Panic selling (rapid drop)
PATTERN_BOTTOMING = "bottoming"  # Price bottoming out
PATTERN_TOPPING = "topping"  # Price topping out


class MarketAnalyzer:
    """Advanced market analyzer for DMarket items.

    This class provides methods to analyze price history, detect patterns,
    and identify market opportunities.
    """

    def __init__(self, min_data_points: int = 5) -> None:
        """Initialize the market analyzer.

        Args:
            min_data_points: Minimum number of data points needed for analysis

        """
        self.min_data_points = min_data_points

    async def analyze_price_history(
        self,
        price_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze price history data to detect trends and patterns.

        Args:
            price_history: List of price data points in chronological order
                           Each point should have 'price' and 'timestamp' keys

        Returns:
            Dictionary containing analysis results

        """
        if not price_history or len(price_history) < self.min_data_points:
            return {
                "trend": TREND_STABLE,
                "confidence": 0.0,
                "volatility": VOL_LOW,
                "patterns": [],
                "support_level": None,
                "resistance_level": None,
                "price_change_24h": 0.0,
                "price_change_7d": 0.0,
                "avg_price": 0.0,
                "volume_change": 0.0,
                "insufficient_data": True,
            }

        # Extract price data and timestamps
        prices = [float(point.get("price", 0)) for point in price_history]
        timestamps = [point.get("timestamp", 0) for point in price_history]

        # Sort by timestamp if needed
        if not all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)):
            combined = sorted(zip(timestamps, prices, strict=False), key=operator.itemgetter(0))
            timestamps, prices = zip(*combined, strict=False)
            prices = list(prices)
            timestamps = list(timestamps)

        # Basic statistics
        current_price = prices[-1] if prices else 0
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        price_range = max_price - min_price

        # Calculate standard deviation for volatility
        std_dev = np.std(prices) if len(prices) > 1 else 0
        volatility_ratio = (std_dev / avg_price) if avg_price > 0 else 0

        # Determine volatility level
        volatility = VOL_LOW
        if volatility_ratio > 0.05:
            volatility = VOL_MEDIUM
        if volatility_ratio > 0.1:
            volatility = VOL_HIGH

        # Calculate price changes
        price_change_24h = 0.0
        price_change_7d = 0.0

        if len(prices) > 1:
            now = datetime.now().timestamp()
            day_ago = now - (24 * 60 * 60)
            week_ago = now - (7 * 24 * 60 * 60)

            # Find closest points to 24h and 7d ago
            day_ago_price = prices[0]
            week_ago_price = prices[0]

            for i, ts in enumerate(timestamps):
                if abs(ts - day_ago) < abs(
                    timestamps[prices.index(day_ago_price)] - day_ago,
                ):
                    day_ago_price = prices[i]
                if abs(ts - week_ago) < abs(
                    timestamps[prices.index(week_ago_price)] - week_ago,
                ):
                    week_ago_price = prices[i]

            # Calculate percentage changes
            if day_ago_price > 0:
                price_change_24h = ((current_price - day_ago_price) / day_ago_price) * 100
            if week_ago_price > 0:
                price_change_7d = ((current_price - week_ago_price) / week_ago_price) * 100

        # Trend analysis
        trend, confidence = self._analyze_trend(prices)

        # Pattern recognition
        patterns = self._detect_patterns(prices, timestamps)

        # Support and resistance levels
        support_level, resistance_level = self._find_support_resistance(prices)

        # Volume analysis if available
        volumes = [float(point.get("volume", 0)) for point in price_history if "volume" in point]
        volume_change = 0.0

        if len(volumes) > 1:
            volume_change = ((volumes[-1] - volumes[0]) / volumes[0]) * 100 if volumes[0] > 0 else 0

        return {
            "trend": trend,
            "confidence": confidence,
            "volatility": volatility,
            "volatility_ratio": volatility_ratio,
            "patterns": patterns,
            "support_level": support_level,
            "resistance_level": resistance_level,
            "current_price": current_price,
            "avg_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "price_range": price_range,
            "price_change_24h": price_change_24h,
            "price_change_7d": price_change_7d,
            "volume_change": volume_change,
            "insufficient_data": False,
        }

    def _analyze_trend(self, prices: list[float]) -> tuple[str, float]:
        """Analyze the trend in the price data.

        Args:
            prices: List of price points

        Returns:
            Tuple of (trend_type, confidence)

        """
        if len(prices) < self.min_data_points:
            return TREND_STABLE, 0.0

        # Use linear regression to determine trend
        x = np.array(range(len(prices)))
        y = np.array(prices)

        # Calculate slope and correlation coefficient
        n = len(prices)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_x_squared = sum(x**2)
        sum_xy = sum(x * y)

        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x**2)

        # Calculate Pearson correlation coefficient for confidence
        mean_x = sum_x / n
        mean_y = sum_y / n

        variance_x = sum((xi - mean_x) ** 2 for xi in x) / n
        variance_y = sum((yi - mean_y) ** 2 for yi in y) / n

        if variance_x == 0 or variance_y == 0:
            correlation = 0.0
        else:
            covariance = (
                sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=False)) / n
            )
            correlation = covariance / (math.sqrt(variance_x) * math.sqrt(variance_y))

        # Determine trend type
        confidence = abs(correlation)

        # Check for volatility vs stable trend
        price_range = max(prices) - min(prices)
        avg_price = sum(prices) / len(prices)
        relative_range = price_range / avg_price if avg_price > 0 else 0

        if relative_range > 0.15 and confidence < 0.7:
            return TREND_VOLATILE, confidence

        if slope > 0:
            return TREND_UP, confidence
        if slope < 0:
            return TREND_DOWN, confidence
        return TREND_STABLE, confidence

    def _detect_patterns(
        self,
        prices: list[float],
        timestamps: list[int],
    ) -> list[dict[str, Any]]:
        """Detect price patterns in the data.

        Args:
            prices: List of price points
            timestamps: List of timestamp values

        Returns:
            List of detected patterns with details

        """
        if len(prices) < self.min_data_points:
            return []

        patterns = []

        # Check for breakout
        if self._is_breakout(prices):
            patterns.append(
                {
                    "type": PATTERN_BREAKOUT,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_BREAKOUT,
                    ),
                    "description": "Price breaking out of previous range",
                },
            )

        # Check for reversal
        if self._is_reversal(prices):
            rev_type = "upward" if prices[-1] > prices[-2] else "downward"
            patterns.append(
                {
                    "type": PATTERN_REVERSAL,
                    "direction": rev_type,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_REVERSAL,
                    ),
                    "description": f"{rev_type.capitalize()} reversal pattern detected",
                },
            )

        # Check for FOMO (rapid rise)
        if self._is_fomo(prices):
            patterns.append(
                {
                    "type": PATTERN_FOMO,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_FOMO,
                    ),
                    "description": "Rapid price increase detected (FOMO)",
                },
            )

        # Check for panic selling
        if self._is_panic(prices):
            patterns.append(
                {
                    "type": PATTERN_PANIC,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_PANIC,
                    ),
                    "description": "Rapid price decrease detected (panic selling)",
                },
            )

        # Check for bottoming pattern
        if self._is_bottoming(prices):
            patterns.append(
                {
                    "type": PATTERN_BOTTOMING,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_BOTTOMING,
                    ),
                    "description": "Price appears to be bottoming out",
                },
            )

        # Check for topping pattern
        if self._is_topping(prices):
            patterns.append(
                {
                    "type": PATTERN_TOPPING,
                    "confidence": self._calculate_pattern_confidence(
                        prices,
                        PATTERN_TOPPING,
                    ),
                    "description": "Price appears to be forming a top",
                },
            )

        return patterns

    def _is_breakout(self, prices: list[float]) -> bool:
        """Check if the price is breaking out of a range."""
        if len(prices) < 10:
            return False

        # Use the last 75% of the data to establish the range
        range_end = int(len(prices) * 0.75)
        range_prices = prices[:range_end]

        range_max = max(range_prices)
        range_min = min(range_prices)
        range_size = range_max - range_min

        # Check if the last price is significantly outside the range
        last_price = prices[-1]

        if last_price > range_max + (range_size * 0.05):
            return True
        return last_price < range_min - range_size * 0.05

    def _is_reversal(self, prices: list[float]) -> bool:
        """Check if there's a trend reversal."""
        if len(prices) < 5:
            return False

        # Check for a trend direction change
        prev_trend = self._analyze_trend(prices[:-2])[0]
        current_trend = self._analyze_trend(prices[-5:])[0]

        return prev_trend not in {current_trend, TREND_STABLE}

    def _is_fomo(self, prices: list[float]) -> bool:
        """Check if there's a FOMO pattern (rapid rise)."""
        if len(prices) < 3:
            return False

        # Calculate rate of price change
        recent_prices = prices[-3:]
        if recent_prices[0] <= 0:
            return False

        change_percent = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100

        # FOMO defined as rapid price increase
        return change_percent > 15

    def _is_panic(self, prices: list[float]) -> bool:
        """Check if there's a panic selling pattern (rapid drop)."""
        if len(prices) < 3:
            return False

        # Calculate rate of price change
        recent_prices = prices[-3:]
        if recent_prices[0] <= 0:
            return False

        change_percent = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100

        # Panic defined as rapid price decrease
        return change_percent < -15

    def _is_bottoming(self, prices: list[float]) -> bool:
        """Check if the price is bottoming out."""
        if len(prices) < 5:
            return False

        # Look for a pattern where price has been decreasing but starts to stabilize
        recent_prices = prices[-5:]

        # Calculate slopes for first half and second half
        first_half_slope = (recent_prices[2] - recent_prices[0]) / 2
        second_half_slope = (recent_prices[4] - recent_prices[2]) / 2

        # Bottoming pattern: downward trend followed by stabilization or slight rise
        return first_half_slope < -0.02 and second_half_slope > -0.01

    def _is_topping(self, prices: list[float]) -> bool:
        """Check if the price is forming a top."""
        if len(prices) < 5:
            return False

        # Look for a pattern where price has been increasing but starts to stabilize
        recent_prices = prices[-5:]

        # Calculate slopes for first half and second half
        first_half_slope = (recent_prices[2] - recent_prices[0]) / 2
        second_half_slope = (recent_prices[4] - recent_prices[2]) / 2

        # Topping pattern: upward trend followed by stabilization or slight decline
        return first_half_slope > 0.02 and second_half_slope < 0.01

    def _calculate_pattern_confidence(
        self,
        prices: list[float],
        pattern_type: str,
    ) -> float:
        """Calculate confidence score for a detected pattern.

        Args:
            prices: List of price points
            pattern_type: Type of pattern

        Returns:
            Confidence score between 0.0 and 1.0

        """
        # Default base confidence
        confidence = 0.6

        # Adjust confidence based on data size
        if len(prices) < 10:
            confidence *= 0.8
        elif len(prices) > 20:
            confidence *= 1.2

        # Pattern-specific confidence adjustments
        if pattern_type == PATTERN_BREAKOUT:
            # Higher confidence for stronger breakouts
            range_end = int(len(prices) * 0.75)
            range_prices = prices[:range_end]
            range_max = max(range_prices)
            range_min = min(range_prices)
            range_size = range_max - range_min

            if range_size > 0:
                # How far beyond the range is the breakout
                breakout_strength = (
                    abs(
                        prices[-1] - (range_max if prices[-1] > range_max else range_min),
                    )
                    / range_size
                )
                confidence *= min(1 + breakout_strength, 1.5)

        elif pattern_type in {PATTERN_FOMO, PATTERN_PANIC}:
            # Higher confidence for more extreme moves
            change_rate = abs((prices[-1] - prices[-3]) / prices[-3]) if prices[-3] > 0 else 0
            confidence *= min(1 + change_rate, 1.5)

        elif pattern_type in {PATTERN_BOTTOMING, PATTERN_TOPPING}:
            # Higher confidence for clearer formations
            volatility = (
                np.std(prices[-5:]) / np.mean(prices[-5:]) if np.mean(prices[-5:]) > 0 else 0
            )
            confidence *= max(float(1 - volatility * 2), 0.6)

        # Cap confidence at 1.0
        return min(confidence, 1.0)

    def _find_support_resistance(
        self,
        prices: list[float],
    ) -> tuple[float | None, float | None]:
        """Find support and resistance levels in price data.

        Args:
            prices: List of price points

        Returns:
            Tuple of (support_level, resistance_level)

        """
        if len(prices) < self.min_data_points:
            return None, None

        # Use local min/max as potential support/resistance
        support_candidates = []
        resistance_candidates = []

        # Skip first and last point for local min/max detection
        for i in range(1, len(prices) - 1):
            # Local minimum (potential support)
            if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
                support_candidates.append(prices[i])

            # Local maximum (potential resistance)
            if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
                resistance_candidates.append(prices[i])

        # Process current price relative to historical levels
        current_price = prices[-1]

        # Find closest support below current price
        support_level = None
        min_distance = float("inf")

        for level in support_candidates:
            if level < current_price:
                distance = current_price - level
                if distance < min_distance:
                    min_distance = distance
                    support_level = level

        # Find closest resistance above current price
        resistance_level = None
        min_distance = float("inf")

        for level in resistance_candidates:
            if level > current_price:
                distance = level - current_price
                if distance < min_distance:
                    min_distance = distance
                    resistance_level = level

        return support_level, resistance_level


async def analyze_market_opportunity(
    item_data: dict[str, Any],
    price_history: list[dict[str, Any]],
    game: str,
) -> dict[str, Any]:
    """Analyze a market item for trading opportunities.

    Args:
        item_data: Current item data from DMarket
        price_history: Historical price data
        game: Game code (csgo, dota2, tf2, rust)

    Returns:
        Dictionary with opportunity analysis

    """
    analyzer = MarketAnalyzer()

    # Analyze price history
    analysis = await analyzer.analyze_price_history(price_history)

    # Get current price
    current_price = 0
    if "price" in item_data:
        if isinstance(item_data["price"], dict) and "amount" in item_data["price"]:
            current_price = float(item_data["price"]["amount"]) / 100
        elif isinstance(item_data["price"], int | float):
            current_price = float(item_data["price"])

    # Calculate opportunity score (0-100)
    opportunity_score = 0
    reasons = []

    # Base opportunity on trend and patterns
    if analysis["trend"] == TREND_UP:
        # Uptrend - good opportunity for selling
        opportunity_score += 20 * analysis["confidence"]
        reasons.append("Upward price trend")

        if PATTERN_TOPPING in [p["type"] for p in analysis["patterns"]]:
            opportunity_score += 15
            reasons.append("Potential price top forming (good sell point)")

    elif analysis["trend"] == TREND_DOWN:
        # Downtrend - potential buying opportunity
        opportunity_score += 10 * analysis["confidence"]

        if PATTERN_BOTTOMING in [p["type"] for p in analysis["patterns"]]:
            opportunity_score += 25
            reasons.append("Potential price bottom forming (good buy point)")

    # FOMO pattern - opportunity to sell
    if PATTERN_FOMO in [p["type"] for p in analysis["patterns"]]:
        opportunity_score += 30
        reasons.append("FOMO detected (potential selling opportunity)")

    # Panic pattern - opportunity to buy
    if PATTERN_PANIC in [p["type"] for p in analysis["patterns"]]:
        opportunity_score += 30
        reasons.append("Panic selling detected (potential buying opportunity)")

    # Breakout pattern - opportunity depends on direction
    breakout_patterns = [p for p in analysis["patterns"] if p["type"] == PATTERN_BREAKOUT]
    if breakout_patterns:
        if current_price > analysis["avg_price"]:
            # Upward breakout
            opportunity_score += 25
            reasons.append("Upward breakout detected (momentum trade)")
        else:
            # Downward breakout
            opportunity_score += 15
            reasons.append("Downward breakout detected (potential buy opportunity)")

    # Support/resistance proximity
    if analysis["support_level"] is not None:
        support_distance = (
            (current_price - analysis["support_level"]) / current_price if current_price > 0 else 0
        )
        if support_distance < 0.05 and support_distance > 0:
            # Price near support - potential buy
            opportunity_score += 20
            reasons.append(
                f"Price near support level (${analysis['support_level']:.2f})",
            )

    if analysis["resistance_level"] is not None:
        resistance_distance = (
            (analysis["resistance_level"] - current_price) / current_price
            if current_price > 0
            else 0
        )
        if resistance_distance < 0.05 and resistance_distance > 0:
            # Price near resistance - potential sell
            opportunity_score += 20
            reasons.append(
                f"Price near resistance level (${analysis['resistance_level']:.2f})",
            )

    # Volume changes can indicate opportunity
    if analysis["volume_change"] > 30:
        opportunity_score += 15
        reasons.append("Significant increase in trading volume")

    # Recent price changes
    if abs(analysis["price_change_24h"]) > 15:
        opportunity_score += 10
        if analysis["price_change_24h"] > 0:
            reasons.append(f"Price up {analysis['price_change_24h']:.1f}% in 24h")
        else:
            reasons.append(
                f"Price down {abs(analysis['price_change_24h']):.1f}% in 24h",
            )

    # Game-specific factors
    if game == "csgo":
        # CS:GO case items and collections tend to have better long-term value
        title = item_data.get("title", "").lower()
        if "case" in title or "collection" in title:
            opportunity_score += 5
            reasons.append("CS2 cases/collections tend to retain value")

    # Determine the opportunity type
    opportunity_type = "neutral"
    if opportunity_score >= 60:
        if current_price < analysis["avg_price"] or PATTERN_PANIC in [
            p["type"] for p in analysis["patterns"]
        ]:
            opportunity_type = "buy"
        else:
            opportunity_type = "sell"

    # Cap the score at 100
    opportunity_score = min(opportunity_score, 100)

    return {
        "item_name": item_data.get("title", "Unknown item"),
        "item_id": item_data.get("itemId", ""),
        "current_price": current_price,
        "game": game,
        "opportunity_score": opportunity_score,
        "opportunity_type": opportunity_type,
        "reasons": reasons,
        "market_analysis": analysis,
        "timestamp": datetime.now().timestamp(),
    }


async def batch_analyze_items(
    items: list[dict[str, Any]],
    price_histories: dict[str, list[dict[str, Any]]],
    game: str,
) -> list[dict[str, Any]]:
    """Analyze multiple items for market opportunities.

    Args:
        items: List of item data dictionaries
        price_histories: Dictionary mapping item_id to price history
        game: Game code

    Returns:
        List of opportunity analyses, sorted by opportunity score

    """
    results = []

    for item in items:
        item_id = item.get("itemId", "")
        if not item_id:
            continue

        history = price_histories.get(item_id, [])

        try:
            analysis = await analyze_market_opportunity(item, history, game)
            results.append(analysis)
        except Exception as e:
            logger.exception(f"Error analyzing item {item_id}: {e}")

    # Sort by opportunity score, highest first
    results.sort(key=operator.itemgetter("opportunity_score"), reverse=True)

    return results
