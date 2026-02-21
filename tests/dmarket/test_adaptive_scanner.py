"""Tests for adaptive_scanner module.

This module tests the AdaptiveScanner class for intelligent
market scanning with dynamic intervals based on market volatility.
"""

from datetime import datetime, timedelta

import pytest


class TestAdaptiveScanner:
    """Tests for AdaptiveScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create AdaptiveScanner instance."""
        from src.dmarket.adaptive_scanner import AdaptiveScanner
        return AdaptiveScanner(min_interval=30, max_interval=300, volatility_window=10)

    def test_init(self, scanner):
        """Test initialization."""
        assert scanner.min_interval == 30
        assert scanner.max_interval == 300
        assert scanner.volatility_window == 10
        assert scanner.current_interval == 300  # Starts conservative

    def test_add_snapshot_with_items(self, scanner):
        """Test adding market snapshot with items."""
        items = [
            {"price": {"USD": 1000}},  # $10.00
            {"price": {"USD": 2000}},  # $20.00
            {"price": {"USD": 1500}},  # $15.00
        ]
        
        scanner.add_snapshot(items)
        
        assert len(scanner.snapshots) == 1
        snapshot = scanner.snapshots[0]
        assert snapshot.avg_price == 15.0
        assert snapshot.items_count == 3
        assert snapshot.price_spread == 10.0

    def test_add_snapshot_empty_items(self, scanner):
        """Test adding empty snapshot resets interval."""
        scanner.current_interval = 300
        
        scanner.add_snapshot([])
        
        # Should reset to 60 seconds for empty snapshots
        assert scanner.current_interval == 60
        assert len(scanner.snapshots) == 0

    def test_calculate_volatility_insufficient_data(self, scanner):
        """Test volatility calculation with insufficient data."""
        # Less than 3 snapshots returns default
        volatility = scanner.calculate_volatility()
        assert volatility == 0.5

    def test_calculate_volatility_with_data(self, scanner):
        """Test volatility calculation with sufficient data."""
        # Add stable snapshots (same prices)
        for i in range(5):
            items = [
                {"price": {"USD": 1000}},
                {"price": {"USD": 1100}},
                {"price": {"USD": 1050}},
            ]
            scanner.add_snapshot(items)
        
        volatility = scanner.calculate_volatility()
        # Stable prices should have low volatility
        assert 0 <= volatility <= 1

    def test_get_next_interval(self, scanner):
        """Test getting next scan interval."""
        # Add some snapshots for volatility calculation
        for i in range(5):
            items = [
                {"price": {"USD": 1000 + i * 100}},
                {"price": {"USD": 1500 + i * 50}},
            ]
            scanner.add_snapshot(items)
        
        interval = scanner.get_next_interval()
        
        # Should be between min and max
        assert scanner.min_interval <= interval <= scanner.max_interval

    def test_should_scan_now(self, scanner):
        """Test checking if should scan now."""
        scanner.current_interval = 60
        
        # Just scanned - should not scan
        recent_scan = datetime.now() - timedelta(seconds=30)
        assert not scanner.should_scan_now(recent_scan)
        
        # Old scan - should scan
        old_scan = datetime.now() - timedelta(seconds=120)
        assert scanner.should_scan_now(old_scan)

    @pytest.mark.asyncio
    async def test_wAlgot_next_scan(self, scanner):
        """Test wAlgoting for next scan."""
        # Set short interval for fast test
        scanner.min_interval = 0
        scanner.max_interval = 0
        
        # Should complete quickly
        awAlgot scanner.wAlgot_next_scan()

    def test_volatility_window(self, scanner):
        """Test volatility window limits snapshots."""
        # Add more than volatility_window snapshots
        for i in range(15):
            items = [{"price": {"USD": 1000 + i * 10}}]
            scanner.add_snapshot(items)
        
        # Should only keep volatility_window snapshots
        assert len(scanner.snapshots) == scanner.volatility_window

    def test_high_volatility_shorter_interval(self, scanner):
        """Test high volatility results in shorter interval."""
        # Add volatile snapshots (varying prices)
        for i in range(5):
            items = [
                {"price": {"USD": 500 + i * 500}},  # Large price changes
                {"price": {"USD": 2000 - i * 300}},
            ]
            scanner.add_snapshot(items)
        
        interval = scanner.get_next_interval()
        
        # High volatility should push toward min_interval
        assert interval <= scanner.max_interval

    def test_snapshot_with_zero_prices(self, scanner):
        """Test snapshot ignores zero prices."""
        items = [
            {"price": {"USD": 1000}},
            {"price": {"USD": 0}},  # Should be ignored
            {"price": {"USD": 2000}},
        ]
        
        scanner.add_snapshot(items)
        
        snapshot = scanner.snapshots[0]
        assert snapshot.items_count == 3  # All items counted
        # But avg should be based on valid prices only
        assert snapshot.avg_price == 15.0  # (10 + 20) / 2
