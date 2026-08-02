import contextlib
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from src.db.db_retry import with_db_retry

logger = logging.getLogger("ProfitTracker")

class ProfitTrackerDB:
    def __init__(self, db_path: str = "dmarket_trading.db"):
        self.db_path = Path(__file__).parent.parent.parent / "data" / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        # v12.8: WAL mode for concurrent read/write (P-3).
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        # v15.2: Performance PRAGMAs (matching price_history DB)
        self.conn.execute("PRAGMA synchronous=NORMAL")   # Balance speed/reliability
        self.conn.execute("PRAGMA cache_size=-64000")    # 64MB cache
        self.conn.execute("PRAGMA temp_store=MEMORY")    # Temp tables in memory
        self.conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite schema."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    fee_amount REAL NOT NULL,
                    net_profit REAL NOT NULL,
                    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date DATE PRIMARY KEY,
                    total_profit REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0
                )
            ''')
            # v18.2: Open positions table (buy without matching sell)
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS open_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    buy_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    offer_id TEXT,
                    sold INTEGER DEFAULT 0
                )
            ''')
            # v15.5: Indexes for audit/reporting queries
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_item ON trades(item_name)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_open_positions_item ON open_positions(item_name)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_open_positions_sold ON open_positions(sold)"
            )
        logger.info(f"Profit Tracker DB initialized at {self.db_path}")

    @with_db_retry(operation_name="profit_tracker.record_trade")
    def record_trade(self, item_name: str, buy_price: Decimal, sell_price: Decimal, fee_rate: Decimal):
        """Record a completed round-trip trade."""
        fee_amount = sell_price * fee_rate
        net_profit = (sell_price - fee_amount) - buy_price

        with self.conn:
            self.conn.execute('''
                INSERT INTO trades (item_name, buy_price, sell_price, fee_amount, net_profit)
                VALUES (?, ?, ?, ?, ?)
            ''', (item_name, float(buy_price), float(sell_price), float(fee_amount), float(net_profit)))

            # Upsert daily PnL
            today = datetime.now().date().isoformat()
            self.conn.execute('''
                INSERT INTO daily_pnl (date, total_profit, trades_count)
                VALUES (?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET 
                    total_profit = total_profit + ?,
                    trades_count = trades_count + 1
            ''', (today, net_profit, net_profit))

        logger.info(f"✅ Trade Recorded [{item_name}]: PnL = ${net_profit:.2f}")

    def get_today_pnl(self):
        """Get today's total profit."""
        today = datetime.now().date().isoformat()
        cursor = self.conn.execute('SELECT total_profit, trades_count FROM daily_pnl WHERE date = ?', (today,))
        row = cursor.fetchone()
        if row:
            return {"profit": row["total_profit"], "trades": row["trades_count"]}
        return {"profit": 0.0, "trades": 0}

    @with_db_retry(operation_name="profit_tracker.record_buy")
    def record_buy(self, item_name: str, buy_price: float, offer_id: str = "") -> int:
        """Record a buy event. Returns the open_positions row id."""
        with self.conn:
            cursor = self.conn.execute('''
                INSERT INTO open_positions (item_name, buy_price, offer_id)
                VALUES (?, ?, ?)
            ''', (item_name, buy_price, offer_id))
            row_id = cursor.lastrowid
        logger.info(f"[TRADE-HISTORY] BUY {item_name} @ ${buy_price:.2f} (pos_id={row_id})")
        return row_id

    @with_db_retry(operation_name="profit_tracker.record_sell")
    def record_sell(self, item_name: str, sell_price: float, fee_rate: float = 0.05) -> dict:
        """Record a sell event. Links to earliest open buy, calculates profit.
        Returns dict with buy_price, net_profit, hold_days, or error."""
        # Find earliest unsold position for this item
        row = self.conn.execute('''
            SELECT id, buy_price, buy_date FROM open_positions
            WHERE item_name = ? AND sold = 0
            ORDER BY buy_date ASC LIMIT 1
        ''', (item_name,)).fetchone()

        if not row:
            # No matching buy — record as standalone sell
            logger.warning(f"[TRADE-HISTORY] SELL {item_name} @ ${sell_price:.2f} — NO MATCHING BUY")
            return {"error": "no_matching_buy", "sell_price": sell_price}

        pos_id = row["id"]
        buy_price = row["buy_price"]
        buy_date = row["buy_date"]

        # Calculate profit
        fee_amount = sell_price * fee_rate
        net_profit = (sell_price - fee_amount) - buy_price

        # Calculate hold days
        try:
            buy_dt = datetime.fromisoformat(buy_date)
            hold_days = (datetime.now() - buy_dt).total_seconds() / 86400
        except Exception:
            hold_days = 0.0

        with self.conn:
            # Mark position as sold
            self.conn.execute('UPDATE open_positions SET sold = 1 WHERE id = ?', (pos_id,))

            # Record completed trade
            self.conn.execute('''
                INSERT INTO trades (item_name, buy_price, sell_price, fee_amount, net_profit)
                VALUES (?, ?, ?, ?, ?)
            ''', (item_name, buy_price, sell_price, fee_amount, net_profit))

            # Upsert daily PnL
            today = datetime.now().date().isoformat()
            self.conn.execute('''
                INSERT INTO daily_pnl (date, total_profit, trades_count)
                VALUES (?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    total_profit = total_profit + ?,
                    trades_count = trades_count + 1
            ''', (today, net_profit, net_profit))

        logger.info(
            f"[TRADE-HISTORY] SELL {item_name}: bought ${buy_price:.2f} -> sold ${sell_price:.2f} "
            f"in {hold_days:.1f}d (profit ${net_profit:.2f})"
        )
        return {
            "buy_price": buy_price,
            "sell_price": sell_price,
            "fee_amount": fee_amount,
            "net_profit": net_profit,
            "hold_days": hold_days,
        }

    def get_recent_trades(self, item_name: str, days: int = 30) -> list[dict]:
        """Get recent trades for a title (for reporting, not blocking)."""
        cutoff = datetime.now().date().isoformat()
        rows = self.conn.execute('''
            SELECT item_name, buy_price, sell_price, net_profit, trade_date
            FROM trades
            WHERE item_name = ? AND trade_date >= datetime(?, '-' || ? || ' days')
            ORDER BY trade_date DESC
        ''', (item_name, cutoff, days)).fetchall()
        return [dict(r) for r in rows]

    def get_open_positions(self, item_name: str = None) -> list[dict]:
        """Get all open (unsold) positions, optionally filtered by title."""
        if item_name:
            rows = self.conn.execute('''
                SELECT id, item_name, buy_price, buy_date FROM open_positions
                WHERE item_name = ? AND sold = 0 ORDER BY buy_date DESC
            ''', (item_name,)).fetchall()
        else:
            rows = self.conn.execute('''
                SELECT id, item_name, buy_price, buy_date FROM open_positions
                WHERE sold = 0 ORDER BY buy_date DESC
            ''').fetchall()
        return [dict(r) for r in rows]

    def close(self):
        """v12.8: Clean shutdown with WAL checkpoint."""
        if self.conn:
            with contextlib.suppress(Exception):
                self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            self.conn.close()

# Global DB instance for easy access
db = ProfitTrackerDB()

# v15.5: Register shutdown hook for clean WAL checkpoint
import atexit as _atexit

_atexit.register(db.close)
