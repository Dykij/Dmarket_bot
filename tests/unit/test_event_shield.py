"""Tests for event_shield.py — CS2 Event Calendar Awareness."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from src.core.event_shield import EventShield


def _make_event(
    name: str = "Major",
    start: str = "2025-01-01",
    end: str = "2025-12-31",
    effect: str = "caution",
    margin_multiplier: float = 2.0,
    affected_categories: list[str] | None = None,
):
    return {
        "name": name,
        "start": start,
        "end": end,
        "effect": effect,
        "margin_multiplier": margin_multiplier,
        "affected_categories": affected_categories or [],
        "notes": "",
    }


class TestEventShield:

    def test_init_empty(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        assert shield.events == []

    def test_get_active_events_none(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        assert shield.get_active_events() == []

    def test_get_active_events_with_active(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(start="2020-01-01", end="2030-12-31")]
        active = shield.get_active_events(check_date=date(2025, 6, 15))
        assert len(active) == 1

    def test_get_active_events_expired(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(start="2020-01-01", end="2020-12-31")]
        active = shield.get_active_events(check_date=date(2025, 6, 15))
        assert len(active) == 0

    def test_get_active_events_future(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(start="2030-01-01", end="2030-12-31")]
        active = shield.get_active_events(check_date=date(2025, 6, 15))
        assert len(active) == 0

    def test_get_active_events_invalid_date(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [{"name": "Bad", "start": "invalid", "end": "invalid"}]
        active = shield.get_active_events(check_date=date(2025, 6, 15))
        assert len(active) == 0

    def test_get_margin_multiplier_no_events(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        assert shield.get_margin_multiplier() == 1.0

    def test_get_margin_multiplier_caution(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(effect="caution", margin_multiplier=2.0, start="2020-01-01", end="2030-12-31")]
        assert shield.get_margin_multiplier() == 2.0

    def test_get_margin_multiplier_opportunity(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(effect="opportunity", margin_multiplier=0.5, start="2020-01-01", end="2030-12-31")]
        assert shield.get_margin_multiplier() == 0.5

    def test_get_margin_multiplier_mixed(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [
            _make_event("Major", effect="caution", margin_multiplier=2.0, start="2020-01-01", end="2030-12-31"),
            _make_event("Sale", effect="opportunity", margin_multiplier=0.5, start="2020-01-01", end="2030-12-31"),
        ]
        # caution(2.0) * opportunity(0.5) = 1.0
        assert shield.get_margin_multiplier() == 1.0

    def test_is_category_risky_true(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(
            effect="caution", affected_categories=["knife", "rifle"],
            start="2020-01-01", end="2030-12-31",
        )]
        # "knife" is in "Knife | Fade"
        assert shield.is_category_risky("Knife | Fade") is True

    def test_is_category_risky_ak47(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(
            effect="caution", affected_categories=["knife", "rifle"],
            start="2020-01-01", end="2030-12-31",
        )]
        # "rifle" is NOT in "AK-47 | Redline" (substring match, not category)
        assert shield.is_category_risky("AK-47 | Redline") is False

    def test_is_category_risky_false(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(
            effect="caution", affected_categories=["knife"],
            start="2020-01-01", end="2030-12-31",
        )]
        assert shield.is_category_risky("AK-47 | Redline") is False

    def test_is_category_risky_no_caution_events(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(effect="opportunity", start="2020-01-01", end="2030-12-31")]
        assert shield.is_category_risky("★ Karambit") is False

    def test_is_opportunity_mode_true(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(effect="opportunity", start="2020-01-01", end="2030-12-31")]
        assert shield.is_opportunity_mode() is True

    def test_is_opportunity_mode_false(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(effect="caution", start="2020-01-01", end="2030-12-31")]
        assert shield.is_opportunity_mode() is False

    def test_get_status_summary_no_events(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        summary = shield.get_status_summary()
        assert "Нет активных" in summary

    def test_get_status_summary_with_events(self):
        shield = EventShield.__new__(EventShield)
        shield.events = [_make_event(name="Major 2025", start="2020-01-01", end="2030-12-31")]
        summary = shield.get_status_summary()
        assert "Major 2025" in summary

    def test_add_event(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        with patch.object(shield, "save_events"):
            shield.add_event("Test", "2025-01-01", "2025-12-31", "caution", 2.0)
        assert len(shield.events) == 1
        assert shield.events[0]["name"] == "Test"

    def test_reload(self):
        shield = EventShield.__new__(EventShield)
        shield.events = []
        with patch.object(shield, "_load_events"):
            shield.reload()

    def test_load_events_file_not_found(self):
        """Missing events file logs warning (line 35)."""
        shield = EventShield.__new__(EventShield)
        shield.events = []
        with patch("src.core.event_shield.EVENTS_FILE") as mock_path:
            mock_path.exists.return_value = False
            shield._load_events()
        assert shield.events == []

    def test_load_events_exception(self):
        """Exception during load is caught (lines 36-37)."""
        shield = EventShield.__new__(EventShield)
        shield.events = []
        with patch("src.core.event_shield.EVENTS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.__str__ = MagicMock(return_value="/fake/path")
            with patch("builtins.open", side_effect=PermissionError("denied")):
                shield._load_events()
        assert shield.events == []

    def test_save_events_success(self):
        """save_events writes to file (lines 122-124)."""
        shield = EventShield.__new__(EventShield)
        shield.events = [{"name": "Test"}]
        with patch("builtins.open", MagicMock()):
            with patch("src.core.event_shield.json.dump"):
                shield.save_events()

    def test_save_events_exception(self):
        """save_events exception is caught (lines 125-126)."""
        shield = EventShield.__new__(EventShield)
        shield.events = [{"name": "Test"}]
        with patch("builtins.open", side_effect=PermissionError("denied")):
            shield.save_events()  # Should not raise
