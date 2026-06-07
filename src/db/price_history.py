"""
⚠️  DEPRECATED — DO NOT USE THIS FILE.

The active implementation lives in `src/db/price_history/` (a Python
package with mixin-based architecture). Python prefers packages over
modules of the same name, so this file is shadowed by the package.

This file is kept ONLY for historical reference and will be removed
in a future cleanup. All edits should go to the package files:
    src/db/price_history/core.py        — PriceHistoryDB orchestrator
    src/db/price_history/inventory.py    — virtual_inventory + helpers
    src/db/price_history/state.py        — scanning_state
    src/db/price_history/history.py      — price observations
    src/db/price_history/targets.py      — active_targets
    src/db/price_history/asset_status.py — asset_status (v12.2)
    src/db/price_history/low_fee.py      — low_fee_cache

Original (v8.0 monolithic) implementation preserved below for reference.

TODO(remove-deprecated-shim): Delete this entire file once:
  1. The package at src/db/price_history/ has been stable for ≥1 release.
  2. A grep across the repo (excluding this file) shows 0 references to
     `from src.db.price_history import X` (other than the package import).
  3. The DeprecationWarning has been logged in production for ≥30 days
     with no breakage reported.
Until then, the file is harmless — Python's package import shadow
mechanism routes all real usage to src/db/price_history/__init__.py.
"""

# Original (deprecated) implementation follows. Kept for git history only.
# DO NOT IMPORT FROM THIS FILE — use `src.db.price_history.price_db` instead.

import sqlite3
import logging
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger("PriceHistoryDB_DEPRECATED")
# Intentionally NOT creating a PriceHistoryDB instance here to avoid
# double-init with the package version.

class _DeprecatedStub:
    """Stub that raises if anyone tries to use this file."""
    def __getattr__(self, name):
        raise RuntimeError(
            f"src.db.price_history (the .py file) is DEPRECATED. "
            f"Use `from src.db.price_history import price_db` instead. "
            f"You tried to access: {name}"
        )

# If anyone somehow imports `from src.db.price_history import X` from this
# file, give them a clear error.
_globals = list(globals().keys())
# Preserve only module metadata; replace classes with stubs.
_DELETED = ('PriceHistoryDB', 'price_db')
for _name in _DELETED:
    if _name in _globals:
        del globals()[_name]

# Show a deprecation warning at import time
import warnings  # noqa: E402
warnings.warn(
    "src.db.price_history (the .py file) is deprecated; "
    "use the package at src.db.price_history/ instead.",
    DeprecationWarning,
    stacklevel=2,
)


