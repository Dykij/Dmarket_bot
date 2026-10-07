"""F2.3: сроки очистки берутся из env (не ниже 7 дней), git-бэкап состояния выключен по умолчанию."""
from pathlib import Path

import pytest

from src.core.target_sniping import scheduler as sch

SRC = Path(sch.__file__).read_text(encoding="utf-8")


def test_retention_defaults_keep_old_behaviour(monkeypatch):
    monkeypatch.delenv("PRICE_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("TRADE_RETENTION_DAYS", raising=False)
    assert sch._retention_days("PRICE_RETENTION_DAYS", 30) == 30
    assert sch._retention_days("TRADE_RETENTION_DAYS", 90) == 90


def test_retention_env_override(monkeypatch):
    monkeypatch.setenv("PRICE_RETENTION_DAYS", "90")
    assert sch._retention_days("PRICE_RETENTION_DAYS", 30) == 90


@pytest.mark.parametrize("raw,expected", [("0", 7), ("-5", 7), ("3", 7), ("abc", 30), ("", 30)])
def test_retention_is_clamped_or_falls_back(monkeypatch, raw, expected):
    monkeypatch.setenv("PRICE_RETENTION_DAYS", raw)
    assert sch._retention_days("PRICE_RETENTION_DAYS", 30) == expected


def test_git_backup_off_by_default(monkeypatch):
    monkeypatch.delenv("STATE_BACKUP_GIT_ENABLED", raising=False)
    assert sch._state_backup_git_enabled() is False


@pytest.mark.parametrize(
    "raw,expected",
    [("true", True), ("1", True), ("yes", True), ("false", False), ("0", False), ("", False)],
)
def test_git_backup_flag_values(monkeypatch, raw, expected):
    monkeypatch.setenv("STATE_BACKUP_GIT_ENABLED", raw)
    assert sch._state_backup_git_enabled() is expected


def test_maintenance_loop_uses_the_helpers():
    assert 'cleanup_old_prices, days=_retention_days("PRICE_RETENTION_DAYS", 30)' in SRC
    assert 'cleanup_old_trades, days=_retention_days("TRADE_RETENTION_DAYS", 90)' in SRC
    assert "if _state_backup_git_enabled():" in SRC
    assert "cleanup_old_prices, days=30)" not in SRC
    assert "cleanup_old_trades, days=90)" not in SRC
