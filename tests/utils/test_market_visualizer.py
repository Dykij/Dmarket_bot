"""Unit tests for the market visualizer module."""

import io
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.utils.market_visualizer import MarketVisualizer


@pytest.fixture()
def sample_price_history():
    """Sample price history data for testing."""
    return [
        {
            "price": 10.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=6)).timestamp(),
        },
        {
            "price": 10.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
        },
        {
            "price": 11.2,
            "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
        },
        {
            "price": 11.8,
            "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
        },
        {
            "price": 11.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
        },
        {
            "price": 12.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
        },
        {"price": 12.5, "timestamp": datetime.now(UTC).timestamp()},
    ]


@pytest.fixture()
def sample_price_history_with_volume():
    """Sample price history data with volume for testing."""
    return [
        {
            "price": 10.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=6)).timestamp(),
            "volume": 50,
        },
        {
            "price": 10.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=5)).timestamp(),
            "volume": 45,
        },
        {
            "price": 11.2,
            "timestamp": (datetime.now(UTC) - timedelta(days=4)).timestamp(),
            "volume": 60,
        },
        {
            "price": 11.8,
            "timestamp": (datetime.now(UTC) - timedelta(days=3)).timestamp(),
            "volume": 70,
        },
        {
            "price": 11.5,
            "timestamp": (datetime.now(UTC) - timedelta(days=2)).timestamp(),
            "volume": 55,
        },
        {
            "price": 12.0,
            "timestamp": (datetime.now(UTC) - timedelta(days=1)).timestamp(),
            "volume": 65,
        },
        {"price": 12.5, "timestamp": datetime.now(UTC).timestamp(), "volume": 80},
    ]


@pytest.fixture()
def sample_items_data():
    """Sample items data for comparison charts."""
    return [
        {
            "itemId": "item1",
            "title": "AK-47 | Redline",
            "price": {"amount": 1250},  # $12.50
        },
        {
            "itemId": "item2",
            "title": "M4A4 | Asiimov",
            "price": {"amount": 2500},  # $25.00
        },
    ]


@pytest.fixture()
def sample_price_histories():
    """Sample price histories for multiple items."""
    now = datetime.now(UTC)

    # Item 1 with upward trend
    item1_history = [
        {"price": 10.0, "timestamp": (now - timedelta(days=6)).timestamp()},
        {"price": 10.8, "timestamp": (now - timedelta(days=5)).timestamp()},
        {"price": 11.2, "timestamp": (now - timedelta(days=4)).timestamp()},
        {"price": 11.5, "timestamp": (now - timedelta(days=3)).timestamp()},
        {"price": 12.0, "timestamp": (now - timedelta(days=2)).timestamp()},
        {"price": 12.3, "timestamp": (now - timedelta(days=1)).timestamp()},
        {"price": 12.5, "timestamp": now.timestamp()},
    ]

    # Item 2 with downward trend
    item2_history = [
        {"price": 30.0, "timestamp": (now - timedelta(days=6)).timestamp()},
        {"price": 29.0, "timestamp": (now - timedelta(days=5)).timestamp()},
        {"price": 28.2, "timestamp": (now - timedelta(days=4)).timestamp()},
        {"price": 27.5, "timestamp": (now - timedelta(days=3)).timestamp()},
        {"price": 26.8, "timestamp": (now - timedelta(days=2)).timestamp()},
        {"price": 26.0, "timestamp": (now - timedelta(days=1)).timestamp()},
        {"price": 25.0, "timestamp": now.timestamp()},
    ]

    return {
        "item1": item1_history,
        "item2": item2_history,
    }


