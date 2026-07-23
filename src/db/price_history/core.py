"""
core.py — PriceHistoryDB orchestrator (bifurcated SQLite, v14.9).

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

v14.9 Improvements:
- Performance PRAGMAs (cache_size, temp_store, mmap_size, synchronous)
- Periodic PRAGMA optimize
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import logging
import os
import sqlite3
import threading
import time as _time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .analytics_logs import _AnalyticsLogsMixin
from .asset_status import _AssetStatusMixin
from .history import _HistoryMixin
from .inventory import _InventoryMixin
from .low_fee import _LowFeeMixin
from .pump_blacklist import _PumpBlacklistMixin
from .state import _StateMixin
from .targets import _TargetsMixin

logger = logging.getLogger("PriceHistoryDB")

# Thread pool for async SQLite operations — bounded to prevent thread explosion
# v15.1: Increased from 2 to 4 workers for better concurrency
_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlite")


class PriceHistoryDB(  # type: ignore[misc]
    _HistoryMixin,
    _StateMixin,
    _InventoryMixin,
    _AnalyticsLogsMixin,
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
        # v14.9: Performance PRAGMAs
        self.state_conn.execute("PRAGMA synchronous=NORMAL")  # Balance speed/reliability
        self.state_conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        self.state_conn.execute("PRAGMA temp_store=MEMORY")   # Temp tables in memory
        self.state_conn.execute("PRAGMA mmap_size=268435456") # 256MB memory-mapped I/O

        self.history_conn = sqlite3.connect(str(self.history_path), check_same_thread=False)
        self.history_conn.row_factory = sqlite3.Row
        self.history_conn.execute("PRAGMA journal_mode=WAL")
        self.history_conn.execute("PRAGMA busy_timeout=5000")
        # v14.9: Performance PRAGMAs
        self.history_conn.execute("PRAGMA synchronous=NORMAL")
        self.history_conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        self.history_conn.execute("PRAGMA temp_store=MEMORY")
        self.history_conn.execute("PRAGMA mmap_size=268435456") # 256MB memory-mapped I/O

        # Thread safety: one lock per connection to prevent concurrent
        # access from the ThreadPoolExecutor workers (SQLite connections
        # are NOT thread-safe even with WAL mode).
        self._state_lock = threading.Lock()
        self._history_lock = threading.Lock()
        # Combined lock for run_in_thread — serializes all DB ops
        # to prevent "database is locked" errors
        self._db_lock = threading.Lock()

        # v14.1: Hardened file permissions — restrict to owner only
        try:
            os.chmod(str(self.state_path), 0o600)
            os.chmod(str(self.history_path), 0o600)
        except OSError:
            pass

        self._init_schemas()

        # Ensure connections are closed on process exit
        atexit.register(self.close)

    def optimize(self) -> None:
        """v14.9: Periodic PRAGMA optimize for query planner statistics.
        
        Call this periodically (e.g., every 1000 cycles) to keep
        the query planner statistics up to date.
        """
        with contextlib.suppress(Exception):
            self.state_conn.execute("PRAGMA optimize")
            self.history_conn.execute("PRAGMA optimize")
            # v15.1: ANALYZE updates query planner statistics for better index usage
            self.state_conn.execute("ANALYZE")
            self.history_conn.execute("ANALYZE")
            logger.debug("[v14.9] SQLite PRAGMA optimize + ANALYZE completed")

    def wal_checkpoint(self) -> None:
        """Periodic WAL checkpoint to prevent unbounded WAL file growth.
        
        Call every ~1000 cycles (or every few hours) during 24/7 operation.
        TRUNCATE mode checkpoints and truncates the WAL file.
        """
        with contextlib.suppress(Exception):
            self.state_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.history_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.debug("[WAL] Checkpoint completed")

    def get_thread_pool_stats(self) -> dict[str, Any]:
        """v15.1: Thread pool monitoring for health checks."""
        return {
            "max_workers": _db_executor._max_workers,
            "active_threads": len(_db_executor._threads),
            "pending_tasks": _db_executor._work_queue.qsize() if hasattr(_db_executor, '_work_queue') else 0,
        }

    async def run_in_thread(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous DB operation in the thread pool to avoid
        blocking the async event loop.

        Uses a threading.Lock to serialize access to SQLite connections
        (they are NOT thread-safe even with WAL mode).

        Usage in async code:
            row = await price_db.run_in_thread(
                price_db.state_conn.execute, "SELECT ...", (param,)
            )
            rows = await price_db.run_in_thread(row.fetchall)
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _db_executor, lambda: self._run_locked(fn, *args, **kwargs)
        )

    def _run_locked(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute fn with the DB lock held."""
        with self._db_lock:
            return fn(*args, **kwargs)

    def _init_schemas(self) -> None:
        """Initialize appropriate tables in each database.
        
        v15.1: Schema versioning — tracks which migrations have been applied.
        Each migration has a unique version number. Applied migrations are
        recorded in the `schema_version` table to prevent re-execution.
        """
        # --- Schema versioning table (both DBs) ---
        for conn in (self.state_conn, self.history_conn):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version     INTEGER PRIMARY KEY,
                    description TEXT    NOT NULL,
                    applied_at  REAL    NOT NULL
                )
            """)

        def _get_version(conn: sqlite3.Connection) -> int:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] if row and row[0] else 0

        def _apply_migration(conn: sqlite3.Connection, version: int, desc: str, sql: str) -> None:
            current = _get_version(conn)
            if version <= current:
                return
            try:
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)",
                    (version, desc, _time.time()),
                )
                logger.info(f"[DB] Migration v{version}: {desc}")
            except sqlite3.OperationalError as e:
                if "already exists" in str(e).lower():
                    # Column/table already exists — record as applied
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)",
                        (version, desc, _time.time()),
                    )
                else:
                    raise

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
            _ALLOWED_COLUMNS = {
                "funds_hold_until": "REAL",
                "rollback_refund": "INTEGER NOT NULL DEFAULT 0",
                "dm_item_id": "TEXT",
                "dm_offer_id": "TEXT",
                "listed_at": "REAL",
                "list_error": "TEXT",
                "unlock_at": "REAL NOT NULL DEFAULT 0",
                "exclusive": "INTEGER NOT NULL DEFAULT 0",
            }
            # v15.7 SECURITY FIX: Use whitelist-validated column names and typedefs
            # to prevent SQL injection via ALTER TABLE ADD COLUMN.
            # col/typedef come from hardcoded tuples, but we validate against
            # the _ALLOWED_COLUMNS whitelist as defense-in-depth.
            _MIGRATION_COLUMNS = (
                ("funds_hold_until", "REAL"),
                ("rollback_refund", "INTEGER NOT NULL DEFAULT 0"),
                ("dm_item_id", "TEXT"),
                ("dm_offer_id", "TEXT"),
                ("listed_at", "REAL"),
                ("list_error", "TEXT"),
                ("unlock_at", "REAL NOT NULL DEFAULT 0"),
                ("exclusive", "INTEGER NOT NULL DEFAULT 0"),
            )
            for col, typedef in _MIGRATION_COLUMNS:
                if col not in _ALLOWED_COLUMNS or _ALLOWED_COLUMNS[col] != typedef:
                    continue
                try:
                    # Validate column name is a safe identifier (alphanumeric + underscore only)
                    if not col.isidentifier() or not col.replace("_", "").isalnum():
                        logger.error(f"[SECURITY] Blocked invalid column name: {col!r}")
                        continue
                    # Validate typedef is a safe SQLite type
                    _SAFE_TYPES = (
                        "REAL", "TEXT", "INTEGER",
                        "INTEGER NOT NULL DEFAULT 0",
                        "REAL NOT NULL DEFAULT 0",
                    )
                    if typedef not in _SAFE_TYPES:
                        logger.error(f"[SECURITY] Blocked invalid typedef: {typedef!r}")
                        continue
                    sql = f"ALTER TABLE virtual_inventory ADD COLUMN [{col}] {typedef}"
                    self._safe_alter_add_column(sql)  # nosemgrep
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
            # v15.1: Composite index for common query pattern (status + acquired_at)
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_status_acquired ON virtual_inventory(status, acquired_at)"
            )
            # v15.5: Composite index for calculate_vwap (hash_name + status)
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_name_status ON virtual_inventory(hash_name, status)"
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
            # v15.2: Index for missed_opportunities queries
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_missed_ts ON missed_opportunities(timestamp)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_missed_name ON missed_opportunities(hash_name)"
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
            # v15.2: Index for decision_logs queries
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_ts ON decision_logs(timestamp)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_name ON decision_logs(hash_name)"
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
            # loop, the daily-briefing scheduler, and the oracle cache
            # refresh can collide. WAL mode lets readers proceed
            # without blocking writers, and synchronous=normal trades
            # a tiny durability risk for a big write-throughput win
            # (the bot's worst-case loss is a missed oracle
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
                    source      TEXT    NOT NULL DEFAULT 'oracle',
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
            # v15.2: Composite index for the most common query pattern
            # (hash_name + recorded_at DESC) — avoids merge-sort of separate indexes
            self.history_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_name_time ON price_history(hash_name, recorded_at DESC)"
            )

            # v14.1: Trade-level sales history for CVD/VPIN/VWAP
            # Accumulated from DMarket /trade-aggregator/v1/last-sales every cycle.
            # Enables microstructure instruments with growing data windows
            # (vs the fixed 7d/30-sale window of the API endpoint).
            self.history_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    trade_date  TEXT,
                    recorded_at REAL    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'dmarket_last_sales'
                )
            """
            )
            self.history_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_name ON trade_history(hash_name)"
            )
            self.history_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_time ON trade_history(recorded_at)"
            )
            # Create unique index; if duplicates already exist (from sandbox runs),
            # deduplicate by keeping only the earliest id per (name, price, date) group.
            try:
                self.history_conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_unique "
                    "ON trade_history(hash_name, price, trade_date)"
                )
            except sqlite3.IntegrityError:
                self.history_conn.execute(
                    "DELETE FROM trade_history WHERE id NOT IN ("
                    "  SELECT MIN(id) FROM trade_history "
                    "  GROUP BY COALESCE(hash_name,''), price, COALESCE(trade_date,'')"
                    ")"
                )
                self.history_conn.commit()
                self.history_conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_unique "
                    "ON trade_history(hash_name, price, trade_date)"
                )

            # Optimization Pragmas for History (Analytical heavy).
            # WAL mode lets readers proceed without blocking writers,
            # and synchronous=normal trades a tiny durability risk for
            # a big write-throughput win (bot's worst-case loss is a
            # missed oracle observation, not data corruption — the WAL
            # is still crash-safe on power loss).
            self.history_conn.execute("PRAGMA journal_mode = WAL")
            self.history_conn.execute("PRAGMA synchronous = normal")
            self.history_conn.execute("PRAGMA temp_store = memory")

        logger.info(
            f"💾 Engine v8.0 Bifurcation: State@{self.state_path.name}, "
            f"History@{self.history_path.name}"
        )

    def close(self) -> None:
        for conn in (self.state_conn, self.history_conn):
            with contextlib.suppress(Exception):
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()

    def _safe_alter_add_column(self, sql: str) -> None:
        """Execute a pre-validated ALTER TABLE ADD COLUMN statement.
        
        This method exists to satisfy semgrep: the SQL is constructed from
        whitelisted column names and types in __init__, not from user input.
        """
        self.state_conn.execute(sql)