class PriceHistoryDB:
    """Bifurcated SQLite-backed price history with trend analysis."""

    def __init__(self, state_db: str = "dmarket_state.db", history_db: str = "dmarket_history.db"):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_path = self.data_dir / state_db
        self.history_path = self.data_dir / history_db
        
        # Initialize Connections
        self.state_conn = sqlite3.connect(str(self.state_path), check_same_thread=False)
        self.state_conn.row_factory = sqlite3.Row
        
        self.history_conn = sqlite3.connect(str(self.history_path), check_same_thread=False)
        self.history_conn.row_factory = sqlite3.Row
        
        self._init_schemas()

    def _init_schemas(self):
        """Initialize appropriate tables in each database."""
        # --- STATE DB (OLTP) ---
        with self.state_conn:
            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS scanning_state (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  REAL NOT NULL
                )
            """)
            self.state_conn.execute("""
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
                    dm_item_id   TEXT,    -- DMarket's real itemId (for the /user-offers/create endpoint)
                    dm_offer_id  TEXT,    -- DMarket's offerId once we list it (for /edit and /delete)
                    listed_at    REAL,    -- when we successfully called create_sell_offer
                    list_error   TEXT     -- last error from a failed listing attempt
                )
            """)
            # Migration: Ensure unlock_at exists in older DBs
            try:
                self.state_conn.execute("ALTER TABLE virtual_inventory ADD COLUMN unlock_at REAL NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass # Column already exists
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
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_dm_item ON virtual_inventory(dm_item_id)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_dm_offer ON virtual_inventory(dm_offer_id)"
            )
            self.state_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vinv_status ON virtual_inventory(status)"
            )

            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS missed_opportunities (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    expected_sell REAL  NOT NULL,
                    reason      TEXT    NOT NULL,
                    timestamp   REAL    NOT NULL
                )
            """)
            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    decision    TEXT    NOT NULL, -- 'buy', 'skip', 'target'
                    reason      TEXT    NOT NULL,
                    details     TEXT,
                    timestamp   REAL    NOT NULL
                )
            """)
            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS active_targets (
                    item_id     TEXT PRIMARY KEY,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    created_at  REAL    NOT NULL
                )
            """)
            self.state_conn.execute("CREATE INDEX IF NOT EXISTS idx_targets_created ON active_targets(created_at)")
            
            # Temporary safety check: remove price_history from state_db if it exists after migration
            try:
                self.state_conn.execute("DROP TABLE IF EXISTS price_history")
            except sqlite3.OperationalError:
                pass
        
        # --- HISTORY DB (OLAP) ---
        with self.history_conn:
            self.history_conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'csfloat',
                    recorded_at REAL    NOT NULL
                )
            """)
            self.history_conn.execute("CREATE INDEX IF NOT EXISTS idx_price_recorded ON price_history(recorded_at)")
            self.history_conn.execute("CREATE INDEX IF NOT EXISTS idx_price_name ON price_history(hash_name)")
            
            # Optimization Pragmas for History (Analytical heavy)
            self.history_conn.execute("PRAGMA journal_mode = WAL")
            self.history_conn.execute("PRAGMA synchronous = normal")
            self.history_conn.execute("PRAGMA temp_store = memory")

        logger.info(f"💾 Engine v8.0 Bifurcation: State@{self.state_path.name}, History@{self.history_path.name}")

    # ------------------------------------------------------------------
    # Write (HISTORY)
    # ------------------------------------------------------------------
    def record_price(self, hash_name: str, price: float, source: str = "csfloat"):
        """Insert a new price observation into the history DB."""
        with self.history_conn:
            self.history_conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                (hash_name, price, source, time.time()),
            )

    # ------------------------------------------------------------------
    # Read (HISTORY)
    # ------------------------------------------------------------------
    def get_latest_price(self, hash_name: str, max_age_seconds: int = 10800) -> Optional[float]:
        cutoff = time.time() - max_age_seconds
        row = self.history_conn.execute(
            "SELECT price FROM price_history WHERE hash_name = ? AND recorded_at > ? ORDER BY recorded_at DESC LIMIT 1",
            (hash_name, cutoff),
        ).fetchone()
        return row["price"] if row else None

    def get_recent_prices(self, hash_name: str, days: int = 7) -> List[Tuple[float, float]]:
        cutoff = time.time() - (days * 86400)
        rows = self.history_conn.execute(
            "SELECT price, recorded_at FROM price_history WHERE hash_name = ? AND recorded_at > ? ORDER BY recorded_at DESC",
            (hash_name, cutoff),
        ).fetchall()
        return [(r["price"], r["recorded_at"]) for r in rows]

    def is_crashing(self, hash_name: str, consecutive_drops: int = 3) -> bool:
        prices = self.get_recent_prices(hash_name, days=14)
        if len(prices) < consecutive_drops + 1:
            return False
        for i in range(consecutive_drops):
            if prices[i][0] >= prices[i + 1][0]:
                return False
        return True

    def get_avg_price(self, hash_name: str, days: int = 7) -> Optional[float]:
        cutoff = time.time() - (days * 86400)
        row = self.history_conn.execute(
            "SELECT AVG(price) as avg_price FROM price_history WHERE hash_name = ? AND recorded_at > ?",
            (hash_name, cutoff),
        ).fetchone()
        return row["avg_price"] if row and row["avg_price"] else None

    # ------------------------------------------------------------------
    # State Persistence (STATE)
    # ------------------------------------------------------------------
    def save_state(self, key: str, value: str):
        with self.state_conn:
            self.state_conn.execute(
                "INSERT OR REPLACE INTO scanning_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, time.time())
            )

    def get_state(self, key: str) -> Optional[str]:
        row = self.state_conn.execute(
            "SELECT value FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Virtual Assets (STATE)
    # ------------------------------------------------------------------
    def add_virtual_item(self, hash_name: str, buy_price: float, trade_lock_hours: int = 168):
        """Add item to virtual sandbox inventory (v9.0 with Trade Lock)."""
        now = time.time()
        unlock_at = now + (trade_lock_hours * 3600)
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO virtual_inventory (hash_name, buy_price, acquired_at, unlock_at, status) VALUES (?, ?, ?, ?, 'idle')",
                (hash_name, buy_price, now, unlock_at)
            )
        logger.info(f"📦 [DB] Virtual item added: {hash_name} (Unlocked at: {time.ctime(unlock_at)})")

    def get_virtual_inventory(self, status: str = 'idle', only_unlocked: bool = False) -> List[sqlite3.Row]:
        """Fetch virtual items. v9.0 adds only_unlocked filter."""
        query = "SELECT * FROM virtual_inventory WHERE status = ?"
        params = [status]
        
        if only_unlocked:
            query += " AND unlock_at <= ?"
            params.append(time.time())
            
        return self.state_conn.execute(query, params).fetchall()

    def get_total_equity(self, current_balance: float) -> Dict[str, float]:
        """Sandbox v9.5: Calculates Total Equity (Cash + Virtual Asset Value)."""
        row = self.state_conn.execute(
            "SELECT SUM(buy_price) as total_value, COUNT(*) as item_count FROM virtual_inventory WHERE status != 'sold'"
        ).fetchone()
        
        asset_value = row["total_value"] or 0.0
        item_count = row["item_count"] or 0
        
        return {
            "cash": current_balance,
            "assets": asset_value,
            "total": current_balance + asset_value,
            "count": item_count
        }

    def calculate_vwap(self, hash_name: str) -> float:
        """Calculates Volume-Weighted Average Price for currently held items."""
        row = self.state_conn.execute(
            "SELECT AVG(buy_price) as avg_price FROM virtual_inventory WHERE hash_name = ? AND status != 'sold'",
            (hash_name,)
        ).fetchone()
        return row["avg_price"] or 0.0

    def record_missed_opportunity(self, hash_name: str, price: float, expected_sell: float, reason: str):
        """Phase 7: Records items we skipped but might have been profitable."""
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO missed_opportunities (hash_name, price, expected_sell, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (hash_name, price, expected_sell, reason, time.time())
            )

    def log_decision(self, hash_name: str, decision: str, reason: str, details: str = ""):
        """Phase 7: 'Self-Reflection' log - why the bot did what it did."""
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO decision_logs (hash_name, decision, reason, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (hash_name, decision, reason, details, time.time())
            )

    def backup_state(self, tag: str = "snapshot"):
        """Creates a snapshot of the current trading state."""
        import shutil
        dest = self.data_dir / f"state_{tag}.db"
        self.state_conn.commit()
        shutil.copy2(self.state_path, dest)
        logger.info(f"💾 [DB] State snapshot saved: {dest.name}")

    def restore_state(self, tag: str = "snapshot"):
        """Restores the trading state from a snapshot."""
        import shutil
        src = self.data_dir / f"state_{tag}.db"
        if not src.exists():
            logger.error(f"❌ [DB] Snapshot {tag} not found!")
            return
        self.state_conn.close()
        shutil.copy2(src, self.state_path)
        # Reconnect
        self.state_conn = sqlite3.connect(str(self.state_path), check_same_thread=False)
        self.state_conn.row_factory = sqlite3.Row
        logger.info(f"🔄 [DB] State restored from: {src.name}")

    def update_virtual_status(self, item_id: int, new_status: str):
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET status = ? WHERE id = ?",
                (new_status, item_id)
            )

    # ------------------------------------------------------------------
    # v12.5: Production sell-side helpers
    # ------------------------------------------------------------------
    def attach_dm_item_id(self, row_id: int, dm_item_id: str) -> None:
        """Link a virtual_inventory row to its real DMarket itemId.

        Called when we either:
        - Bought an item and DMarket returned the itemId (after a successful buy)
        - Pulled an item from DMarket inventory sync and want to track it locally
        """
        if not dm_item_id:
            return
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET dm_item_id = ? WHERE id = ?",
                (dm_item_id, row_id),
            )

    def find_by_dm_item_id(self, dm_item_id: str) -> Optional[sqlite3.Row]:
        """Look up virtual_inventory by DMarket's itemId (for inventory sync)."""
        if not dm_item_id:
            return None
        return self.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE dm_item_id = ? ORDER BY id DESC LIMIT 1",
            (dm_item_id,),
        ).fetchone()

    def find_by_dm_offer_id(self, dm_offer_id: str) -> Optional[sqlite3.Row]:
        """Look up virtual_inventory by DMarket's offerId (for sell notifications)."""
        if not dm_offer_id:
            return None
        return self.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE dm_offer_id = ? ORDER BY id DESC LIMIT 1",
            (dm_offer_id,),
        ).fetchone()

    def mark_listed(self, row_id: int, dm_offer_id: str, list_price: float) -> None:
        """Mark a virtual item as successfully listed on DMarket.

        Status flow: idle → listed (or re-listed: selling → listed).
        listed_at is the timestamp used by reprice_unsold_offers to detect
        stale listings (older than REPRICE_AFTER_HOURS).
        """
        with self.state_conn:
            self.state_conn.execute(
                """UPDATE virtual_inventory
                   SET status = 'listed',
                       dm_offer_id = ?,
                       sell_price = ?,
                       listed_at = ?,
                       list_error = NULL
                   WHERE id = ?""",
                (dm_offer_id, list_price, time.time(), row_id),
            )

    def mark_list_failed(self, row_id: int, error_msg: str) -> None:
        """Record a failed listing attempt; status stays 'idle' so we retry next cycle."""
        with self.state_conn:
            self.state_conn.execute(
                """UPDATE virtual_inventory
                   SET list_error = ?
                   WHERE id = ?""",
                (error_msg[:500] if error_msg else None, row_id),
            )

    def get_stale_listings(self, max_age_seconds: int) -> List[sqlite3.Row]:
        """Get items that have been listed for >max_age_seconds (caller passes REPRICE_AFTER_HOURS * 3600).

        Used by reprice_unsold_offers to find listings that haven't sold and need price drops.
        """
        cutoff = time.time() - max_age_seconds
        return self.state_conn.execute(
            """SELECT * FROM virtual_inventory
               WHERE status = 'listed'
                 AND listed_at IS NOT NULL
                 AND listed_at < ?
               ORDER BY listed_at ASC""",
            (cutoff,),
        ).fetchall()

    def get_recent_sales(self, since_ts: float) -> List[sqlite3.Row]:
        """Get items sold since timestamp (for daily PnL calc)."""
        return self.state_conn.execute(
            """SELECT * FROM virtual_inventory
               WHERE status = 'sold' AND sold_at > ?
               ORDER BY sold_at DESC""",
            (since_ts,),
        ).fetchall()

    def get_daily_realized_pnl(self, since_ts: float) -> float:
        """Sum of profit on items sold since timestamp (for daily briefing)."""
        row = self.state_conn.execute(
            "SELECT COALESCE(SUM(profit), 0) as pnl FROM virtual_inventory WHERE status = 'sold' AND sold_at > ?",
            (since_ts,),
        ).fetchone()
        return float(row["pnl"] or 0.0)

    def record_virtual_sale(self, item_id: int, sell_price: float, fee_paid: float):
        with self.state_conn:
            row = self.state_conn.execute("SELECT buy_price FROM virtual_inventory WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return
            profit = sell_price - row["buy_price"] - fee_paid
            self.state_conn.execute(
                """UPDATE virtual_inventory 
                   SET status = 'sold', sell_price = ?, fee_paid = ?, profit = ?, sold_at = ?
                   WHERE id = ?""",
                (sell_price, fee_paid, profit, time.time(), item_id)
            )

    # ------------------------------------------------------------------
    # Targets (STATE)
    # ------------------------------------------------------------------
    def record_placed_target(self, item_id: str, hash_name: str, price: float):
        with self.state_conn:
            self.state_conn.execute(
                "INSERT OR REPLACE INTO active_targets (item_id, hash_name, price, created_at) VALUES (?, ?, ?, ?)",
                (item_id, hash_name, price, time.time())
            )

    def has_target_been_placed(self, item_id: str, max_age_seconds: int = 2592000) -> bool:
        cutoff = time.time() - max_age_seconds
        row = self.state_conn.execute(
            "SELECT 1 FROM active_targets WHERE item_id = ? AND created_at > ?",
            (item_id, cutoff)
        ).fetchone()
        return row is not None

    def close(self):
        self.state_conn.close()
        self.history_conn.close()


# Singleton instance
price_db = PriceHistoryDB()
