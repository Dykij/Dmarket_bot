"""
Async Database Core (SQLite + aiosqlite).
Foundation for AI Data Lake.

Features:
- Singleton Pattern
- Write-Ahead Logging (WAL) for concurrency
- Robust Error Handling
"""

import aiosqlite
import logging
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger("AsyncDB")

DB_PATH = Path("D:/Dmarket_bot/data/market_data.db")

class AsyncDatabase:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AsyncDatabase, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = DB_PATH
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._initialized = True
        
        # Ensure dir exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        if self._db:
            return
            
        async with self._lock:
            if self._db:
                return
                
            try:
                self._db = await aiosqlite.connect(self.db_path)
                # Performance tuning for HFT
                await self._db.execute("PRAGMA journal_mode=WAL;")  # Write-Ahead Logging
                await self._db.execute("PRAGMA synchronous=NORMAL;") # Faster sync
                await self._db.execute("PRAGMA cache_size=-64000;") # 64MB cache
                await self._db.commit()
                logger.info(f"✅ Database connected: {self.db_path} (WAL Mode)")
                
                await self._init_schema()
                
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                raise

    async def _init_schema(self):
        """Create tables if not exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS market_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            price_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            source TEXT DEFAULT 'dmarket'
        );
        
        CREATE INDEX IF NOT EXISTS idx_item_time ON market_ticks(item_name, timestamp);
        """
        await self._db.executescript(schema)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed.")

    async def insert_tick(self, item_name: str, price_cents: int):
        """High-speed insert of a single price tick."""
        if not self._db:
            await self.connect()
            
        try:
            # We use time.time() inside SQL or pass it? Better pass it to be explicit.
            import time
            ts = int(time.time())
            
            await self._db.execute(
                "INSERT INTO market_ticks (item_name, timestamp, price_cents) VALUES (?, ?, ?)",
                (item_name, ts, price_cents)
            )
            # Note: We do NOT commit on every insert in HFT loop usually, 
            # but aiosqlite manages concurrency well in WAL mode.
            # For max speed, we should rely on periodic commit or auto-commit.
            # Let's commit for safety for now.
            await self._db.commit() 
            
        except Exception as e:
            logger.error(f"Failed to insert tick for {item_name}: {e}")

# Global instance
db = AsyncDatabase()
