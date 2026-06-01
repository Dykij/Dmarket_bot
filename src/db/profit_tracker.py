import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("ProfitTracker")

class ProfitTrackerDB:
    def __init__(self, db_path: str = "dmarket_trading.db"):
        self.db_path = Path(__file__).parent.parent.parent / "data" / db_path
        # Ensure data dir exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite schema."""
        with self.conn:
            # Table for completed trades
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
            # Table for daily PnL rollups
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date DATE PRIMARY KEY,
                    total_profit REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0
                )
            ''')
        logger.info(f"💾 Profit Tracker DB initialized at {self.db_path}")

    def record_trade(self, item_name: str, buy_price: float, sell_price: float, fee_rate: float):
        """Record a completed round-trip trade."""
        fee_amount = sell_price * fee_rate
        net_profit = (sell_price - fee_amount) - buy_price
        
        with self.conn:
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
            
        logger.info(f"✅ Trade Recorded [{item_name}]: PnL = ${net_profit:.2f}")

    def get_today_pnl(self):
        """Get today's total profit."""
        today = datetime.now().date().isoformat()
        cursor = self.conn.execute('SELECT total_profit, trades_count FROM daily_pnl WHERE date = ?', (today,))
        row = cursor.fetchone()
        if row:
            return {"profit": row["total_profit"], "trades": row["trades_count"]}
        return {"profit": 0.0, "trades": 0}

# Global DB instance for easy access
db = ProfitTrackerDB()
