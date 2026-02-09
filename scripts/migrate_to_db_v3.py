"""Database migration script: JSON/Pickle to SQLite."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Manually load environment variables for Config.load()
from dotenv import load_dotenv

load_dotenv()

from src.models import PriceAlert, TradingSettings, UserSettings
from src.utils.config import Config
from src.utils.database import DatabaseManager


async def migrate_users(db: DatabaseManager, profiles_path: Path):
    """Migrate user profiles from JSON to DB."""
    if not profiles_path.exists():
        logger.warning(f"{profiles_path} not found")
        return

    try:
        with open(profiles_path, encoding='utf-8') as f:
            profiles = json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Failed to decode {profiles_path}")
        return

    count = 0
    async with db.get_async_session() as session:
        for user_id_str, data in profiles.items():
            # In user_profiles.json, keys are telegram_ids
            try:
                tg_id = int(user_id_str)
            except ValueError:
                continue

            try:
                # 1. Create User
                # Provide default values if missing
                user = await db.get_or_create_user(
                    telegram_id=tg_id,
                    username=data.get("username", f"user_{tg_id}"),
                    first_name=data.get("first_name", ""),
                    last_name=data.get("last_name", ""),
                    language_code=data.get("language", "en") # Note: 'language' in json, 'language_code' in method
                )
                
                # 2. Migrate UserSettings
                settings = data.get("settings", {})
                if settings:
                    from sqlalchemy import select
                    stmt = select(UserSettings).where(UserSettings.user_id == user.id)
                    result = await session.execute(stmt)
                    existing_settings = result.scalar_one_or_none()
                    
                    if not existing_settings:
                        new_settings = UserSettings(
                            user_id=user.id,
                            theme=settings.get("theme", "dark"),
                            notifications_enabled=settings.get("notification_enabled", True), # Note: 'notification_enabled' in json
                            language=settings.get("language", "en")
                        )
                        session.add(new_settings)

                # 3. Migrate TradingSettings (from 'trade_settings' or 'trading_config')
                trading = data.get("trade_settings") or data.get("trading_config") or {}
                if trading:
                    stmt = select(TradingSettings).where(TradingSettings.user_id == user.id)
                    result = await session.execute(stmt)
                    existing_trading = result.scalar_one_or_none()
                    
                    if not existing_trading:
                        new_trading = TradingSettings(
                            user_id=user.id,
                            max_trade_amount=float(trading.get("max_trade") or trading.get("max_price") or 50.0),
                            min_profit_percent=float(trading.get("min_profit", 5.0)),
                            stop_loss_percent=float(trading.get("stop_loss", 10.0)),
                            auto_buy_enabled=data.get("auto_trading_enabled", False),
                            auto_sell_enabled=trading.get("auto_sell", False)
                        )
                        session.add(new_trading)
                
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate user {tg_id}: {e}")
                continue
        
        await session.commit()
            
    logger.info(f"Migrated {count} users")

async def migrate_alerts(db: DatabaseManager, alerts_path: Path):
    """Migrate alerts from JSON."""
    if not alerts_path.exists():
        return

    try:
        with open(alerts_path, encoding='utf-8') as f:
            alerts_data = json.load(f)
    except Exception:
        return

    count = 0
    async with db.get_async_session() as session:
        for user_id_str, alerts in alerts_data.items():
            try:
                tg_id = int(user_id_str)
                user = await db.get_user_by_telegram_id_cached(tg_id)
                if not user:
                    continue
                    
                for alert in alerts:
                    new_alert = PriceAlert(
                        id=uuid4(),
                        user_id=user.id,
                        item_name=alert.get("item_name"),
                        target_price=float(alert.get("price", 0.0)),
                        condition=alert.get("condition", "below"),
                        is_active=alert.get("active", True)
                    )
                    session.add(new_alert)
                    count += 1
            except ValueError:
                continue
                
        await session.commit()
    logger.info(f"Migrated {count} alerts")

async def main():
    # Load config safely
    try:
        config = Config.load()
    except ValueError as e:
        logger.warning(f"Config validation warning: {e}")
        # Proceed with default if possible or minimal config
        config = Config()
        config.database.url = os.getenv("DATABASE_URL", "sqlite:///data/dmarket_bot.db")

    print(f"Connecting to DB: {config.database.url}")
    
    db = DatabaseManager(database_url=config.database.url)
    await db.init_database()
    
    data_dir = PROJECT_ROOT / "data"
    
    print("Starting migration...")
    
    await migrate_users(db, data_dir / "user_profiles.json")
    await migrate_alerts(db, data_dir / "user_alerts.json")
    
    await db.close()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
