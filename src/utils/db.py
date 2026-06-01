import aiosqlite
import logging

logger = logging.getLogger("DB")


class ProfitTracker:
    def __init__(self, db_path="profit.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    buy_price INTEGER,
                    sell_price_est INTEGER,
                    expected_profit INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("Profit tracking database initialized.")

    async def record_target(
        self, item_name: str, buy_price: int, sell_price_est: int, expected_profit: int
    ):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO trades (item_name, buy_price, sell_price_est, expected_profit) VALUES (?, ?, ?, ?)",
                    (item_name, buy_price, sell_price_est, expected_profit),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to record trade to DB: {e}")


profit_db = ProfitTracker()
