"""Tests for BotBrAlgon - autonomous decision-making module."""

from datetime import UTC, datetime

import pytest

from src.ml.Algo_coordinator import AutonomyLevel
from src.ml.bot_brain import (
    Alert,
    AlertLevel,
    AutonomyConfig,
    BotBrAlgon,
    BotState,
    CycleResult,
    create_bot_brain,
)


class TestBotBrAlgonBasic:
    """Basic tests for BotBrAlgon."""

    def test_init_creates_brain(self):
        """Test that BotBrAlgon can be initialized."""
        brain = BotBrAlgon()

        assert brain is not None
        assert brain.state == BotState.IDLE
        assert brain.is_running is False
        assert brain.config.dry_run is True

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = AutonomyConfig(
            autonomy_level=AutonomyLevel.SEMI_AUTO,
            max_trade_usd=100.0,
            dry_run=False,
        )
        brain = BotBrAlgon(config=config)

        assert brain.config.autonomy_level == AutonomyLevel.SEMI_AUTO
        assert brain.config.max_trade_usd == 100.0
        assert brain.config.dry_run is False


class TestAutonomyConfig:
    """Tests for AutonomyConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AutonomyConfig()

        assert config.autonomy_level == AutonomyLevel.MANUAL
        assert config.max_trade_usd == 50.0
        assert config.max_daily_volume_usd == 200.0
        assert config.dry_run is True
        assert config.scan_interval_seconds == 60

    def test_custom_config(self):
        """Test custom configuration."""
        config = AutonomyConfig(
            autonomy_level=AutonomyLevel.AUTO,
            max_trade_usd=25.0,
            scan_interval_seconds=120,
        )

        assert config.autonomy_level == AutonomyLevel.AUTO
        assert config.max_trade_usd == 25.0
        assert config.scan_interval_seconds == 120


class TestBotState:
    """Tests for BotState enum."""

    def test_all_states_exist(self):
        """Test that all expected states exist."""
        states = [s.value for s in BotState]

        assert "idle" in states
        assert "scanning" in states
        assert "analyzing" in states
        assert "deciding" in states
        assert "executing" in states
        assert "learning" in states
        assert "paused" in states
        assert "stopped" in states


class TestAlert:
    """Tests for Alert dataclass."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            level=AlertLevel.WARNING,
            message="Test alert",
        )

        assert alert.level == AlertLevel.WARNING
        assert alert.message == "Test alert"
        assert alert.timestamp is not None

    def test_alert_with_data(self):
        """Test alert with additional data."""
        alert = Alert(
            level=AlertLevel.ERROR,
            message="Error occurred",
            data={"error_code": 500},
        )

        assert alert.data == {"error_code": 500}


class TestCycleResult:
    """Tests for CycleResult dataclass."""

    def test_cycle_result_creation(self):
        """Test creating a cycle result."""
        now = datetime.now(UTC)
        result = CycleResult(
            cycle_number=1,
            started_at=now,
            completed_at=now,
            items_scanned=100,
            opportunities_found=5,
        )

        assert result.cycle_number == 1
        assert result.items_scanned == 100
        assert result.opportunities_found == 5

    def test_cycle_result_to_dict(self):
        """Test CycleResult to_dict method."""
        now = datetime.now(UTC)
        result = CycleResult(
            cycle_number=1,
            started_at=now,
            completed_at=now,
        )

        data = result.to_dict()

        assert data["cycle_number"] == 1
        assert "started_at" in data
        assert "completed_at" in data


class TestBrAlgonControls:
    """Tests for brain control methods."""

    def test_pause_sets_state(self):
        """Test pause sets paused state."""
        brain = BotBrAlgon()

        brain.pause()

        assert brain.state == BotState.PAUSED

    def test_resume_from_pause(self):
        """Test resume from paused state."""
        brain = BotBrAlgon()
        brain.pause()

        brain.resume()

        assert brain.state == BotState.IDLE

    def test_emergency_stop(self):
        """Test emergency stop."""
        brain = BotBrAlgon()

        brain.emergency_stop("Test reason")

        assert brain.state == BotState.STOPPED
        assert brain.is_running is False


class TestPendingDecisions:
    """Tests for pending decisions management."""

    def test_pending_decisions_initially_empty(self):
        """Test pending decisions list is initially empty."""
        brain = BotBrAlgon()

        assert len(brain.pending_decisions) == 0

    def test_clear_pending_decisions(self):
        """Test clearing pending decisions."""
        brain = BotBrAlgon()

        count = brain.clear_pending_decisions()

        assert count == 0


class TestStatistics:
    """Tests for statistics."""

    def test_get_statistics(self):
        """Test getting statistics."""
        brain = BotBrAlgon()

        stats = brain.get_statistics()

        assert "total_cycles" in stats
        assert "total_items_scanned" in stats
        assert "successful_trades" in stats
        assert "state" in stats
        assert "is_running" in stats
        assert stats["total_cycles"] == 0

    def test_reset_daily_stats(self):
        """Test resetting daily statistics."""
        brain = BotBrAlgon()

        brain.reset_daily_stats()

        stats = brain.get_statistics()
        assert stats["daily_volume"] == 0.0


class TestAlerts:
    """Tests for alert management."""

    def test_get_alerts_empty(self):
        """Test getting alerts when none exist."""
        brain = BotBrAlgon()

        alerts = brain.get_alerts()

        assert len(alerts) == 0

    def test_alerts_after_emergency_stop(self):
        """Test alerts are generated after emergency stop."""
        brain = BotBrAlgon()

        brain.emergency_stop("Test")

        alerts = brain.get_alerts()
        assert len(alerts) > 0
        assert any("EMERGENCY" in a.message for a in alerts)


class TestFactoryFunction:
    """Tests for create_bot_brain factory."""

    def test_create_bot_brain_default(self):
        """Test creating brain with defaults."""
        brain = create_bot_brain()

        assert brain is not None
        assert brain.config.autonomy_level == AutonomyLevel.MANUAL
        assert brain.config.dry_run is True

    def test_create_bot_brain_custom(self):
        """Test creating brain with custom options."""
        brain = create_bot_brain(
            autonomy_level=AutonomyLevel.AUTO,
            dry_run=False,
            max_trade_usd=100.0,
        )

        assert brain.config.autonomy_level == AutonomyLevel.AUTO
        assert brain.config.dry_run is False
        assert brain.config.max_trade_usd == 100.0


class TestRunCycle:
    """Tests for run_cycle method."""

    @pytest.mark.asyncio
    async def test_run_cycle_without_api(self):
        """Test running cycle without API returns empty result."""
        brain = BotBrAlgon()

        result = await brain.run_cycle()

        assert isinstance(result, CycleResult)
        assert result.cycle_number == 1
        assert result.items_scanned == 0  # No API, no items

    @pytest.mark.asyncio
    async def test_run_cycle_updates_stats(self):
        """Test running cycle updates statistics."""
        brain = BotBrAlgon()

        await brain.run_cycle()

        stats = brain.get_statistics()
        assert stats["total_cycles"] == 1


class TestConfirmReject:
    """Tests for confirm/reject decisions."""

    @pytest.mark.asyncio
    async def test_confirm_invalid_index(self):
        """Test confirming with invalid index."""
        brain = BotBrAlgon()

        result = await brain.confirm_decision(999)

        assert result is False

    def test_reject_invalid_index(self):
        """Test rejecting with invalid index."""
        brain = BotBrAlgon()

        result = brain.reject_decision(999)

        assert result is False
