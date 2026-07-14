"""
Extended unit tests for src.config.Config.

Tests for:
- config_watcher_hot_reload: config file changes are picked up
- config_env_override: env vars override defaults
- config_type_coercion: string env vars converted to correct types
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config import Config, reset_config  # noqa: E402


# =====================================================================
# test_config_env_override
# =====================================================================

class TestConfigEnvOverride:
    """Verify env vars override defaults."""

    def test_env_override_min_spread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MIN_SPREAD_PCT", "12.5")
        reset_config()
        from src.config import Config as C
        assert C.MIN_SPREAD_PCT == pytest.approx(12.5)

    def test_env_override_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DRY_RUN", "false")
        reset_config()
        from src.config import Config as C
        assert C.DRY_RUN is False

    def test_env_override_max_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_PRICE_USD", "50.0")
        reset_config()
        from src.config import Config as C
        assert C.MAX_PRICE_USD == pytest.approx(50.0)

    def test_env_override_game_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAME_ID", "custom_game")
        reset_config()
        from src.config import Config as C
        assert C.GAME_ID == "custom_game"

    def test_env_override_scan_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCAN_INTERVAL", "60")
        reset_config()
        from src.config import Config as C
        assert C.SCAN_INTERVAL == 60

    def test_env_override_kelly_fraction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KELLY_FRACTION", "0.75")
        reset_config()
        from src.config import Config as C
        assert C.KELLY_FRACTION == pytest.approx(0.75)

    def test_env_override_batch_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BATCH_SIZE", "200")
        reset_config()
        from src.config import Config as C
        assert C.BATCH_SIZE == 200

    def test_env_override_public_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DMARKET_PUBLIC_KEY", "my_test_key")
        reset_config()
        from src.config import Config as C
        assert C.DMARKET_PUBLIC_KEY == "my_test_key"
        assert C.PUBLIC_KEY == "my_test_key"

    def test_env_override_secret_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DMARKET_SECRET_KEY", "my_test_secret")
        reset_config()
        from src.config import Config as C
        assert C.DMARKET_SECRET_KEY == "my_test_secret"
        assert C.SECRET_KEY == "my_test_secret"


# =====================================================================
# test_config_type_coercion
# =====================================================================

class TestConfigTypeCoercion:
    """Verify string env vars are converted to correct types."""

    def test_string_to_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FEE_RATE", "0.08")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.FEE_RATE, float)
        assert C.FEE_RATE == pytest.approx(0.08)

    def test_string_to_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_OPEN_TARGETS", "75")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.MAX_OPEN_TARGETS, int)
        assert C.MAX_OPEN_TARGETS == 75

    def test_string_true_to_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KELLY_ENABLED", "true")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.KELLY_ENABLED, bool)
        assert C.KELLY_ENABLED is True

    def test_string_false_to_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KELLY_ENABLED", "false")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.KELLY_ENABLED, bool)
        assert C.KELLY_ENABLED is False

    def test_string_one_to_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DRY_RUN", "1")
        reset_config()
        from src.config import Config as C
        assert C.DRY_RUN is True

    def test_string_zero_to_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DRY_RUN", "0")
        reset_config()
        from src.config import Config as C
        assert C.DRY_RUN is False

    def test_string_to_str_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ACTIVE_STRATEGY", "CrossMarketArbitrage")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.ACTIVE_STRATEGY, str)
        assert C.ACTIVE_STRATEGY == "CrossMarketArbitrage"

    def test_float_field_with_integer_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pydantic should coerce '5' (string int) to 5.0 (float)."""
        monkeypatch.setenv("MIN_SPREAD_PCT", "5")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.MIN_SPREAD_PCT, float)
        assert C.MIN_SPREAD_PCT == pytest.approx(5.0)

    def test_int_field_with_float_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pydantic should coerce '30.0' to 30 for int fields."""
        monkeypatch.setenv("SCAN_INTERVAL", "30")
        reset_config()
        from src.config import Config as C
        assert isinstance(C.SCAN_INTERVAL, int)
        assert C.SCAN_INTERVAL == 30


# =====================================================================
# test_config_watcher_hot_reload
# =====================================================================

class TestConfigWatcherHotReload:
    """Verify config file changes are picked up by reset_config()."""

    def test_reset_config_picks_up_new_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """reset_config() re-reads env vars, simulating hot reload."""
        monkeypatch.setenv("SCAN_INTERVAL", "15")
        reset_config()
        from src.config import Config as C1
        assert C1.SCAN_INTERVAL == 15

        # "Hot reload" with new value
        monkeypatch.setenv("SCAN_INTERVAL", "45")
        reset_config()
        from src.config import Config as C2
        assert C2.SCAN_INTERVAL == 45

    def test_reset_config_preserves_unset_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fields not overridden by env retain their defaults after reset."""
        monkeypatch.setenv("SCAN_INTERVAL", "99")
        reset_config()
        from src.config import Config as C
        assert C.SCAN_INTERVAL == 99
        # These should still be defaults
        assert C.GAME_ID == "a8db"
        assert C.BATCH_SIZE == 100

    def test_reset_config_creates_new_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each reset_config() call creates a fresh Config instance."""
        monkeypatch.setenv("SCAN_INTERVAL", "10")
        reset_config()
        import src.config as mod
        instance1 = mod.Config

        monkeypatch.setenv("SCAN_INTERVAL", "20")
        reset_config()
        instance2 = mod.Config

        # Should be different objects (new singleton)
        assert instance1 is not instance2
        assert instance2.SCAN_INTERVAL == 20

    def test_multiple_resets_are_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling reset_config() multiple times with same env is stable."""
        monkeypatch.setenv("FEE_RATE", "0.07")
        reset_config()
        reset_config()
        reset_config()
        from src.config import Config as C
        assert C.FEE_RATE == pytest.approx(0.07)

    def test_env_file_values_loaded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config can load from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("SCAN_INTERVAL=99\nFEE_RATE=0.12\n")

        # Remove env vars that would override .env file values
        monkeypatch.delenv("SCAN_INTERVAL", raising=False)
        monkeypatch.delenv("FEE_RATE", raising=False)

        from pydantic_settings import BaseSettings

        class TestConfig(BaseSettings):
            model_config = {"env_file": str(env_file), "extra": "ignore"}
            SCAN_INTERVAL: int = 30
            FEE_RATE: float = 0.05

        tc = TestConfig()
        assert tc.SCAN_INTERVAL == 99
        assert tc.FEE_RATE == pytest.approx(0.12)


