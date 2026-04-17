"""
PriceHistoryDB — Native Bifurcated SQLite storage (v8.0).

Splits trading state and historical analysis into two distinct physical databases:
1. dmarket_state.db   — (OLTP) Fast transactions: orders, inventory, scan state.
2. dmarket_history.db — (OLAP) Bulk analytical data: price observations.

This eliminates write-lock contention during heavy market scans.
"""

import sqlite3
import logging
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger("PriceHistoryDB")


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
                    status      TEXT    NOT NULL DEFAULT 'idle', -- 'idle', 'selling', 'sold'
                    acquired_at REAL    NOT NULL,
                    unlock_at   REAL    NOT NULL DEFAULT 0, -- v9.0 Trade Lock timestamp
                    sold_at     REAL
                )
            """)
            # Migration: Ensure unlock_at exists in older DBs
            try:
                self.state_conn.execute("ALTER TABLE virtual_inventory ADD COLUMN unlock_at REAL NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass # Column already exists

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

    def record_virtual_sale(self, item_id: int, sell_price: float, fee_paid: float):
        with self.state_conn:
            row = self.state_conn.execute("SELECT buy_price FROM virtual_inventory WHERE id = ?", (item_id,)).fetchone()
            if not row: return
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
