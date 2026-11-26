"""Contract tests verifying virtual_inventory rows support dict .get()."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import Config
from src.core.target_sniping.cycle_orchestrator import CycleContext, CycleOrchestrator
from src.core.target_sniping.position_guard import _PositionGuardMixin
from src.db.price_history.core import PriceHistoryDB
from src.telegram.control_bot.commands import control as control_mod


@pytest.fixture()
def real_db(tmp_path, monkeypatch):
    """Create a real PriceHistoryDB backed by a temporary directory."""
    monkeypatch.setenv("DMARKET_DATA_DIR", str(tmp_path))
    db = PriceHistoryDB(
        state_db=str(tmp_path / "state.db"),
        history_db=str(tmp_path / "history.db"),
    )
    yield db
    db.close()


class _GuardStub(_PositionGuardMixin):
    def __init__(self) -> None:
        self.client = AsyncMock()
        self._current_agg_prices: dict = {}
        self._background_tasks: set = set()


class _OrchestratorStub(CycleOrchestrator):
    def __init__(self) -> None:
        self.client = AsyncMock()
        self.client.get_real_balance = AsyncMock(return_value=40.0)
        self.deep_scan_counter = 1
        self.resale_cycle_limit = 10
        self.reprice_counter = 1
        self.empty_page_count = 0
        self.pump_detector = None
        self.inventory_mgr = object()
        self.risk = MagicMock()
        self.risk._update_equity = MagicMock()
        self.risk.get_state.return_value = MagicMock(current_drawdown_pct=0.0)


def test_get_virtual_inventory_rows_support_get(real_db: PriceHistoryDB) -> None:
    """Protects src/db/price_history/inventory.py:81 get_virtual_inventory() returning dict-like rows."""
    item_name = "AK-47 | Redline (FT)"
    real_db.add_virtual_item(hash_name=item_name, buy_price=15.5)

    rows = real_db.get_virtual_inventory()

    assert len(rows) == 1
    assert rows[0].get("hash_name") == item_name
    assert rows[0]["hash_name"] == item_name


@pytest.mark.asyncio
async def test_stop_loss_demand_item_on_real_rows(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Protects src/core/target_sniping/position_guard.py:91 check_stop_losses() .get('strategy') on real rows."""
    monkeypatch.setattr(Config, "DEMAND_STRATEGY_ENABLED", True)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_ENABLED", True)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_MIN_AGE_HOURS", 24.0)
    monkeypatch.setattr("src.core.target_sniping.position_guard.STOP_LOSS_PCT", 10.0)
    monkeypatch.setattr("src.core.target_sniping.position_guard.price_db", real_db)

    real_db.add_virtual_item(
        hash_name="AWP | Asiimov (FT)",
        buy_price=10.0,
        trade_lock_hours=0,
        strategy="demand",
    )
    old_ts = time.time() - (36.0 * 3600.0)
    with real_db.state_conn:
        real_db.state_conn.execute(
            "UPDATE virtual_inventory SET acquired_at = ?", (old_ts,)
        )

    guard = _GuardStub()
    guard._get_current_price = AsyncMock(return_value=9.0)  # type: ignore[method-assign]
    guard._execute_liquidation = AsyncMock(return_value=1)  # type: ignore[method-assign]

    result = await guard.check_stop_losses("a8db")

    assert result == 1
    guard._execute_liquidation.assert_called_once()
    assert "stop-loss" in repr(guard._execute_liquidation.call_args)


@pytest.mark.asyncio
async def test_postprocess_equity_includes_inventory_bid(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Protects src/core/target_sniping/cycle_orchestrator.py:449 _stage_postprocess() .get('hash_name') on real rows."""
    monkeypatch.setattr("src.core.target_sniping.cycle_orchestrator.price_db", real_db)
    real_db.add_virtual_item(hash_name="X", buy_price=5.0, trade_lock_hours=0)

    orch = _OrchestratorStub()
    ctx = CycleContext(
        game_id="a8db",
        agg_prices={"X": {"best_bid": 7.5}},
        balance_before=40.0,
    )

    await orch._stage_postprocess(ctx)

    orch.risk._update_equity.assert_called_once_with(47.5)


@pytest.mark.asyncio
async def test_liquidate_confirmation_on_real_rows(
    real_db: PriceHistoryDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Protects src/telegram/control_bot/commands/control.py:464-466 cmd_liquidate() .get() on real rows."""
    monkeypatch.setattr("src.db.price_history.price_db", real_db)
    monkeypatch.setattr(control_mod.state, "client", object())

    item_name = "M4A1-S | Printstream (FT)"
    real_db.add_virtual_item(hash_name=item_name, buy_price=12.0, trade_lock_hours=0)

    message = MagicMock()
    message.answer = AsyncMock()

    await control_mod.cmd_liquidate.__wrapped__(message)

    message.answer.assert_awaited_once()
    reply_text = message.answer.call_args.args[0]
    assert item_name in reply_text
    assert "12.00" in reply_text
