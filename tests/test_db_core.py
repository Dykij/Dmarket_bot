import asyncio
import logging
import sys
import os

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import db

# Setup logging to console
logging.basicConfig(level=logging.INFO)

async def test_db():
    print("Testing Database...")
    await db.connect()
    
    print("Inserting tick...")
    await db.insert_tick("Mann Co. Supply Crate Key", 228)
    
    print("Verifying...")
    async with db._db.execute("SELECT * FROM market_ticks ORDER BY id DESC LIMIT 1") as cursor:
        row = await cursor.fetchone()
        print(f"Row: {row}")
        
    await db.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test_db())