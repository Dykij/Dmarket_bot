"""
core.py — PriceHistoryDB orchestrator (bifurcated SQLite, v8.0).

Splits trading state and historical analysis into two physical databases:
    dmarket_state.db   — (OLTP) Fast transactions: orders, inventory, scan state
    dmarket_history.db — (OLAP) Bulk analytical data: price observations

Composes focused mixins for each table group:
    history.py       — price_history (observations + liquidez + wash trading)
    state.py         — scanning_state (cursor, etc.)
    inventory.py     — virtual_inventory + decision_logs + missed_opportunities
    targets.py       — active_targets (placed buy orders)
    asset_status.py  — asset_status (v12.2 trade_protected, reverted)
    low_fee.py       — low_fee_cache (v12.0 daily refresh)
    pump_blacklist.py — pump_blacklist (v12.7 FOMO protection, persistent)
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .asset_status import _AssetStatusMixin
from .history import _HistoryMixin
from .inventory import _InventoryMixin
from .low_fee import _LowFeeMixin
from .pump_blacklist import _PumpBlacklistMixin
from .state import _StateMixin
from .targets import _TargetsMixin

logger = logging.getLogger("PriceHistoryDB")


class PriceHistoryDB(  # type: ignore[misc]
    _HistoryMixin,
    _StateMixin,
    _InventoryMixin,
    _TargetsMixin,
    _AssetStatusMixin,
    _LowFeeMixin,
    _PumpBlacklistMixin,
):
    """Bifurcated SQLite-backed price history with trend analysis."""

    def __init__(
        self,
        state_db: str = "dmarket_state.db",
        history_db: str = "dmarket_history.db",
    ) -> None:
        # v12.8: Resolve data_dir from project ROOT, not from src/.
        # File path: src/db/price_history/core.py → 4 .parent levels
        # to reach the project root. (Previous: 3 .parent levels = src/,
        # which silently wrote to src/data/ — now fixed.)
        self.data_dir = Path(__file__).parent.parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.state_path = self.data_dir / state_db
        self.history_path = self.data_dir / history_db

        # Initialize Connections
        self.state_conn = sqlite3.connect(str(self.state_path), check_same_thread=False)
        self.state_conn.row_factory = sqlite3.Row
        # v12.7: Enable WAL mode for better concurrent read/write (P0-4).
        # WAL allows readers and one writer simultaneously, reducing
        # "database is locked" errors in async contexts.
        self.state_conn.execute("PRAGMA journal_mode=WAL")
        self.state_conn.execute("PRAGMA busy_timeout=5000")

        self.history_conn = sqlite3.connect(str(self.history_path), check_same_thread=False)
        self.history_conn.row_factory = sqlite3.Row
        self.history_conn.execute("PRAGMA journal_mode=WAL")
        self.history_conn.execute("PRAGMA busy_timeout=5000")

        self._init_schemas()

    def _init_schemas(self) -> None:
        """Initialize appropriate tables in each database."""
        # --- STATE DB (OLTP) ---
        with self.state_conn:
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scanning_state (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  REAL NOT NULL
                )
            """
            )
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS virtual_inventory (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    buy_price   REAL    NOT NULL,
                    sell_price  REAL,
                    fee_paid    REAL,
                    profit      REAL,
                    status      TEXT    NOT NULL DEFAULT 'idle', -- 'idle', 'listed', 'selling', 'sold', 'failed'
                    acquired_at REAL    NOT NULL,
                    unlock_at   REAL    NOT NULL DEFAULT 0, -- v9.0 Trade Lock timestamp
                    sold_at     REAL,
                    -- v12.5: production sell-side columns
                    dm_item_id   TEXT,    -- DMarket's real itemId (for /user-offers/create)
                    dm_offer_id  TEXT,    -- DMarket's offerId once listed (for /edit and /delete)
                    listed_at    REAL,    -- when we successfully called create_sell_offers_batch
                    list_error   TEXT     -- last error from a failed listing attempt
                )
            """
            )
            # v13.1 migration: funds hold tracking for Trade Protection
            for col, typedef in (
                ("funds_hold_until", "REAL"),
                ("rollback_refund", "INTEGER NOT NULL DEFAULT 0"),
            ):
                try:
                    self.state_conn.execute(
                        f"ALTER TABLE virtual_inventory ADD COLUMN {col} {typedef}"
                    )
                except sqlite3.OperationalError:
                    pass
            # Migration: Ensure unlock_at exists in older DBs
            try:
                self.state_conn.execute(
                    "ALTER TABLE virtual_inventory ADD COLUMN unlock_at REAL NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists
            # v12.5 migrations: production sell-side columns
            for col, typedef in (
                ("dm_item_id", "TEXT"),
                ("dm_offer_id", "TEXT"),
                ("listed_at", "REAL"),
                ("list_error", "TEXT"),
            ):
                try:
                    self.state_conn.execute(
                        f"ALTER TABLE virtual_inventory ADD COLUMN {col} {typedef}"
                    )
                except sqlite3.OperationalError:
                    pass  # already exists
            # v13.0 migration: exclusive flag for keep-forever items
            try:
                self.state_conn.execute(
                    "ALTER TABLE virtual_inventory ADD COLUMN exclusive INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # already exists
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_dm_item ON virtual_inventory(dm_item_id)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_dm_offer ON virtual_inventory(dm_offer_id)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_status ON virtual_inventory(status)"
            )

            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS missed_opportunities (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    expected_sell REAL  NOT NULL,
                    reason      TEXT    NOT NULL,
                    timestamp   REAL    NOT NULL
                )
            """
            )
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    decision    TEXT    NOT NULL, -- 'buy', 'skip', 'target'
                    reason      TEXT    NOT NULL,
                    details     TEXT,
                    timestamp   REAL    NOT NULL
                )
            """
            )
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_targets (
                    item_id     TEXT PRIMARY KEY,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    created_at  REAL    NOT NULL
                )
            """
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_targets_created ON active_targets(created_at)"
            )

            # v12.0: Low-fee items cache (refreshed daily)
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS low_fee_cache (
                    title       TEXT PRIMARY KEY,
                    fee_rate    REAL    NOT NULL,
                    fetched_at  REAL    NOT NULL
                )
            """
            )

            # v12.2: Asset status tracking (trade_protected, reverted, FinalizationTime)
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_status (
                    item_id             TEXT PRIMARY KEY,
                    title               TEXT    NOT NULL,
                    status              TEXT    NOT NULL DEFAULT 'active',
                    finalization_time   REAL    NOT NULL DEFAULT 0,
                    created_at          REAL    NOT NULL,
                    updated_at          REAL    NOT NULL
                )
            """
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_asset_status ON asset_status(status, updated_at)"
            )

            # v12.5: Equity snapshots for crash-recovery + daily PnL.
            # Keeps last 90 days of snapshots for backtesting risk metrics.
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    taken_at    REAL    NOT NULL,
                    snapshot_date TEXT  NOT NULL,  -- YYYY-MM-DD (UTC)
                    cash        REAL    NOT NULL,
                    assets      REAL    NOT NULL,
                    total       REAL    NOT NULL,
                    realized_pnl REAL   NOT NULL DEFAULT 0,
                    note        TEXT
                )
            """
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_equity_date ON equity_snapshots(snapshot_date)"
            )

            # v12.5: Risk event log (kill-switch trips, soft-halts, etc.)
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          REAL    NOT NULL,
                    event_type  TEXT    NOT NULL,
                    severity    TEXT    NOT NULL DEFAULT 'warning',
                    details     TEXT    NOT NULL
                )
            """
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_ts ON risk_events(ts)"
            )

            # v12.7: Persistent pump-blacklist (survives watchdog restarts).
            # The PumpDetector in src/risk/pump_detector.py writes here
            # on every spike detection and reads here at boot. Without
            # this table, the 24h FOMO protection would be lost on
            # any restart (e.g. memory-leak kill by watchdog).
            self.state_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pump_blacklist (
                    hash_name   TEXT PRIMARY KEY,
                    old_price   REAL    NOT NULL,
                    new_price   REAL    NOT NULL,
                    pct_change  REAL    NOT NULL,
                    detected_at REAL    NOT NULL,
                    expires_at  REAL    NOT NULL,
                    alerted     INTEGER NOT NULL DEFAULT 0
                )
            """
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pump_expires ON pump_blacklist(expires_at)"
            )

            # v12.8: Optimization Pragmas for State (OLTP). The state
            # DB is the hot path — concurrent writes from the sniping
            # loop, the daily-briefing scheduler, and the CS2Cap cache
            # refresh can collide. WAL mode lets readers proceed
            # without blocking writers, and synchronous=normal trades
            # a tiny durability risk for a big write-throughput win
            # (the bot's worst-case loss is a missed CS2Cap
            # observation, not data corruption — the WAL is still
            # crash-safe on power loss).
            self.state_conn.execute("PRAGMA journal_mode = WAL")
            self.state_conn.execute("PRAGMA synchronous = normal")
            self.state_conn.execute("PRAGMA temp_store = memory")

        # --- HISTORY DB (OLAP) ---
        with self.history_conn:
            self.history_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'cs2cap',
                    recorded_at REAL    NOT NULL
                )
            """
            )
            self.history_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_recorded ON price_history(recorded_at)"
            )
            self.history_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_name ON price_history(hash_name)"
            )

            # Optimization Pragmas for History (Analytical heavy).
            # WAL mode lets readers proceed without blocking writers,
            # and synchronous=normal trades a tiny durability risk for
            # a big write-throughput win (bot's worst-case loss is a
            # missed CS2Cap observation, not data corruption — the WAL
            # is still crash-safe on power loss).
            self.history_conn.execute("PRAGMA journal_mode = WAL")
            self.history_conn.execute("PRAGMA synchronous = normal")
            self.history_conn.execute("PRAGMA temp_store = memory")

        logger.info(
            f"💾 Engine v8.0 Bifurcation: State@{self.state_path.name}, "
            f"History@{self.history_path.name}"
        )

    def close(self) -> None:
        self.state_conn.close()
        self.history_conn.close()
