"""Analytics and visualization utilities for DMarket Bot.

This module provides functions for generating charts, analyzing market data,
and creating visualizations for Telegram bot responses.
"""

import io
from typing import Any

import matplotlib as mpl

mpl.use("Agg")  # Use non-interactive backend
import logging

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

# Configure matplotlib and seaborn
try:
    plt.style.use("seaborn-v0_8")
except OSError:
    # Fallback to default style if seaborn not available
    plt.style.use("default")
sns.set_palette("husl")


class ChartGenerator:
    """Utility class for generating charts and visualizations."""

    def __init__(self, style: str = "default", figsize: tuple[int, int] = (12, 8)) -> None:
        """Initialize chart generator.

        Args:
            style: Matplotlib style to use (default, bmh, ggplot)
            figsize: Default figure size

        """
        self.style = style
        self.figsize = figsize
        try:
            plt.style.use(style)
        except OSError:
            plt.style.use("default")

    def create_price_history_chart(
        self,
        price_data: list[dict[str, Any]],
        title: str = "Price History",
        currency: str = "USD",
    ) -> io.BytesIO:
        """Create a price history chart.

        Args:
            price_data: List of price data points with 'date' and 'price' keys
            title: Chart title
            currency: Currency symbol

        Returns:
            BytesIO: Chart image as bytes

        """
        try:
            # Create DataFrame
            df = pd.DataFrame(price_data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize)

            # Plot price line
            ax.plot(
                df["date"],
                df["price"],
                linewidth=2,
                color="#2E86AB",
                marker="o",
                markersize=4,
            )

            # Customize chart
            ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("Date", fontsize=12)
            ax.set_ylabel(f"Price ({currency})", fontsize=12)
            ax.grid(True, alpha=0.3)

            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.xticks(rotation=45)

            # Add price range annotation
            min_price = df["price"].min()
            max_price = df["price"].max()
            price_range = max_price - min_price

            if price_range > 0:
                ax.axhline(
                    y=min_price,
                    color="red",
                    linestyle="--",
                    alpha=0.5,
                    label=f"Min: ${min_price:.2f}",
                )
                ax.axhline(
                    y=max_price,
                    color="green",
                    linestyle="--",
                    alpha=0.5,
                    label=f"Max: ${max_price:.2f}",
                )
                ax.legend()

            # Tight layout and save
            plt.tight_layout()

            # Save to BytesIO
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
            img_buffer.seek(0)
            plt.close(fig)

            return img_buffer

        except Exception as e:
            logger.exception(f"Error creating price history chart: {e}")
            return self._create_error_chart("Failed to generate price chart")

    def create_market_overview_chart(
        self,
        items_data: list[dict[str, Any]],
        title: str = "Market Overview",
    ) -> io.BytesIO:
        """Create a market overview chart with top items by price.

        Args:
            items_data: List of item data with 'name' and 'price' keys
            title: Chart title

        Returns:
            BytesIO: Chart image as bytes

        """
        try:
            # Limit to top 10 items
            sorted_items = sorted(
                items_data,
                key=lambda x: x.get("price", 0),
                reverse=True,
            )[:10]

            if not sorted_items:
                return self._create_error_chart("No data available")

            # Create DataFrame
            df = pd.DataFrame(sorted_items)

            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize)

            # Create horizontal bar chart
            bars = ax.barh(range(len(df)), df["price"], color="#A23B72")

            # Customize chart
            ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("Price (USD)", fontsize=12)
            ax.set_ylabel("Items", fontsize=12)

            # Set y-tick labels to item names (truncated)
            item_names = [name[:30] + "..." if len(name) > 30 else name for name in df["name"]]
            ax.set_yticks(range(len(df)))
            ax.set_yticklabels(item_names)

            # Add value labels on bars
            for bar in bars:
                width = bar.get_width()
                ax.text(
                    width,
                    bar.get_y() + bar.get_height() / 2,
                    f"${width:.2f}",
                    ha="left",
                    va="center",
                    fontweight="bold",
                )

            # Tight layout
            plt.tight_layout()

            # Save to BytesIO
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
            img_buffer.seek(0)
            plt.close(fig)

            return img_buffer

        except Exception as e:
            logger.exception(f"Error creating market overview chart: {e}")
            return self._create_error_chart("Failed to generate market chart")

    def create_arbitrage_opportunities_chart(
        self,
        opportunities: list[dict[str, Any]],
        title: str = "Arbitrage Opportunities",
    ) -> io.BytesIO:
        """Create an arbitrage opportunities chart.

        Args:
            opportunities: List of arbitrage opportunities
            title: Chart title

        Returns:
            BytesIO: Chart image as bytes

        """
        try:
            if not opportunities:
                return self._create_error_chart("No arbitrage opportunities found")

            # Create DataFrame
            df = pd.DataFrame(opportunities)
            df = df.head(10)  # Top 10 opportunities

            # Create figure with subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

            # Chart 1: Profit amounts
            bars1 = ax1.bar(range(len(df)), df["profit_amount"], color="#F18F01")
            ax1.set_title("Profit Amount (USD)", fontsize=14, fontweight="bold")
            ax1.set_ylabel("Profit (USD)", fontsize=12)
            ax1.set_xlabel("Opportunity Index", fontsize=12)

            # Add value labels
            for bar in bars1:
                height = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"${height:.2f}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                )

            # Chart 2: Profit percentages
            bars2 = ax2.bar(range(len(df)), df["profit_percentage"], color="#C73E1D")
            ax2.set_title("Profit Percentage", fontsize=14, fontweight="bold")
            ax2.set_ylabel("Profit (%)", fontsize=12)
            ax2.set_xlabel("Opportunity Index", fontsize=12)

            # Add percentage labels
            for bar in bars2:
                height = bar.get_height()
                ax2.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:.1f}%",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                )

            # Overall title
            fig.suptitle(title, fontsize=16, fontweight="bold")

            # Tight layout
            plt.tight_layout()

            # Save to BytesIO
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
            img_buffer.seek(0)
            plt.close(fig)

            return img_buffer

        except Exception as e:
            logger.exception(f"Error creating arbitrage chart: {e}")
            return self._create_error_chart("Failed to generate arbitrage chart")

    def create_volume_analysis_chart(
        self,
        volume_data: list[dict[str, Any]],
        title: str = "Trading Volume Analysis",
    ) -> io.BytesIO:
        """Create a trading volume analysis chart.

        Args:
            volume_data: List of volume data with 'date' and 'volume' keys
            title: Chart title

        Returns:
            BytesIO: Chart image as bytes

        """
        try:
            # Create DataFrame
            df = pd.DataFrame(volume_data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize)

            # Plot volume bars
            ax.bar(df["date"], df["volume"], color="#3A86FF", alpha=0.7, width=0.8)

            # Add trend line
            z = np.polyfit(mdates.date2num(df["date"]), df["volume"], 1)
            p = np.poly1d(z)
            ax.plot(
                df["date"],
                p(mdates.date2num(df["date"])),
                color="red",
                linewidth=2,
                linestyle="--",
                alpha=0.8,
                label="Trend",
            )

            # Customize chart
            ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("Date", fontsize=12)
            ax.set_ylabel("Trading Volume", fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend()

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            plt.xticks(rotation=45)

            # Tight layout
            plt.tight_layout()

            # Save to BytesIO
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
            img_buffer.seek(0)
            plt.close(fig)

            return img_buffer

        except Exception as e:
            logger.exception(f"Error creating volume analysis chart: {e}")
            return self._create_error_chart("Failed to generate volume chart")

    def _create_error_chart(self, error_message: str) -> io.BytesIO:
        """Create a simple error chart.

        Args:
            error_message: Error message to display

        Returns:
            BytesIO: Error chart image as bytes

        """
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(
                0.5,
                0.5,
                error_message,
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                fontweight="bold",
                color="red",
                transform=ax.transAxes,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")

            # Save to BytesIO
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
            img_buffer.seek(0)
            plt.close(fig)

            return img_buffer
        except (OSError, ValueError, RuntimeError):
            # If even error chart fails, return empty BytesIO
            return io.BytesIO()


class MarketAnalyzer:
    """Market data analysis utilities."""

    @staticmethod
    def calculate_price_statistics(price_data: list[float]) -> dict[str, float]:
        """Calculate price statistics.

        Args:
            price_data: List of prices

        Returns:
            Dict with statistics (mean, median, std, min, max, etc.)

        """
        if not price_data:
            return {}

        prices = np.array(price_data)

        return {
            "mean": float(np.mean(prices)),
            "median": float(np.median(prices)),
            "std": float(np.std(prices)),
            "min": float(np.min(prices)),
            "max": float(np.max(prices)),
            "q25": float(np.percentile(prices, 25)),
            "q75": float(np.percentile(prices, 75)),
            "range": float(np.max(prices) - np.min(prices)),
            "cv": (float(np.std(prices) / np.mean(prices)) if np.mean(prices) != 0 else 0),
        }

    @staticmethod
    def detect_price_trends(
        price_data: list[dict[str, Any]],
        window: int = 5,
    ) -> dict[str, Any]:
        """Detect price trends using moving averages.

        Args:
            price_data: List of price data with 'date' and 'price' keys
            window: Moving average window size

        Returns:
            Dict with trend analysis

        """
        if len(price_data) < window:
            return {"trend": "insufficient_data", "confidence": 0.0}

        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # Calculate moving averages
        df["ma_short"] = df["price"].rolling(window=max(3, window // 2)).mean()
        df["ma_long"] = df["price"].rolling(window=window).mean()

        # Determine trend
        latest_short = df["ma_short"].iloc[-1]
        latest_long = df["ma_long"].iloc[-1]

        if pd.isna(latest_short) or pd.isna(latest_long):
            return {"trend": "insufficient_data", "confidence": 0.0}

        # Calculate trend strength
        price_change = (df["price"].iloc[-1] - df["price"].iloc[0]) / df["price"].iloc[0]
        trend_strength = abs(price_change)

        if latest_short > latest_long * 1.02:  # 2% threshold
            trend = "upward"
        elif latest_short < latest_long * 0.98:  # 2% threshold
            trend = "downward"
        else:
            trend = "sideways"

        return {
            "trend": trend,
            "confidence": min(trend_strength * 100, 100.0),
            "price_change_percent": price_change * 100,
            "latest_price": df["price"].iloc[-1],
            "ma_short": latest_short,
            "ma_long": latest_long,
        }

    @staticmethod
    def find_support_resistance(
        price_data: list[float],
        window: int = 5,
    ) -> dict[str, list[float]]:
        """Find support and resistance levels.

        Args:
            price_data: List of prices
            window: Window size for local minima/maxima detection

        Returns:
            Dict with support and resistance levels

        """
        if len(price_data) < window * 2:
            return {"support": [], "resistance": []}

        prices = np.array(price_data)

        # Find local minima (potential support)
        support_candidates = []
        for i in range(window, len(prices) - window):
            if all(prices[i] <= prices[i - j] for j in range(1, window + 1)) and all(
                prices[i] <= prices[i + j] for j in range(1, window + 1)
            ):
                support_candidates.append(prices[i])

        # Find local maxima (potential resistance)
        resistance_candidates = []
        for i in range(window, len(prices) - window):
            if all(prices[i] >= prices[i - j] for j in range(1, window + 1)) and all(
                prices[i] >= prices[i + j] for j in range(1, window + 1)
            ):
                resistance_candidates.append(prices[i])

        # Filter levels by minimum touches (simplified)
        support_levels = list(set(support_candidates))
        resistance_levels = list(set(resistance_candidates))

        return {
            "support": sorted(support_levels)[:5],  # Top 5 support levels
            "resistance": sorted(resistance_levels, reverse=True)[:5],  # Top 5 resistance levels
        }


async def generate_market_report(
    chart_generator: ChartGenerator,
    market_data: dict[str, Any],
    title: str = "Market Report",
) -> list[io.BytesIO]:
    """Generate comprehensive market report with multiple charts.

    Args:
        chart_generator: Chart generator instance
        market_data: Market data containing various metrics
        title: Report title

    Returns:
        List of chart images as BytesIO objects

    """
    charts = []

    try:
        # Generate price history chart if available
        if "price_history" in market_data:
            price_chart = chart_generator.create_price_history_chart(
                market_data["price_history"],
                f"{title} - Price History",
            )
            charts.append(price_chart)

        # Generate market overview chart if available
        if "top_items" in market_data:
            market_chart = chart_generator.create_market_overview_chart(
                market_data["top_items"],
                f"{title} - Top Items",
            )
            charts.append(market_chart)

        # Generate arbitrage chart if available
        if "arbitrage_opportunities" in market_data:
            arbitrage_chart = chart_generator.create_arbitrage_opportunities_chart(
                market_data["arbitrage_opportunities"],
                f"{title} - Arbitrage Opportunities",
            )
            charts.append(arbitrage_chart)

        # Generate volume chart if available
        if "volume_data" in market_data:
            volume_chart = chart_generator.create_volume_analysis_chart(
                market_data["volume_data"],
                f"{title} - Volume Analysis",
            )
            charts.append(volume_chart)

    except Exception as e:
        logger.exception(f"Error generating market report: {e}")

    return charts
