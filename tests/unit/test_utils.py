"""Tests for utils — exceptions, vault provider."""

from __future__ import annotations

from unittest.mock import patch

from src.utils.exceptions import (
    BotError,
    ConfigError,
    NetworkError,
    RiskError,
    TradingError,
)


class TestExceptions:

    def test_bot_error(self):
        e = BotError("test")
        assert str(e) == "test"

    def test_config_error_inherits(self):
        e = ConfigError("bad config")
        assert isinstance(e, BotError)

    def test_trading_error_inherits(self):
        e = TradingError("trade failed")
        assert isinstance(e, BotError)

    def test_risk_error_inherits(self):
        e = RiskError("risk blocked")
        assert isinstance(e, BotError)

    def test_network_error_inherits(self):
        e = NetworkError("timeout")
        assert isinstance(e, BotError)
