"""
tests/unit/test_config_watcher.py — Regression tests for ConfigWatcher.

Formalises the ad-hoc e2e scenario confirmed 2026-09-21 / fixed 2026-09-22:
  ConfigWatcher._apply() must update BOTH Config.<attr> AND os.environ[key]
  synchronously when a successful setattr occurs, and must NOT touch
  os.environ when Pydantic validation fails.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Config
from src.utils.config_watcher import ConfigWatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_watcher(env_path: Path) -> ConfigWatcher:
    """Return a ConfigWatcher with _ENV_PATH patched to the given temp file."""
    watcher = ConfigWatcher()
    return watcher


def _run_reload(watcher: ConfigWatcher, env_path: Path) -> None:
    """Patch _ENV_PATH and synchronously call _reload()."""
    import src.utils.config_watcher as cw_mod
    original = cw_mod._ENV_PATH
    cw_mod._ENV_PATH = env_path
    try:
        asyncio.run(watcher._reload())
    finally:
        cw_mod._ENV_PATH = original


# ---------------------------------------------------------------------------
# Test 1: float key — Config attr AND os.environ both updated
# ---------------------------------------------------------------------------

class TestReloadSyncsOsEnvironForReloadableKey:
    """After _reload(), os.environ must mirror Config attribute for reloadable keys."""

    def test_reload_syncs_os_environ_for_float_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MIN_SPREAD_PCT (float, in _reloadable_keys): both Config and os.environ updated."""
        # Arrange: set known baseline
        original_val = Config.MIN_SPREAD_PCT
        monkeypatch.setattr(Config, "MIN_SPREAD_PCT", 5.0)
        monkeypatch.setenv("MIN_SPREAD_PCT", "5.0")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            fh.write("MIN_SPREAD_PCT=12.0\n")
            env_path = Path(fh.name)

        try:
            watcher = _make_watcher(env_path)
            _run_reload(watcher, env_path)

            # Both must reflect the new value
            assert Config.MIN_SPREAD_PCT == pytest.approx(12.0), (
                f"Config.MIN_SPREAD_PCT not updated: {Config.MIN_SPREAD_PCT}"
            )
            assert os.environ.get("MIN_SPREAD_PCT") == "12.0", (
                f"os.environ['MIN_SPREAD_PCT'] not updated: "
                f"{os.environ.get('MIN_SPREAD_PCT')!r}"
            )
        finally:
            env_path.unlink(missing_ok=True)
            monkeypatch.setattr(Config, "MIN_SPREAD_PCT", original_val)

    def test_reload_syncs_os_environ_for_bool_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KELLY_ENABLED (bool, in _reloadable_keys): both Config and os.environ updated."""
        original_val = Config.KELLY_ENABLED
        monkeypatch.setattr(Config, "KELLY_ENABLED", False)
        monkeypatch.setenv("KELLY_ENABLED", "false")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            fh.write("KELLY_ENABLED=true\n")
            env_path = Path(fh.name)

        try:
            watcher = _make_watcher(env_path)
            _run_reload(watcher, env_path)

            assert Config.KELLY_ENABLED is True, (
                f"Config.KELLY_ENABLED not updated: {Config.KELLY_ENABLED}"
            )
            assert os.environ.get("KELLY_ENABLED") == "true", (
                f"os.environ['KELLY_ENABLED'] not updated: "
                f"{os.environ.get('KELLY_ENABLED')!r}"
            )
        finally:
            env_path.unlink(missing_ok=True)
            monkeypatch.setattr(Config, "KELLY_ENABLED", original_val)


# ---------------------------------------------------------------------------
# Test 2: Validation failure — NEITHER Config NOR os.environ updated
# ---------------------------------------------------------------------------

class TestReloadDoesNotSyncOsEnvironOnValidationFailure:
    """On Pydantic ge/le constraint failure, os.environ must NOT be touched."""

    def test_float_key_validation_failure_leaves_environ_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        KELLY_FRACTION has ge=0.0, le=1.0.
        Submitting value=999.0 must fail Pydantic validation.
        After _reload(), Config.KELLY_FRACTION and os.environ['KELLY_FRACTION']
        must both remain at the original value.
        """
        original_val = Config.KELLY_FRACTION  # 0.50 by default
        monkeypatch.setattr(Config, "KELLY_FRACTION", 0.50)
        monkeypatch.setenv("KELLY_FRACTION", "0.5")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            # 999.0 violates le=1.0 constraint
            fh.write("KELLY_FRACTION=999.0\n")
            env_path = Path(fh.name)

        try:
            watcher = _make_watcher(env_path)
            _run_reload(watcher, env_path)

            # Config must NOT have changed
            assert Config.KELLY_FRACTION == pytest.approx(0.50), (
                f"Config.KELLY_FRACTION must be unchanged: {Config.KELLY_FRACTION}"
            )
            # os.environ must NOT have changed
            assert os.environ.get("KELLY_FRACTION") == "0.5", (
                f"os.environ['KELLY_FRACTION'] must be unchanged: "
                f"{os.environ.get('KELLY_FRACTION')!r}"
            )
        finally:
            env_path.unlink(missing_ok=True)
            monkeypatch.setattr(Config, "KELLY_FRACTION", original_val)

    def test_min_spread_pct_above_le_100_leaves_environ_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        MIN_SPREAD_PCT has le=100.0.
        Value 200.0 must fail validation; environ must stay at original.
        """
        original_val = Config.MIN_SPREAD_PCT
        monkeypatch.setattr(Config, "MIN_SPREAD_PCT", 6.0)
        monkeypatch.setenv("MIN_SPREAD_PCT", "6.0")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            fh.write("MIN_SPREAD_PCT=200.0\n")
            env_path = Path(fh.name)

        try:
            watcher = _make_watcher(env_path)
            _run_reload(watcher, env_path)

            assert Config.MIN_SPREAD_PCT == pytest.approx(6.0), (
                f"Config.MIN_SPREAD_PCT must be unchanged: {Config.MIN_SPREAD_PCT}"
            )
            assert os.environ.get("MIN_SPREAD_PCT") == "6.0", (
                f"os.environ['MIN_SPREAD_PCT'] must be unchanged: "
                f"{os.environ.get('MIN_SPREAD_PCT')!r}"
            )
        finally:
            env_path.unlink(missing_ok=True)
            monkeypatch.setattr(Config, "MIN_SPREAD_PCT", original_val)


# ---------------------------------------------------------------------------
# Test 3: Non-reloadable key — Config and os.environ both untouched
# ---------------------------------------------------------------------------

class TestReloadIgnoresNonReloadableKey:
    """Keys absent from _reloadable_keys must be silently skipped."""

    def test_non_reloadable_key_not_applied_to_config_or_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        GAME_ID is not in _reloadable_keys.
        Even if .env contains GAME_ID=CHANGED, _reload() must not touch
        Config.GAME_ID nor os.environ['GAME_ID'].
        """
        assert "GAME_ID" not in ConfigWatcher._reloadable_keys, (
            "GAME_ID must not be in _reloadable_keys for this test to be valid"
        )
        original_val = Config.GAME_ID
        monkeypatch.setattr(Config, "GAME_ID", "a8db")
        monkeypatch.setenv("GAME_ID", "a8db")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as fh:
            fh.write("GAME_ID=CHANGED\n")
            env_path = Path(fh.name)

        try:
            watcher = _make_watcher(env_path)
            _run_reload(watcher, env_path)

            assert Config.GAME_ID == "a8db", (
                f"Config.GAME_ID must be unchanged: {Config.GAME_ID}"
            )
            assert os.environ.get("GAME_ID") == "a8db", (
                f"os.environ['GAME_ID'] must be unchanged: "
                f"{os.environ.get('GAME_ID')!r}"
            )
        finally:
            env_path.unlink(missing_ok=True)
            monkeypatch.setattr(Config, "GAME_ID", original_val)
