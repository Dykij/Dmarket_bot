"""
Script: audit_db.py
Description: Reads the last 10 entries from the market_data.db to verify data collection.
"""

import aiosqlite
import asyncio
import logging
import os
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DB_Audit")

DB_PATH = Path("D:/Dmarket_bot/data/market_data.db")

async def audit():
    if not DB_PATH.exists():
        logger.error(f"❌ Database not found at {DB_PATH}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        logger.info(f"🔍 Connecting to {DB_PATH}...")
        
        # Get count
        async with db.execute("SELECT COUNT(*) FROM market_ticks") as cursor:
            count = await cursor.fetchone()
            logger.info(f"📊 Total Records: {count[0]}")

        # Get last 10
        logger.info("📉 Last 10 Entries:")
        async with db.execute("SELECT id, item_name, timestamp, price_cents FROM market_ticks ORDER BY id DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(f"   Row {row[0]}: {row[1]} | Price: {row[3]}c | TS: {row[2]}")

if __name__ == "__main__":
    asyncio.run(audit())