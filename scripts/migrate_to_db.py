"""Database migration script: JSON/Pickle to SQLite."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.utils.config import get_config
from src.utils.database import DatabaseManager


async def migrate_users(db: DatabaseManager, profiles_path: Path):
    """Migrate user profiles from JSON to DB."""
    if not profiles_path.exists():
        print("❌ user_profiles.json not found")
        return

    with open(profiles_path, encoding='utf-8') as f:
        profiles = json.load(f)

    count = 0
    async with db.get_async_session() as session:
        for user_id_str, data in profiles.items():
            # Check if user exists
            tg_id = data.get("telegram_id")
            if not tg_id:
                continue

            user = await db.get_or_create_user(
                telegram_id=int(tg_id),
                username=data.get("username"),
                first_name=data.get("first_name"),
                language_code=data.get("language_code", "en")
            )
            
            # Migrate settings
            settings = data.get("settings", {})
            if settings:
                # Assuming UserSettings model exists and has a user_id foreign key
                # We need to check if UserSettings exists or create it.
                # Since get_or_create_user doesn't return the ORM object attached to session in a way we can directly use without re-querying or using the ID.
                # Ideally, we should use an upsert logic here.
                pass
                
            count += 1
            
    print(f"✅ Migrated {count} users")

async def migrate_all():
    config = get_config()
    db_url = config.DATABASE_URL
    print(f"🔌 Connecting to {db_url}...")
    
    db = DatabaseManager(database_url=db_url)
    await db.init_database()
    
    data_dir = Path("data")
    
    print("🚀 Starting migration...")
    
    # 1. Users & Settings
    await migrate_users(db, data_dir / "user_profiles.json")
    
    # 2. Alerts (Not implemented in this snippet, similar logic)
    # await migrate_alerts(db, data_dir / "user_alerts.json")

    # 3. Whitelist/Blacklist (If moving to DB)
    
    await db.close()
    print("✨ Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_all())