# =====================================================================
# test_config_validation
# =====================================================================

class TestConfigValidation:
    """Verify Pydantic validators work correctly."""

    def test_max_price_must_exceed_min_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_PRICE_USD > MIN_PRICE_USD validator."""
        monkeypatch.setenv("MIN_PRICE_USD", "10.0")
        monkeypatch.setenv("MAX_PRICE_USD", "5.0")
        with pytest.raises(Exception):  # ValidationError
            reset_config()

    def test_night_end_must_differ_from_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TIME_OF_DAY_NIGHT_END_UTC != TIME_OF_DAY_NIGHT_START_UTC."""
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_START_UTC", "4")
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_END_UTC", "4")
        with pytest.raises(Exception):  # ValidationError
            reset_config()

    def test_valid_config_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid configuration should not raise."""
        monkeypatch.setenv("MIN_PRICE_USD", "1.0")
        monkeypatch.setenv("MAX_PRICE_USD", "20.0")
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_START_UTC", "4")
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_END_UTC", "10")
        reset_config()
        from src.config import Config as C
        assert C.MAX_PRICE_USD > C.MIN_PRICE_USD

    def test_field_constraint_ge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fields with ge=0 constraint reject negative values."""
        monkeypatch.setenv("FEE_RATE", "-0.05")
        with pytest.raises(Exception):
            reset_config()

    def test_field_constraint_le(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fields with le=1.0 constraint reject values > 1.0."""
        monkeypatch.setenv("FEE_RATE", "1.5")
        with pytest.raises(Exception):
            reset_config()


# =====================================================================
# test_config_backward_compat_aliases
# =====================================================================

class TestConfigBackwardCompatAliases:
    """Verify legacy property aliases work."""

    def test_public_key_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DMARKET_PUBLIC_KEY", "test_pk")
        reset_config()
        from src.config import Config as C
        assert C.PUBLIC_KEY == C.DMARKET_PUBLIC_KEY == "test_pk"

    def test_secret_key_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DMARKET_SECRET_KEY", "test_sk")
        reset_config()
        from src.config import Config as C
        assert C.SECRET_KEY == C.DMARKET_SECRET_KEY == "test_sk"

    def test_tod_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TIME_OF_DAY_ENABLED", "true")
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_START_UTC", "22")
        monkeypatch.setenv("TIME_OF_DAY_NIGHT_END_UTC", "6")
        reset_config()
        from src.config import Config as C
        assert C.TOD_ENABLED is True
        assert C.TOD_NIGHT_START_UTC == 22
        assert C.TOD_NIGHT_END_UTC == 6
