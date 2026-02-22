"""Market data visualization module for DMarket.

This module provides utilities for creating visual representations of market data:
- Price trend charts
- Volume analysis
- Support/resistance levels
- Pattern detection visualization
- Market comparisons
- Supply/demand heat maps
"""

import io
import logging
from datetime import datetime
from typing import Any

import matplotlib as mpl

mpl.use("Agg")  # Non-interactive backend for server use
import contextlib
import operator

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle
from PIL import Image, ImageDraw, ImageFont

# Logger
logger = logging.getLogger(__name__)


class MarketVisualizer:
    """Creates visual representations of market data for analysis."""

    def __init__(self, theme: str = "dark") -> None:
        """Initialize the market visualizer.

        Args:
            theme: Chart theme ('dark' or 'light')

        """
        self.theme = theme
        self.setup_plot_style()

    def setup_plot_style(self) -> None:
        """Set up matplotlib plot style based on theme."""
        if self.theme == "dark":
            plt.style.use("dark_background")
            self.text_color = "white"
            self.grid_color = "#333333"
            self.up_color = "#00ff9f"  # Green for price increases
            self.down_color = "#ff5757"  # Red for price decreases
            self.neutral_color = "#aaaaaa"  # Gray for neutral
            self.volume_color = "#3498db"  # Blue for volume
            self.highlight_color = "#ffcc00"  # Yellow for highlights
        else:
            plt.style.use("seaborn-v0_8-whitegrid")
            self.text_color = "black"
            self.grid_color = "#dddddd"
            self.up_color = "#00aa5e"  # Green for price increases
            self.down_color = "#d63031"  # Red for price decreases
            self.neutral_color = "#636e72"  # Gray for neutral
            self.volume_color = "#0984e3"  # Blue for volume
            self.highlight_color = "#e67e22"  # Orange for highlights

    async def create_price_chart(
        self,
        price_history: list[dict[str, Any]],
        item_name: str,
        game: str,
        include_volume: bool = True,
        width: int = 800,
        height: int = 600,
    ) -> io.BytesIO:
        """Create a price chart for an item.

        Args:
            price_history: List of price data points
            item_name: Item name
            game: Game code
            include_volume: Whether to include volume data
            width: Image width
            height: Image height

        Returns:
            BytesIO object containing the chart image

        """
        if not price_history:
            # Create empty chart with message
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
            ax.text(
                0.5,
                0.5,
                "No price data avAlgolable",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                fontsize=14,
                color=self.text_color,
            )
            ax.set_axis_off()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf

        # Process data
        df = self.process_price_data(price_history)

        # Create figure with appropriate subplot layout
        ax2 = None  # Initialize ax2 for type checker
        if include_volume and "volume" in df.columns:
            fig, (ax1, ax2) = plt.subplots(
                2,
                1,
                figsize=(width / 100, height / 100),
                gridspec_kw={"height_ratios": [3, 1]},
                dpi=100,
            )
            fig.subplots_adjust(hspace=0)
        else:
            fig, ax1 = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

        # Plot price
        ax1.plot(df.index, df["price"], color=self.neutral_color, linewidth=2)

        # Color regions based on trend
        self.color_trend_regions(ax1, df)

        # Add support/resistance lines if we have enough data
        if len(df) >= 10:
            self.add_support_resistance(ax1, df)

        # Format main axis
        ax1.set_title(
            f"{item_name} - Price History",
            fontsize=14,
            color=self.text_color,
        )
        ax1.grid(axis="y", linestyle="--", alpha=0.3, color=self.grid_color)
        ax1.set_ylabel("Price (USD)", color=self.text_color)

        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

        # Add volume subplot if requested and avAlgolable
        if include_volume and "volume" in df.columns and ax2 is not None:
            # Plot volume as bar chart
            ax2.bar(
                df.index,
                df["volume"],
                color=self.volume_color,
                alpha=0.7,
                width=0.8,
            )

            # Format volume axis
            ax2.set_ylabel("Volume", color=self.text_color)
            ax2.grid(axis="y", linestyle="--", alpha=0.3, color=self.grid_color)
            ax2.set_xlabel("Date", color=self.text_color)

            # Format x-axis dates on volume subplot
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")

            # Make sure the x-axes align
            ax1.set_xticklabels([])  # Remove x labels from top plot
            ax1.set_xlim(ax2.get_xlim())  # Match x range
        else:
            ax1.set_xlabel("Date", color=self.text_color)

        # Add game info and current stats
        current_price = df["price"].iloc[-1] if not df.empty else 0
        min_price = df["price"].min() if not df.empty else 0
        max_price = df["price"].max() if not df.empty else 0

        game_names = {
            "csgo": "CS2",
            "dota2": "Dota 2",
            "tf2": "Team Fortress 2",
            "rust": "Rust",
        }
        game_name = game_names.get(game, game)

        stats_text = f"{game_name} | Current: ${current_price:.2f} | Min: ${min_price:.2f} | Max: ${max_price:.2f}"
        fig.text(0.5, 0.01, stats_text, ha="center", color=self.text_color, fontsize=10)

        # Save to buffer
        buf = io.BytesIO()
        fig.tight_layout(
            rect=[0, 0.03, 1, 0.95],
        )  # Adjust layout to make room for stats text
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return buf

    async def create_market_comparison_chart(
        self,
        items_data: list[dict[str, Any]],
        price_histories: dict[str, list[dict[str, Any]]],
        width: int = 800,
        height: int = 600,
    ) -> io.BytesIO:
        """Create a chart comparing multiple items.

        Args:
            items_data: List of item data
            price_histories: Dictionary mapping item IDs to price histories
            width: Image width
            height: Image height

        Returns:
            BytesIO object containing the chart image

        """
        if not items_data or not price_histories:
            # Create empty chart with message
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
            ax.text(
                0.5,
                0.5,
                "No comparison data avAlgolable",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                fontsize=14,
                color=self.text_color,
            )
            ax.set_axis_off()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf

        # Create figure
        fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

        # Plot each item's price history
        for i, item in enumerate(items_data):
            item_id = item.get("itemId")
            if not item_id or item_id not in price_histories:
                continue

            # Process data
            history = price_histories[item_id]
            if not history:
                continue

            df = self.process_price_data(history)

            # Normalize prices to percentage change from first day for fAlgor comparison
            if not df.empty:
                first_price = df["price"].iloc[0]
                if first_price > 0:
                    normalized = ((df["price"] / first_price) - 1) * 100
                    ax.plot(
                        df.index,
                        normalized,
                        linewidth=2,
                        label=item.get("title", f"Item {i + 1}"),
                    )

        # Format the chart
        ax.set_title("Price Comparison (% Change)", fontsize=14, color=self.text_color)
        ax.grid(linestyle="--", alpha=0.3, color=self.grid_color)
        ax.set_ylabel("Price Change (%)", color=self.text_color)
        ax.set_xlabel("Date", color=self.text_color)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        # Add reference line at 0%
        ax.axhline(y=0, color=self.neutral_color, linestyle="-", alpha=0.3)

        # Add legend
        ax.legend(loc="best", framealpha=0.7)

        # Save to buffer
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return buf

    async def create_pattern_visualization(
        self,
        price_history: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
        item_name: str,
        width: int = 800,
        height: int = 500,
    ) -> io.BytesIO:
        """Create a chart highlighting detected patterns.

        Args:
            price_history: List of price data points
            patterns: List of detected patterns
            item_name: Item name
            width: Image width
            height: Image height

        Returns:
            BytesIO object containing the chart image

        """
        if not price_history or not patterns:
            # Create empty chart with message
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
            ax.text(
                0.5,
                0.5,
                "No pattern data avAlgolable",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                fontsize=14,
                color=self.text_color,
            )
            ax.set_axis_off()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf

        # Process data
        df = self.process_price_data(price_history)

        # Create figure
        fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)

        # Plot price
        ax.plot(df.index, df["price"], color=self.neutral_color, linewidth=2)

        # Add pattern highlights
        pattern_areas = []
        annotations = []

        for pattern in patterns:
            pattern_type = pattern.get("type", "")
            confidence = pattern.get("confidence", 0.5)

            # Only show patterns with reasonable confidence
            if confidence < 0.5:
                continue

            # Determine pattern region
            # For simplicity, we'll highlight the last 20% of the data for most patterns
            start_idx = int(len(df) * 0.8)
            end_idx = len(df) - 1

            color = self.highlight_color
            if pattern_type == "reversal":
                color = (
                    self.up_color
                    if pattern.get("direction") == "upward"
                    else self.down_color
                )
            elif pattern_type == "fomo":
                color = self.up_color
            elif pattern_type == "panic":
                color = self.down_color

            # Add pattern highlight
            pattern_areas.append(
                {
                    "start": df.index[start_idx],
                    "end": df.index[end_idx],
                    "min_price": df["price"].iloc[start_idx : end_idx + 1].min() * 0.98,
                    "max_price": df["price"].iloc[start_idx : end_idx + 1].max() * 1.02,
                    "color": color,
                    "alpha": min(0.3, confidence * 0.4),  # Scale alpha with confidence
                    "pattern": pattern_type,
                },
            )

            # Add pattern label
            annotations.append(
                {
                    "x": df.index[end_idx - 3],  # Place label near the end
                    "y": df["price"].iloc[end_idx - 3],
                    "text": pattern_type.replace("_", " ").title(),
                    "color": color,
                },
            )

        # Draw pattern highlights
        for area in pattern_areas:
            rect = Rectangle(
                (mdates.date2num(area["start"]), area["min_price"]),
                mdates.date2num(area["end"]) - mdates.date2num(area["start"]),
                area["max_price"] - area["min_price"],
                facecolor=area["color"],
                alpha=area["alpha"],
                edgecolor="none",
                zorder=1,
            )
            ax.add_patch(rect)

        # Add pattern labels
        for annotation in annotations:
            ax.annotate(
                annotation["text"],
                xy=(annotation["x"], annotation["y"]),
                xytext=(10, 10),
                textcoords="offset points",
                color=annotation["color"],
                fontsize=10,
                fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": annotation["color"]},
            )

        # Format the chart
        ax.set_title(
            f"{item_name} - Pattern Detection",
            fontsize=14,
            color=self.text_color,
        )
        ax.grid(linestyle="--", alpha=0.3, color=self.grid_color)
        ax.set_ylabel("Price (USD)", color=self.text_color)
        ax.set_xlabel("Date", color=self.text_color)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        # Add legend for patterns
        pattern_types = {area["pattern"] for area in pattern_areas}
        handles = [
            Rectangle((0, 0), 1, 1, color=self.highlight_color, alpha=0.3)
            for _ in pattern_types
        ]
        labels = [p.replace("_", " ").title() for p in pattern_types]
        if handles and labels:
            ax.legend(handles, labels, loc="upper left", title="Patterns")

        # Save to buffer
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return buf

    async def create_market_summary_image(
        self,
        item_data: dict[str, Any],
        analysis: dict[str, Any],
        width: int = 800,
        height: int = 400,
    ) -> io.BytesIO:
        """Create a summary image with key market stats.

        Args:
            item_data: Item data
            analysis: Market analysis data
            width: Image width
            height: Image height

        Returns:
            BytesIO object containing the image

        """
        # Create image with background color
        bg_color = (25, 25, 25) if self.theme == "dark" else (245, 245, 245)
        text_color = (255, 255, 255) if self.theme == "dark" else (30, 30, 30)

        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Try to load a font, fall back to default if not avAlgolable
        try:
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_medium = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            # Use default font
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Get item data
        item_name = item_data.get("title", "Unknown Item")
        current_price = 0
        if "price" in item_data:
            if isinstance(item_data["price"], dict) and "amount" in item_data["price"]:
                current_price = float(item_data["price"]["amount"]) / 100
            elif isinstance(item_data["price"], int | float):
                current_price = float(item_data["price"])

        # Draw item name
        draw.text((20, 20), item_name, font=font_large, fill=text_color)

        # Draw current price
        draw.text(
            (20, 60),
            f"Current Price: ${current_price:.2f}",
            font=font_medium,
            fill=text_color,
        )

        # Add market analysis
        y_pos = 100

        # Trend
        trend = analysis.get("trend", "stable")
        trend_color = (
            (0, 200, 100)
            if trend == "up"
            else (255, 80, 80) if trend == "down" else (170, 170, 170)
        )
        draw.text(
            (20, y_pos),
            f"Trend: {trend.title()}",
            font=font_medium,
            fill=trend_color,
        )
        y_pos += 30

        # Price changes
        price_change_24h = analysis.get("price_change_24h", 0)
        price_change_7d = analysis.get("price_change_7d", 0)

        price_24h_color = (
            (0, 200, 100)
            if price_change_24h > 0
            else (255, 80, 80) if price_change_24h < 0 else text_color
        )
        price_7d_color = (
            (0, 200, 100)
            if price_change_7d > 0
            else (255, 80, 80) if price_change_7d < 0 else text_color
        )

        draw.text(
            (20, y_pos),
            f"24h Change: {price_change_24h:+.2f}%",
            font=font_small,
            fill=price_24h_color,
        )
        y_pos += 25
        draw.text(
            (20, y_pos),
            f"7d Change: {price_change_7d:+.2f}%",
            font=font_small,
            fill=price_7d_color,
        )
        y_pos += 35

        # Volatility
        volatility = analysis.get("volatility", "low")
        volatility_color = (
            (170, 170, 170)
            if volatility == "low"
            else (255, 170, 0) if volatility == "medium" else (255, 80, 80)
        )
        draw.text(
            (20, y_pos),
            f"Volatility: {volatility.title()}",
            font=font_small,
            fill=volatility_color,
        )
        y_pos += 35

        # Support/Resistance levels
        support = analysis.get("support_level")
        resistance = analysis.get("resistance_level")

        if support is not None:
            draw.text(
                (20, y_pos),
                f"Support: ${support:.2f}",
                font=font_small,
                fill=text_color,
            )
            y_pos += 25

        if resistance is not None:
            draw.text(
                (20, y_pos),
                f"Resistance: ${resistance:.2f}",
                font=font_small,
                fill=text_color,
            )
            y_pos += 35

        # Patterns detected
        patterns = analysis.get("patterns", [])
        if patterns:
            draw.text(
                (20, y_pos),
                "Patterns Detected:",
                font=font_small,
                fill=text_color,
            )
            y_pos += 25

            for _i, pattern in enumerate(patterns[:3]):  # Show top 3 patterns
                pattern_type = pattern.get("type", "").replace("_", " ").title()
                confidence = pattern.get("confidence", 0) * 100

                draw.text(
                    (30, y_pos),
                    f"• {pattern_type} ({confidence:.0f}%)",
                    font=font_small,
                    fill=text_color,
                )
                y_pos += 25

        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text(
            (width - 200, height - 30),
            f"Generated: {timestamp}",
            font=font_small,
            fill=text_color,
        )

        # Save to buffer
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return buf

    def process_price_data(self, price_history: list[dict[str, Any]]) -> pd.DataFrame:
        """Process price history data into a pandas DataFrame.

        Args:
            price_history: List of price data points

        Returns:
            Processed DataFrame with datetime index

        """
        # Extract data
        dates = []
        prices = []
        volumes = []

        for point in price_history:
            # Get timestamp
            if "timestamp" in point:
                timestamp = point["timestamp"]
                if isinstance(timestamp, str):
                    # Try to parse string timestamp
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp,
                        )
                    except ValueError:
                        try:
                            timestamp = datetime.fromtimestamp(float(timestamp))
                        except ValueError:
                            continue
                elif isinstance(timestamp, int | float):
                    timestamp = datetime.fromtimestamp(timestamp)
                else:
                    continue
            else:
                continue

            # Get price
            price = None
            if "price" in point:
                if isinstance(point["price"], dict) and "amount" in point["price"]:
                    price = float(point["price"]["amount"]) / 100
                elif isinstance(point["price"], int | float):
                    price = float(point["price"])
                elif isinstance(point["price"], str):
                    with contextlib.suppress(ValueError):
                        price = float(point["price"])

            if price is None:
                continue

            # Get volume if avAlgolable
            volume = None
            if "volume" in point:
                with contextlib.suppress(ValueError, TypeError):
                    volume = float(point["volume"])

            # Add to lists
            dates.append(timestamp)
            prices.append(price)
            if volume is not None:
                volumes.append(volume)

        # Create DataFrame
        data = {"price": prices}
        if volumes and len(volumes) == len(prices):
            data["volume"] = volumes

        df = pd.DataFrame(data, index=dates)

        # Sort by date
        return df.sort_index()

    def color_trend_regions(self, ax, df: pd.DataFrame) -> None:
        """Color regions of the chart based on trend.

        Args:
            ax: Matplotlib axis
            df: Price data DataFrame

        """
        if len(df) < 3:
            return

        # Use simple moving average for trend detection
        window_size = max(3, len(df) // 10)
        df["sma"] = df["price"].rolling(window=window_size, min_periods=1).mean()

        # Identify trend regions
        df["trend"] = 0  # 0 = neutral, 1 = up, -1 = down

        for i in range(1, len(df)):
            if df["sma"].iloc[i] > df["sma"].iloc[i - 1]:
                df.loc[df.index[i], "trend"] = 1
            elif df["sma"].iloc[i] < df["sma"].iloc[i - 1]:
                df.loc[df.index[i], "trend"] = -1

        # Merge consecutive same-trend regions
        current_trend = df["trend"].iloc[0]
        trend_regions = []
        start_idx = 0

        for i in range(1, len(df)):
            if df["trend"].iloc[i] != current_trend:
                # End of a trend region
                trend_regions.append((start_idx, i - 1, current_trend))
                start_idx = i
                current_trend = df["trend"].iloc[i]

        # Add the last region
        trend_regions.append((start_idx, len(df) - 1, current_trend))

        # Color each region
        for start, end, trend in trend_regions:
            if trend == 1:  # Uptrend
                color = self.up_color
            elif trend == -1:  # Downtrend
                color = self.down_color
            else:  # Neutral
                continue  # Skip coloring neutral regions

            # Get region boundaries
            x_start = df.index[start]
            x_end = df.index[end]
            y_min = df["price"].iloc[start : end + 1].min() * 0.99
            y_max = df["price"].iloc[start : end + 1].max() * 1.01

            # Add colored background
            rect = Rectangle(
                (mdates.date2num(x_start), y_min),
                mdates.date2num(x_end) - mdates.date2num(x_start),
                y_max - y_min,
                facecolor=color,
                alpha=0.1,
                edgecolor="none",
                zorder=1,
            )
            ax.add_patch(rect)

    def add_support_resistance(self, ax, df: pd.DataFrame) -> None:
        """Add support and resistance lines to the chart.

        Args:
            ax: Matplotlib axis
            df: Price data DataFrame

        """
        if len(df) < 10:
            return

        # Find local minima and maxima
        window_size = min(5, len(df) // 5)
        df["min"] = df["price"].rolling(window=window_size, center=True).min()
        df["max"] = df["price"].rolling(window=window_size, center=True).max()

        # Identify support and resistance points
        support_points = []
        resistance_points = []

        for i in range(window_size, len(df) - window_size):
            # Support point (local minimum)
            if (
                df["price"].iloc[i] == df["min"].iloc[i]
                and df["price"].iloc[i] < df["price"].iloc[i - 1]
                and df["price"].iloc[i] < df["price"].iloc[i + 1]
            ):
                support_points.append((df.index[i], df["price"].iloc[i]))

            # Resistance point (local maximum)
            if (
                df["price"].iloc[i] == df["max"].iloc[i]
                and df["price"].iloc[i] > df["price"].iloc[i - 1]
                and df["price"].iloc[i] > df["price"].iloc[i + 1]
            ):
                resistance_points.append((df.index[i], df["price"].iloc[i]))

        # Filter out points that are too close in price
        def filter_clusters(points, threshold=0.05):
            if not points:
                return []

            # Sort by price
            points.sort(key=operator.itemgetter(1))

            # Group points that are close in price
            groups = [[points[0]]]

            for i in range(1, len(points)):
                point = points[i]
                prev_point = points[i - 1]

                # If price is within threshold percentage, add to current group
                if abs(point[1] - prev_point[1]) / prev_point[1] <= threshold:
                    groups[-1].append(point)
                else:
                    # Start a new group
                    groups.append([point])

            # Take the median point from each group
            result = []
            for group in groups:
                if len(group) > 0:
                    # Sort by date and take the most recent
                    group.sort(key=operator.itemgetter(0))
                    result.append(group[-1])

            return result

        # Filter clusters
        support_points = filter_clusters(support_points)
        resistance_points = filter_clusters(resistance_points)

        # Draw support and resistance lines
        [df.index[0], df.index[-1]]

        for _date, price in support_points:
            ax.axhline(
                y=price,
                color=self.up_color,
                linestyle="--",
                alpha=0.5,
                linewidth=1,
            )

        for _date, price in resistance_points:
            ax.axhline(
                y=price,
                color=self.down_color,
                linestyle="--",
                alpha=0.5,
                linewidth=1,
            )
