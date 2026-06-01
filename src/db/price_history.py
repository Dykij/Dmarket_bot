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
from typing import Optional, List, Tuple, Dict, Any

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

            # v12.0: Low-fee items cache (refreshed daily)
            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS low_fee_cache (
                    title       TEXT PRIMARY KEY,
                    fee_rate    REAL    NOT NULL,
                    fetched_at  REAL    NOT NULL
                )
            """)

            # v12.2: Asset status tracking (trade_protected, reverted, FinalizationTime)
            self.state_conn.execute("""
                CREATE TABLE IF NOT EXISTS asset_status (
                    item_id             TEXT PRIMARY KEY,
                    title               TEXT    NOT NULL,
                    status              TEXT    NOT NULL DEFAULT 'active',
                    finalization_time   REAL    NOT NULL DEFAULT 0,
                    created_at          REAL    NOT NULL,
                    updated_at          REAL    NOT NULL
                )
            """)
            self.state_conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_status ON asset_status(status, updated_at)")

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
                    source      TEXT    NOT NULL DEFAULT 'cs2cap',
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
    def record_price(self, hash_name: str, price: float, source: str = "cs2cap"):
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

    # ------------------------------------------------------------------
    # v12.2 Phase 2.4: Multi-level liquidity verification
    # ------------------------------------------------------------------
    def get_liquidity_metrics(self, hash_name: str, days: int = 23) -> Dict[str, Any]:
        """
        Calculate liquidity metrics for an asset based on historical price observations.
        Mirrors the Gemini-recommended multi-level filter:
        - ALL_SALES (total historical observations)
        - DAYS_COUNT (lookback window in days)
        - SALE_COUNT (sales in window)
        - FIRST_SALE (oldest sale in window, in days)
        - LAST_SALE (most recent sale age, in days)

        Returns dict with metrics and an is_liquid flag computed from Config thresholds.
        """
        prices = self.get_recent_prices(hash_name, days=days)
        now = time.time()

        if not prices:
            return {
                "total_sales": 0,
                "sales_in_window": 0,
                "first_sale_age_days": None,
                "last_sale_age_days": None,
                "is_liquid": False,
                "reason": "no_data",
            }

        timestamps = [t for _, t in prices]
        oldest_ts = min(timestamps)
        newest_ts = max(timestamps)

        first_sale_age_days = (now - oldest_ts) / 86400.0
        last_sale_age_days = (now - newest_ts) / 86400.0

        metrics = {
            "total_sales": len(prices),
            "sales_in_window": len(prices),
            "first_sale_age_days": first_sale_age_days,
            "last_sale_age_days": last_sale_age_days,
            "is_liquid": True,
            "reason": "ok",
        }

        # Apply thresholds from config
        from src.config import Config
        if metrics["total_sales"] < Config.MIN_TOTAL_SALES:
            metrics["is_liquid"] = False
            metrics["reason"] = f"insufficient_total_sales({metrics['total_sales']}<{Config.MIN_TOTAL_SALES})"
        elif metrics["sales_in_window"] < Config.MIN_SALES_IN_WINDOW:
            metrics["is_liquid"] = False
            metrics["reason"] = f"insufficient_window_sales({metrics['sales_in_window']}<{Config.MIN_SALES_IN_WINDOW})"
        elif metrics["first_sale_age_days"] > Config.MAX_FIRST_SALE_AGE_DAYS:
            metrics["is_liquid"] = False
            metrics["reason"] = f"first_sale_too_old({metrics['first_sale_age_days']:.1f}d>{Config.MAX_FIRST_SALE_AGE_DAYS}d)"
        elif metrics["last_sale_age_days"] > Config.MAX_LAST_SALE_AGE_DAYS:
            metrics["is_liquid"] = False
            metrics["reason"] = f"last_sale_too_old({metrics['last_sale_age_days']:.1f}d>{Config.MAX_LAST_SALE_AGE_DAYS}d)"

        return metrics

    def passes_liquidity_filter(self, hash_name: str) -> bool:
        """
        Returns True if asset passes all liquidity thresholds from Config.
        """
        metrics = self.get_liquidity_metrics(hash_name)
        return metrics["is_liquid"]

    def get_avg_price(self, hash_name: str, days: int = 7) -> Optional[float]:
        cutoff = time.time() - (days * 86400)
        row = self.history_conn.execute(
            "SELECT AVG(price) as avg_price FROM price_history WHERE hash_name = ? AND recorded_at > ?",
            (hash_name, cutoff)
        ).fetchone()
        return row["avg_price"] if row and row["avg_price"] else None

    # ------------------------------------------------------------------
    # v12.2 Phase 2.3: Trimmed Mean (resistant to wash trading)
    # ------------------------------------------------------------------
    def get_trimmed_mean(self, hash_name: str, days: int = 14,
                         boost_pct: float = 24.0, max_outliers: int = 3) -> Optional[float]:
        """
        Compute the trimmed mean of historical prices.

        Algorithm:
        1. Get all prices within the time window
        2. Compute the arithmetic mean
        3. Iteratively remove up to `max_outliers` points that exceed the mean
           by `boost_pct`% (in either direction)
        4. Recompute the mean on the cleaned set

        Returns None if no data available.

        Example:
            prices = [10, 10, 10, 100, 10, 10]
            raw_mean = 25
            100 is +300% from mean → outlier, remove
            cleaned = [10, 10, 10, 10, 10]
            trimmed_mean = 10
        """
        prices_with_time = self.get_recent_prices(hash_name, days=days)
        if not prices_with_time:
            return None

        prices = [p for p, _ in prices_with_time]
        if not prices:
            return None

        current_prices = list(prices)
        for _ in range(max_outliers):
            if len(current_prices) < 3:
                break
            mean = sum(current_prices) / len(current_prices)
            if mean <= 0:
                break
            upper = mean * (1.0 + boost_pct / 100.0)
            lower = mean * (1.0 - boost_pct / 100.0)
            # Find the most extreme outlier
            worst_idx = -1
            worst_dev = 0.0
            for i, p in enumerate(current_prices):
                if p > upper:
                    dev = (p - mean) / mean
                    if dev > worst_dev:
                        worst_dev = dev
                        worst_idx = i
                elif p < lower:
                    dev = (mean - p) / mean
                    if dev > worst_dev:
                        worst_dev = dev
                        worst_idx = i
            if worst_idx < 0:
                break  # No more outliers
            current_prices.pop(worst_idx)

        if not current_prices:
            return None
        return sum(current_prices) / len(current_prices)

    def detect_wash_trading(self, hash_name: str, days: int = 14,
                            boost_pct: float = 24.0, max_outliers: int = 3,
                            divergence_pct: float = 50.0) -> bool:
        """
        Returns True if the asset looks LEGITIMATE (not wash-traded).
        Returns False if raw mean is X% higher than trimmed mean,
        indicating anomalous trades inflating the price.

        divergence_pct=50.0 means raw mean is 50% higher than trimmed → flagged.
        """
        trimmed = self.get_trimmed_mean(hash_name, days=days, boost_pct=boost_pct, max_outliers=max_outliers)
        raw = self.get_avg_price(hash_name, days=days)
        if trimmed is None or raw is None:
            return True  # No data, don't flag
        if trimmed <= 0:
            return True
        # If raw mean is much higher than trimmed mean, wash trading suspected
        divergence = ((raw - trimmed) / trimmed) * 100.0
        return divergence < divergence_pct

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

    def cleanup_old_targets(self, max_age_seconds: int = 7776000):
        """
        Remove active_targets entries older than max_age_seconds (default 90 days).
        Keeps the DB clean of stale records.
        """
        cutoff = time.time() - max_age_seconds
        with self.state_conn:
            cur = self.state_conn.execute(
                "DELETE FROM active_targets WHERE created_at < ?", (cutoff,)
            )
            deleted = cur.rowcount
            if deleted:
                logger.info(f"[DB] Cleaned up {deleted} stale active_targets entries")
            return deleted

    # ------------------------------------------------------------------
    # v12.2: Asset Status Tracking (trade_protected, reverted, FinalizationTime)
    # ------------------------------------------------------------------
    def update_asset_status(self, item_id: str, title: str, status: str,
                            finalization_time: float = 0.0) -> None:
        """
        Insert or update asset status. Called when we detect a status change
        from DMarket (trade_protected, reverted, etc.).
        """
        now = time.time()
        with self.state_conn:
            existing = self.state_conn.execute(
                "SELECT created_at FROM asset_status WHERE item_id = ?", (item_id,)
            ).fetchone()
            if existing:
                self.state_conn.execute(
                    """UPDATE asset_status
                       SET title = ?, status = ?, finalization_time = ?, updated_at = ?
                       WHERE item_id = ?""",
                    (title, status, finalization_time, now, item_id)
                )
            else:
                self.state_conn.execute(
                    """INSERT INTO asset_status
                       (item_id, title, status, finalization_time, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (item_id, title, status, finalization_time, now, now)
                )

    def get_asset_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an asset. Returns None if unknown."""
        row = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "item_id": row["item_id"],
            "title": row["title"],
            "status": row["status"],
            "finalization_time": row["finalization_time"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_active_assets(self) -> List[Dict[str, Any]]:
        """Return all assets with status='active' (tradable)."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'active' ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trade_protected_assets(self) -> List[Dict[str, Any]]:
        """Return all assets that are still in trade_protected status."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'trade_protected' ORDER BY finalization_time ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_reverted_assets(self) -> List[Dict[str, Any]]:
        """Return all assets that have been reverted (DMarket rolled back the transaction)."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'reverted' ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reverted(self, item_id: str) -> None:
        """Convenience: mark an asset as reverted."""
        existing = self.get_asset_status(item_id)
        title = existing["title"] if existing else ""
        self.update_asset_status(item_id, title, "reverted", finalization_time=0.0)
        logger.warning(f"[DB] Asset {item_id} ({title}) marked as REVERTED")

    def is_trade_locked(self, item_id: str) -> bool:
        """
        Returns True if the asset is currently trade_protected (locked).
        An asset is locked if:
        - status='trade_protected' AND finalization_time > now (still locked)
        - status='reverted' (always)
        """
        asset = self.get_asset_status(item_id)
        if not asset:
            return False
        if asset["status"] == "reverted":
            return True
        if asset["status"] == "trade_protected":
            fin = asset["finalization_time"]
            if fin <= 0:
                return True  # No end time, assume locked
            return fin > time.time()
        return False

    def is_known_item(self, item_id: str) -> bool:
        """Returns True if we've ever tracked this item_id."""
        row = self.state_conn.execute(
            "SELECT 1 FROM asset_status WHERE item_id = ?", (item_id,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # v12.0: Low-fee items cache (State DB, 24h TTL)
    # ------------------------------------------------------------------
    def save_low_fee_items(self, items: List[Dict[str, Any]]):
        """Replace the entire low-fee cache with fresh items from DMarket."""
        with self.state_conn:
            self.state_conn.execute("DELETE FROM low_fee_cache")
            now = time.time()
            self.state_conn.executemany(
                "INSERT OR REPLACE INTO low_fee_cache (title, fee_rate, fetched_at) VALUES (?, ?, ?)",
                [(item["title"], item["fee_rate"], now) for item in items if item.get("title")]
            )

    def get_low_fee_rate(self, title: str, max_age_seconds: int = 86400) -> Optional[float]:
        """Returns the cached low-fee rate for a title, or None if not in cache / expired."""
        cutoff = time.time() - max_age_seconds
        row = self.state_conn.execute(
            "SELECT fee_rate FROM low_fee_cache WHERE title = ? AND fetched_at > ?",
            (title, cutoff)
        ).fetchone()
        return row["fee_rate"] if row else None

    def low_fee_cache_size(self) -> int:
        row = self.state_conn.execute("SELECT COUNT(*) as c FROM low_fee_cache").fetchone()
        return row["c"] or 0

    def low_fee_cache_age_seconds(self) -> Optional[float]:
        """Returns the age (seconds) of the oldest entry, or None if cache is empty."""
        row = self.state_conn.execute(
            "SELECT MIN(fetched_at) as oldest FROM low_fee_cache"
        ).fetchone()
        if not row or not row["oldest"]:
            return None
        return time.time() - row["oldest"]

    def close(self):
        self.state_conn.close()
        self.history_conn.close()


# Singleton instance
price_db = PriceHistoryDB()
