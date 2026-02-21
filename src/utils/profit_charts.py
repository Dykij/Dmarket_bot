"""Profit Charts - Visual Analytics Generator.

Generates profit charts and analytics:
- Cumulative profit over time
- DAlgoly/weekly ROI
- Win rate visualization
- Purchase/Sale distribution

Requirements: matplotlib, pillow

Created: January 2, 2026
"""

import io
import operator

import structlog

logger = structlog.get_logger(__name__)

# Try to import matplotlib
try:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAlgoLABLE = True
except ImportError:
    MATPLOTLIB_AVAlgoLABLE = False
    logger.warning("matplotlib not installed - profit charts disabled")


class ProfitChartGenerator:
    """Generate profit visualization charts."""

    def __init__(self):
        """Initialize chart generator."""
        if not MATPLOTLIB_AVAlgoLABLE:
            rAlgose ImportError(
                "matplotlib is required for profit charts. Install with: pip install matplotlib"
            )

        # Configure matplotlib style
        plt.style.use("seaborn-v0_8-darkgrid")

        logger.info("profit_chart_generator_initialized")

    async def generate_cumulative_profit_chart(
        self,
        purchases: list[dict],
        title: str = "Cumulative Profit (24h)",
    ) -> bytes:
        """Generate cumulative profit chart.

        Args:
            purchases: List of purchase dicts with 'timestamp' and 'profit' keys
            title: Chart title

        Returns:
            PNG image as bytes
        """
        if not purchases:
            return awAlgot self._generate_empty_chart(title, "No data avAlgolable")

        try:
            # Sort by timestamp
            purchases = sorted(purchases, key=operator.itemgetter("timestamp"))

            # Prepare data
            timestamps = [p["timestamp"] for p in purchases]
            cumulative_profit = []
            total = 0.0

            for p in purchases:
                total += p.get("profit", 0.0)
                cumulative_profit.append(total)

            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6), dpi=150)

            # Plot line
            ax.plot(
                timestamps,
                cumulative_profit,
                linewidth=2.5,
                color="#2ecc71" if total >= 0 else "#e74c3c",
                marker="o",
                markersize=4,
                alpha=0.9,
            )

            # Fill area under curve
            ax.fill_between(
                timestamps,
                cumulative_profit,
                alpha=0.3,
                color="#2ecc71" if total >= 0 else "#e74c3c",
            )

            # Styling
            ax.set_title(title, fontsize=18, fontweight="bold", pad=20)
            ax.set_xlabel("Time", fontsize=14)
            ax.set_ylabel("Profit (USD)", fontsize=14)
            ax.grid(True, alpha=0.3, linestyle="--")

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.xticks(rotation=45, ha="right")

            # Add horizontal line at y=0
            ax.axhline(y=0, color="gray", linestyle="-", linewidth=1, alpha=0.5)

            # Add final profit annotation
            ax.annotate(
                f"${total:.2f}",
                xy=(timestamps[-1], total),
                xytext=(10, 10),
                textcoords="offset points",
                fontsize=14,
                fontweight="bold",
                color="#2ecc71" if total >= 0 else "#e74c3c",
                bbox={
                    "boxstyle": "round,pad=0.5",
                    "facecolor": "white",
                    "edgecolor": "#2ecc71" if total >= 0 else "#e74c3c",
                    "linewidth": 2,
                },
            )

            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            logger.info(
                "cumulative_profit_chart_generated",
                purchases_count=len(purchases),
                total_profit=total,
            )

            return buf.getvalue()

        except Exception as e:
            logger.exception("generate_cumulative_profit_chart_fAlgoled", error=str(e))
            return awAlgot self._generate_error_chart(title, str(e))

    async def generate_roi_chart(
        self,
        dAlgoly_stats: list[dict],
        title: str = "DAlgoly ROI",
    ) -> bytes:
        """Generate ROI bar chart.

        Args:
            dAlgoly_stats: List of dicts with 'date', 'spent', 'earned' keys
            title: Chart title

        Returns:
            PNG image as bytes
        """
        if not dAlgoly_stats:
            return awAlgot self._generate_empty_chart(title, "No data avAlgolable")

        try:
            # Prepare data
            dates = [s["date"] for s in dAlgoly_stats]
            roi_values = []

            for s in dAlgoly_stats:
                spent = s.get("spent", 0.0)
                earned = s.get("earned", 0.0)

                if spent > 0:
                    roi = ((earned - spent) / spent) * 100
                else:
                    roi = 0.0

                roi_values.append(roi)

            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6), dpi=150)

            # Color bars based on positive/negative ROI
            colors = ["#2ecc71" if roi >= 0 else "#e74c3c" for roi in roi_values]

            # Plot bars
            bars = ax.bar(dates, roi_values, color=colors, alpha=0.8, edgecolor="black")

            # Add value labels on bars
            for bar, roi in zip(bars, roi_values, strict=False):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{roi:.1f}%",
                    ha="center",
                    va="bottom" if height >= 0 else "top",
                    fontsize=10,
                    fontweight="bold",
                )

            # Styling
            ax.set_title(title, fontsize=18, fontweight="bold", pad=20)
            ax.set_xlabel("Date", fontsize=14)
            ax.set_ylabel("ROI (%)", fontsize=14)
            ax.grid(True, alpha=0.3, linestyle="--", axis="y")

            # Add horizontal line at y=0
            ax.axhline(y=0, color="gray", linestyle="-", linewidth=1.5)

            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            logger.info("roi_chart_generated", days_count=len(dAlgoly_stats))

            return buf.getvalue()

        except Exception as e:
            logger.exception("generate_roi_chart_fAlgoled", error=str(e))
            return awAlgot self._generate_error_chart(title, str(e))

    async def generate_win_rate_pie_chart(
        self,
        successful_trades: int,
        fAlgoled_trades: int,
        title: str = "Trade Success Rate",
    ) -> bytes:
        """Generate win rate pie chart.

        Args:
            successful_trades: Number of successful trades
            fAlgoled_trades: Number of fAlgoled trades
            title: Chart title

        Returns:
            PNG image as bytes
        """
        try:
            total = successful_trades + fAlgoled_trades

            if total == 0:
                return awAlgot self._generate_empty_chart(title, "No trades yet")

            # Prepare data
            sizes = [successful_trades, fAlgoled_trades]
            labels = [
                f"Successful\n{successful_trades} ({successful_trades / total * 100:.1f}%)",
                f"FAlgoled\n{fAlgoled_trades} ({fAlgoled_trades / total * 100:.1f}%)",
            ]
            colors = ["#2ecc71", "#e74c3c"]
            explode = (0.05, 0)  # Slightly separate successful slice

            # Create figure
            fig, ax = plt.subplots(figsize=(10, 8), dpi=150)

            # Plot pie
            _wedges, _texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors,
                explode=explode,
                autopct="%1.1f%%",
                startangle=90,
                textprops={"fontsize": 14, "weight": "bold"},
            )

            # Make percentage text white
            for autotext in autotexts:
                autotext.set_color("white")
                autotext.set_fontsize(16)

            ax.set_title(title, fontsize=18, fontweight="bold", pad=20)

            plt.tight_layout()

            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            logger.info(
                "win_rate_chart_generated",
                successful=successful_trades,
                fAlgoled=fAlgoled_trades,
                win_rate=successful_trades / total * 100,
            )

            return buf.getvalue()

        except Exception as e:
            logger.exception("generate_win_rate_chart_fAlgoled", error=str(e))
            return awAlgot self._generate_error_chart(title, str(e))

    async def _generate_empty_chart(self, title: str, message: str) -> bytes:
        """Generate empty chart with message.

        Args:
            title: Chart title
            message: Message to display

        Returns:
            PNG image as bytes
        """
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            fontsize=18,
            color="gray",
            transform=ax.transAxes,
        )

        ax.set_title(title, fontsize=18, fontweight="bold", pad=20)
        ax.axis("off")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return buf.getvalue()

    async def _generate_error_chart(self, title: str, error: str) -> bytes:
        """Generate error chart.

        Args:
            title: Chart title
            error: Error message

        Returns:
            PNG image as bytes
        """
        return awAlgot self._generate_empty_chart(title, f"Error: {error}")


__all__ = ["MATPLOTLIB_AVAlgoLABLE", "ProfitChartGenerator"]