@pytest.fixture()
def sample_pattern_history():
    """Sample price history with detectable patterns."""
    now = datetime.now(UTC)

    # Create a price history with a breakout pattern
    return [
        {"price": 10.0, "timestamp": (now - timedelta(days=12)).timestamp()},
        {"price": 10.1, "timestamp": (now - timedelta(days=11)).timestamp()},
        {"price": 10.2, "timestamp": (now - timedelta(days=10)).timestamp()},
        {"price": 10.1, "timestamp": (now - timedelta(days=9)).timestamp()},
        {"price": 10.0, "timestamp": (now - timedelta(days=8)).timestamp()},
        {"price": 10.2, "timestamp": (now - timedelta(days=7)).timestamp()},
        {"price": 10.1, "timestamp": (now - timedelta(days=6)).timestamp()},
        {"price": 10.3, "timestamp": (now - timedelta(days=5)).timestamp()},
        {"price": 10.4, "timestamp": (now - timedelta(days=4)).timestamp()},
        {"price": 10.5, "timestamp": (now - timedelta(days=3)).timestamp()},
        {"price": 11.0, "timestamp": (now - timedelta(days=2)).timestamp()},
        {"price": 12.0, "timestamp": (now - timedelta(days=1)).timestamp()},
        {"price": 13.5, "timestamp": now.timestamp()},
    ]


@pytest.fixture()
def sample_patterns():
    """Sample detected patterns for visualization."""
    return [
        {
            "type": "breakout",
            "confidence": 0.85,
            "description": "Price breaking out of previous range",
        },
        {
            "type": "fomo",
            "confidence": 0.75,
            "description": "Rapid price increase detected (FOMO)",
        },
    ]


@pytest.fixture()
def sample_item_data():
    """Sample item data for market summary image."""
    return {
        "itemId": "item1",
        "title": "AK-47 | Redline",
        "price": {"amount": 1250},  # $12.50
        "gameId": "csgo",
        "extra": {
            "categoryPath": "Rifle",
            "rarity": "Classified",
            "exterior": "Field-Tested",
        },
    }


@pytest.fixture()
def sample_analysis_data():
    """Sample market analysis data for summary image."""
    return {
        "trend": "up",
        "confidence": 0.8,
        "volatility": "low",
        "volatility_ratio": 0.03,
        "patterns": [
            {"type": "breakout", "confidence": 0.85},
            {"type": "fomo", "confidence": 0.75},
        ],
        "support_level": 11.0,
        "resistance_level": 13.0,
        "current_price": 12.5,
        "avg_price": 11.0,
        "min_price": 10.0,
        "max_price": 13.5,
        "price_range": 3.5,
        "price_change_24h": 12.5,
        "price_change_7d": 25.0,
        "volume_change": 15.0,
        "insufficient_data": False,
    }


@pytest.mark.asyncio()
class TestMarketVisualizer:
    """Tests for the MarketVisualizer class."""

    def test_init(self):
        """Test that the visualizer initializes with correct parameters."""
        # Test default theme (dark)
        visualizer = MarketVisualizer()
        assert visualizer.theme == "dark"
        assert visualizer.text_color == "white"

        # Test light theme
        visualizer = MarketVisualizer(theme="light")
        assert visualizer.theme == "light"
        assert visualizer.text_color == "black"

    def test_setup_plot_style(self):
        """Test plot style setup with different themes."""
        # Test dark theme
        visualizer = MarketVisualizer(theme="dark")
        assert visualizer.up_color == "#00ff9f"  # Green for dark theme
        assert visualizer.down_color == "#ff5757"  # Red for dark theme

        # Test light theme
        visualizer = MarketVisualizer(theme="light")
        assert visualizer.up_color == "#00aa5e"  # Green for light theme
        assert visualizer.down_color == "#d63031"  # Red for light theme

    async def test_create_price_chart_empty(self):
        """Test creating a chart with empty data."""
        visualizer = MarketVisualizer()

        # Test with empty data
        result = await visualizer.create_price_chart(
            price_history=[],
            item_name="Test Item",
            game="csgo",
            width=800,
            height=600,
        )

        assert isinstance(result, io.BytesIO)
        # Verify it's a valid image by opening it
        img = Image.open(result)
        assert img.width > 0
        assert img.height > 0

    @patch("matplotlib.figure.Figure.savefig")
    async def test_create_price_chart(self, mock_savefig, sample_price_history):
        """Test creating a price chart."""
        visualizer = MarketVisualizer()

        result = await visualizer.create_price_chart(
            price_history=sample_price_history,
            item_name="AK-47 | Redline",
            game="csgo",
            width=800,
            height=600,
        )

        assert isinstance(result, io.BytesIO)
        mock_savefig.assert_called_once()

    @patch("matplotlib.figure.Figure.savefig")
    async def test_create_price_chart_with_volume(
        self,
        mock_savefig,
        sample_price_history_with_volume,
    ):
        """Test creating a price chart with volume data."""
        visualizer = MarketVisualizer()

        result = await visualizer.create_price_chart(
            price_history=sample_price_history_with_volume,
            item_name="AK-47 | Redline",
            game="csgo",
            include_volume=True,
            width=800,
            height=600,
        )

        assert isinstance(result, io.BytesIO)
        mock_savefig.assert_called_once()

    @patch("matplotlib.figure.Figure.savefig")
    async def test_create_market_comparison_chart(
        self,
        mock_savefig,
        sample_items_data,
        sample_price_histories,
    ):
        """Test creating a market comparison chart."""
        visualizer = MarketVisualizer()

        result = await visualizer.create_market_comparison_chart(
            items_data=sample_items_data,
            price_histories=sample_price_histories,
            width=800,
            height=600,
        )

        assert isinstance(result, io.BytesIO)
        mock_savefig.assert_called_once()

    @patch("matplotlib.figure.Figure.savefig")
    async def test_create_pattern_visualization(
        self,
        mock_savefig,
        sample_pattern_history,
        sample_patterns,
    ):
        """Test creating a pattern visualization chart."""
        visualizer = MarketVisualizer()

        result = await visualizer.create_pattern_visualization(
            price_history=sample_pattern_history,
            patterns=sample_patterns,
            item_name="AK-47 | Redline",
            width=800,
            height=500,
        )

        assert isinstance(result, io.BytesIO)
        mock_savefig.assert_called_once()

    @patch("PIL.Image.new")
    async def test_create_market_summary_image(
        self,
        mock_new,
        sample_item_data,
        sample_analysis_data,
    ):
        """Test creating a market summary image."""
        visualizer = MarketVisualizer()

        # Mock Image.new to return a mock image
        mock_img = MagicMock()
        mock_img.save = MagicMock()
        mock_new.return_value = mock_img

        result = await visualizer.create_market_summary_image(
            item_data=sample_item_data,
            analysis=sample_analysis_data,
            width=800,
            height=400,
        )

        assert isinstance(result, io.BytesIO)
        mock_new.assert_called_once()

    def test_process_price_data(self, sample_price_history_with_volume):
        """Test processing price data into a DataFrame."""
        visualizer = MarketVisualizer()

        df = visualizer.process_price_data(sample_price_history_with_volume)

        assert len(df) == 7
        assert "price" in df.columns
        assert "volume" in df.columns
        assert df["price"].iloc[0] == 10.0
        assert df["volume"].iloc[0] == 50

    def test_color_trend_regions(self):
        """Test coloring trend regions on a chart."""
        visualizer = MarketVisualizer()

        # Create a test DataFrame
        import pandas as pd

        dates = [datetime.now(UTC) - timedelta(days=x) for x in range(5, 0, -1)]
        df = pd.DataFrame(
            {
                "price": [10.0, 10.5, 11.0, 11.5, 12.0],
                "sma": [10.0, 10.5, 11.0, 11.5, 12.0],  # Pre-calculated SMA for testing
            },
            index=dates,
        )

        # Mock axis
        ax = MagicMock()
        ax.add_patch = MagicMock()

        # Execute method
        visualizer.color_trend_regions(ax, df)

        # Verify at least one patch was added for trend regions
        assert ax.add_patch.called

    def test_add_support_resistance(self):
        """Test adding support and resistance lines to a chart."""
        visualizer = MarketVisualizer()

        # Create a test DataFrame with local min/max points
        import pandas as pd

        dates = [datetime.now(UTC) - timedelta(days=x) for x in range(10, 0, -1)]
        prices = [10.0, 10.5, 10.0, 11.0, 10.5, 10.0, 10.5, 11.0, 10.5, 10.0]
        df = pd.DataFrame(
            {
                "price": prices,
                # Pre-calculate min/max for the test
                "min": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
                "max": [11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0],
            },
            index=dates,
        )

        # Mock axis
        ax = MagicMock()
        ax.axhline = MagicMock()

        # Execute method
        visualizer.add_support_resistance(ax, df)

        # Verify axhline was called to add lines
        assert ax.axhline.called
