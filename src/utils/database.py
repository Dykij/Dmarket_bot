"""Database utilities for DMarket Bot.

This module provides database connection management, model definitions,
and common database operations.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import all models to ensure they're registered with Base.metadata
from src.models import (
    User,
)
from src.models.base import Base
from src.utils.memory_cache import _user_cache, cached, get_all_cache_stats

logger = logging.getLogger(__name__)


class DatabaseManager:  # noqa: PLR0904
    """Database connection and operations manager."""

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ) -> None:
        """Initialize database manager with optimized connection pooling.

        Args:
            database_url: Database connection URL
            echo: Whether to echo SQL queries
            pool_size: Connection pool size (default: 20 for production)
            max_overflow: Maximum number of connections to overflow
            pool_pre_ping: Test connections before using (detect stale connections)
            pool_recycle: Recycle connections after N seconds (prevent timeout)

        """
        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping
        self.pool_recycle = pool_recycle
        self._async_engine: AsyncEngine | None = None
        self._async_session_maker: async_sessionmaker[AsyncSession] | None = None

    @property
    def async_engine(self) -> AsyncEngine:
        """Get asynchronous SQLAlchemy engine."""
        if self._async_engine is None:
            # Convert sync URL to async URL if needed
            async_url = self.database_url
            if async_url.startswith("postgresql://"):
                async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            elif async_url.startswith("sqlite:///"):
                async_url = async_url.replace("sqlite:///", "sqlite+aiosqlite:///")

            kwargs: dict[str, Any] = {
                "echo": self.echo,
                "pool_pre_ping": self.pool_pre_ping,
                "pool_recycle": self.pool_recycle,
            }

            # Check for in-memory SQLite
            is_memory = ":memory:" in self.database_url or "mode=memory" in self.database_url

            if not is_memory:
                kwargs["pool_size"] = self.pool_size
                kwargs["max_overflow"] = self.max_overflow
            else:
                from sqlalchemy.pool import StaticPool

                kwargs["poolclass"] = StaticPool

            # Enable Write-Ahead Logging (WAL) mode for better concurrency
            if "sqlite" in async_url and not is_memory:
                # aiosqlite specific connection arguments
                kwargs["connect_args"] = {
                    "timeout": 30,
                    "check_same_thread": False,
                    # Enable autocommit mode for better performance
                    "isolation_level": None,
                }

            self._async_engine = create_async_engine(
                async_url,
                **kwargs,
            )
        return self._async_engine

    @property
    def async_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Get session maker for asynchronous operations."""
        if self._async_session_maker is None:
            self._async_session_maker = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_maker

    def get_async_session(self) -> AsyncSession:
        """Get asynchronous database session."""
        return self.async_session_maker()

    async def get_db_status(self) -> dict[str, Any]:
        """Get database connection pool status."""
        status: dict[str, Any] = {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "async_engine": "Not initialized",
        }

        if self._async_engine:
            try:
                # Async engine pool status might be accessed differently
                # depending on the driver. But usually it wraps a sync pool
                pool = self._async_engine.sync_engine.pool
                status["async_engine"] = {
                    "size": pool.size(),  # type: ignore[attr-defined]
                    "checkedin": pool.checkedin(),  # type: ignore[attr-defined]
                    "checkedout": pool.checkedout(),  # type: ignore[attr-defined]
                    "overflow": pool.overflow(),  # type: ignore[attr-defined]
                }
            except AttributeError:
                # Some async engines don't expose sync_engine
                status["async_engine"] = "Initialized (pool stats unavailable)"

        return status

    async def init_database(self) -> None:
        """Initialize database tables and indexes."""
        try:
            async with self.async_engine.begin() as conn:
                # Create tables
                await conn.run_sync(Base.metadata.create_all)

                # Create indexes for better performance
                await self._create_indexes(conn)

                # Enable WAL mode and optimizations for SQLite
                if "sqlite" in self.database_url:
                    await self._optimize_sqlite(conn)

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize database: {e}")
            raise

    async def _optimize_sqlite(self, conn: Any) -> None:
        """Optimize SQLite database settings for performance.

        Enables Write-Ahead Logging (WAL) mode and other optimizations
        for better concurrency and performance.

        Args:
            conn: Database connection
        """
        try:
            # WAL mode for better concurrency
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            # Faster synchronization
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            # Larger cache for better performance
            await conn.execute(text("PRAGMA cache_size=10000"))
            # Store temp tables in memory
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            # Enable memory-mapped I/O (mmap) for faster reads
            await conn.execute(text("PRAGMA mmap_size=268435456"))  # 256MB
            # Optimize page size (4KB is optimal for most cases)
            await conn.execute(text("PRAGMA page_size=4096"))
            # Enable automatic vacuuming
            await conn.execute(text("PRAGMA auto_vacuum=INCREMENTAL"))

            logger.debug("SQLite optimizations applied")
        except Exception as e:
            logger.warning(f"Failed to apply SQLite optimizations: {e}")

    async def _create_indexes(self, conn: Any) -> None:
        """Create database indexes for performance optimization."""
        indexes = [
            # Users table indexes
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity DESC)",
            # Command log indexes (table: command_log)
            "CREATE INDEX IF NOT EXISTS idx_cmdlog_user_id ON command_log(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_cmdlog_created_at ON command_log(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_cmdlog_command ON command_log(command)",
            "CREATE INDEX IF NOT EXISTS idx_cmdlog_success ON command_log(success)",
            # Market data indexes (table: market_data)
            "CREATE INDEX IF NOT EXISTS idx_market_game ON market_data(game)",
            "CREATE INDEX IF NOT EXISTS idx_market_created_at ON market_data(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_market_item_id ON market_data(item_id)",
            # Trade history indexes (table: trade_history)
            "CREATE INDEX IF NOT EXISTS idx_trade_history_created_at ON trade_history(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status)",
            "CREATE INDEX IF NOT EXISTS idx_trade_history_user_id ON trade_history(user_id)",
            # Pending trades indexes (table: pending_trades) - NEW for persistence
            "CREATE INDEX IF NOT EXISTS idx_pending_trades_asset_id ON pending_trades(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_pending_trades_status ON pending_trades(status)",
            "CREATE INDEX IF NOT EXISTS idx_pending_trades_game ON pending_trades(game)",
            "CREATE INDEX IF NOT EXISTS idx_pending_trades_created_at ON pending_trades(created_at DESC)",
            # Composite indexes for common queries
            "CREATE INDEX IF NOT EXISTS idx_cmdlog_user_cmd ON command_log(user_id, command)",
            "CREATE INDEX IF NOT EXISTS idx_market_game_date ON market_data(game, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_pending_status_game ON pending_trades(status, game)",
        ]

        for index_sql in indexes:
            try:
                await conn.execute(text(index_sql))
            except Exception as e:
                # Index might already exist or table might not exist yet
                logger.debug(f"Index creation skipped: {index_sql} - {e}")

    async def close(self) -> None:
        """Close database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Database connections closed")

    # User operations
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str = "en",
    ) -> User:
        """Get existing user or create new one."""
        async with self.get_async_session() as session:
            # Try to find existing user
            result = await session.execute(
                text("SELECT * FROM users WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id},
            )
            user_row = result.fetchone()

            if user_row:
                # Update last activity
                await session.execute(
                    text(
                        """
                        UPDATE users
                        SET last_activity = :now, username = :username,
                            first_name = :first_name, last_name = :last_name
                        WHERE telegram_id = :telegram_id
                    """,
                    ),
                    {
                        "now": datetime.now(UTC),
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "telegram_id": telegram_id,
                    },
                )
                await session.commit()

                # Инвалидация кэша после обновления
                await self.invalidate_user_cache(telegram_id)

                # Return updated user with new data
                return User(
                    id=(UUID(user_row.id) if isinstance(user_row.id, str) else user_row.id),
                    telegram_id=user_row.telegram_id,
                    username=username or user_row.username,
                    first_name=first_name or user_row.first_name,
                    last_name=last_name or user_row.last_name,
                    language_code=user_row.language_code,
                    is_active=user_row.is_active,
                    is_admin=user_row.is_admin,
                    created_at=user_row.created_at,
                    updated_at=user_row.updated_at,
                    last_activity=user_row.last_activity,
                )
            # Create new user
            user_id = uuid4()
            now = datetime.now(UTC)

            await session.execute(
                text(
                    """
                        INSERT INTO users (
                            id, telegram_id, username, first_name,
                            last_name, language_code, is_active,
                            is_admin, created_at, updated_at,
                            last_activity
                        ) VALUES (
                            :id, :telegram_id, :username, :first_name,
                            :last_name, :language_code, :is_active,
                            :is_admin, :created_at, :updated_at,
                            :last_activity
                        )
                    """,
                ),
                {
                    "id": str(user_id),
                    "telegram_id": telegram_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "language_code": language_code,
                    "is_active": True,
                    "is_admin": False,
                    "created_at": now,
                    "updated_at": now,
                    "last_activity": now,
                },
            )
            await session.commit()

            return User(
                id=user_id,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_active=True,
                is_admin=False,
                created_at=now,
                updated_at=now,
                last_activity=now,
            )

    async def log_command(
        self,
        user_id: UUID,
        command: str,
        parameters: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
        execution_time_ms: int | None = None,
    ) -> None:
        """Log command execution."""
        async with self.get_async_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO command_log (
                        id, user_id, command, parameters, success,
                        error_message, execution_time_ms, created_at
                    ) VALUES (
                        :id, :user_id, :command, :parameters, :success,
                        :error_message, :execution_time_ms, :created_at
                    )
                """,
                ),
                {
                    "id": str(uuid4()),
                    "user_id": str(user_id),
                    "command": command,
                    "parameters": json.dumps(parameters) if parameters else None,
                    "success": success,
                    "error_message": error_message,
                    "execution_time_ms": execution_time_ms,
                    "created_at": datetime.now(UTC),
                },
            )
            await session.commit()

    async def save_market_data(
        self,
        item_id: str,
        game: str,
        item_name: str,
        price_usd: float,
        price_change_24h: float | None = None,
        volume_24h: int | None = None,
        market_cap: float | None = None,
        data_source: str = "dmarket",
    ) -> None:
        """Save market data."""
        async with self.get_async_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO market_data (
                        id, item_id, game, item_name, price_usd,
                        price_change_24h, volume_24h, market_cap,
                        data_source, created_at
                    ) VALUES (
                        :id, :item_id, :game, :item_name, :price_usd,
                        :price_change_24h, :volume_24h, :market_cap,
                        :data_source, :created_at
                    )
                """,
                ),
                {
                    "id": str(uuid4()),
                    "item_id": item_id,
                    "game": game,
                    "item_name": item_name,
                    "price_usd": price_usd,
                    "price_change_24h": price_change_24h,
                    "volume_24h": volume_24h,
                    "market_cap": market_cap,
                    "data_source": data_source,
                    "created_at": datetime.now(UTC),
                },
            )
            await session.commit()

    async def get_price_history(
        self,
        item_name: str,
        game: str,
        start_date: datetime,
    ) -> list[dict[str, Any]]:
        """Get price history for an item.

        Args:
            item_name: Name of the item
            game: Game identifier (csgo, dota2, etc.)
            start_date: Start date for history

        Returns:
            list: List of price records with timestamp and price_usd
        """
        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT price_usd, created_at as timestamp
                    FROM market_data
                    WHERE item_name = :item_name
                      AND game = :game
                      AND created_at >= :start_date
                    ORDER BY created_at DESC
                """
                ),
                {
                    "item_name": item_name,
                    "game": game,
                    "start_date": start_date,
                },
            )

            rows = result.fetchall()
            return [
                {
                    "price_usd": row[0],
                    "timestamp": row[1],
                }
                for row in rows
            ]

    async def get_trade_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get trade statistics for a date range.

        Args:
            start_date: Start of the period
            end_date: End of the period

        Returns:
            Dictionary with trade statistics

        """
        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)
                            as successful_trades,
                        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END)
                            as cancelled_trades,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
                            as failed_trades,
                        COALESCE(SUM(profit_usd), 0.0) as total_profit_usd,
                        COALESCE(AVG(profit_percent), 0.0)
                            as avg_profit_percent
                    FROM trades
                    WHERE created_at >= :start_date
                      AND created_at < :end_date
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )

            row = result.fetchone()
            if row:
                return {
                    "total_trades": row[0] or 0,
                    "successful_trades": row[1] or 0,
                    "cancelled_trades": row[2] or 0,
                    "failed_trades": row[3] or 0,
                    "total_profit_usd": float(row[4] or 0.0),
                    "avg_profit_percent": float(row[5] or 0.0),
                }
            return {}

    async def get_error_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get error statistics for a date range.

        Args:
            start_date: Start of the period
            end_date: End of the period

        Returns:
            Dictionary with error statistics

        """
        async with self.get_async_session() as session:
            # API errors breakdown
            result = await session.execute(
                text(
                    """
                    SELECT error_message, COUNT(*) as count
                    FROM command_log
                    WHERE success = false
                      AND created_at >= :start_date
                      AND created_at < :end_date
                      AND error_message LIKE '%API%'
                    GROUP BY error_message
                    ORDER BY count DESC
                    LIMIT 10
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )

            api_errors = {}
            for row in result.fetchall():
                error_type = self._categorize_error(row[0])
                api_errors[error_type] = row[1]

            # Critical errors count
            result_critical = await session.execute(
                text(
                    """
                    SELECT COUNT(*) as critical_count
                    FROM command_log
                    WHERE success = false
                      AND created_at >= :start_date
                      AND created_at < :end_date
                      AND error_message LIKE '%CRITICAL%'
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )

            critical_row = result_critical.fetchone()
            critical_errors = critical_row[0] if critical_row else 0

            return {
                "api_errors": api_errors,
                "critical_errors": critical_errors,
            }

    async def get_scan_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get scan statistics for a date range.

        Args:
            start_date: Start of the period
            end_date: End of the period

        Returns:
            Dictionary with scan statistics

        """
        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as scans_performed,
                        COALESCE(
                            SUM(
                                CAST(
                                    json_extract(
                                        parameters, '$.opportunities_found'
                                    ) AS INTEGER
                                )
                            ), 0
                        ) as opportunities_found
                    FROM command_log
                    WHERE command LIKE '%scan%'
                      AND success = true
                      AND created_at >= :start_date
                      AND created_at < :end_date
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )

            row = result.fetchone()
            if row:
                return {
                    "scans_performed": row[0] or 0,
                    "opportunities_found": row[1] or 0,
                }
            return {}

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into a type.

        Args:
            error_message: Full error message

        Returns:
            Error category/type

        """
        if "rate_limit" in error_message.lower():
            return "rate_limit"
        if "timeout" in error_message.lower():
            return "timeout"
        if "connection" in error_message.lower():
            return "connection"
        if "authentication" in error_message.lower():
            return "authentication"
        return "other"

    # Кэшируемые методы для оптимизации частых запросов

    @cached(cache=_user_cache, ttl=600, key_prefix="user_by_telegram")
    async def get_user_by_telegram_id_cached(self, telegram_id: int) -> User | None:
        """
        Получить пользователя по telegram_id с кэшированием.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            User object или None
        """
        async with self.get_async_session() as session:
            result = await session.execute(
                text("SELECT * FROM users WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id},
            )
            user_row = result.fetchone()

            if not user_row:
                return None

            return User(
                id=(UUID(user_row.id) if isinstance(user_row.id, str) else user_row.id),
                telegram_id=user_row.telegram_id,
                username=user_row.username,
                first_name=user_row.first_name,
                last_name=user_row.last_name,
                language_code=user_row.language_code,
                is_active=user_row.is_active,
                is_admin=user_row.is_admin,
                created_at=user_row.created_at,
                updated_at=user_row.updated_at,
                last_activity=user_row.last_activity,
            )

    @cached(cache=None, ttl=300, key_prefix="recent_scans")
    async def get_recent_scans_cached(self, user_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        """
        Получить последние сканирования пользователя с кэшированием.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей

        Returns:
            Список сканирований
        """
        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        command,
                        parameters,
                        created_at,
                        success,
                        execution_time_ms
                    FROM command_log
                    WHERE user_id = :user_id
                      AND command LIKE '%scan%'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """
                ),
                {"user_id": str(user_id), "limit": limit},
            )

            scans = []
            for row in result.fetchall():
                params = json.loads(row[1]) if row[1] else {}
                scans.append({
                    "command": row[0],
                    "parameters": params,
                    "created_at": row[2],
                    "success": row[3],
                    "execution_time_ms": row[4],
                })

            return scans

    async def get_cache_stats(self) -> dict[str, Any]:
        """
        Получить агрегированную статистику кэширования базы данных.

        Returns:
            Словарь со статистикой всех кэшей
        """
        return await get_all_cache_stats()

    async def invalidate_user_cache(self, telegram_id: int) -> None:
        """
        Инвалидировать кэш пользователя по telegram_id.

        Args:
            telegram_id: Telegram ID пользователя
        """
        cache_key = f"user_by_telegram:{telegram_id}"
        await _user_cache.delete(cache_key)
        logger.debug(f"Invalidated cache for user {telegram_id}")

    # Batch operations for performance

    async def bulk_save_market_data(self, items: list[dict[str, Any]]) -> None:
        """
        Сохранить множество записей market_data одной транзакцией.

        Args:
            items: Список словарей с данными для сохранения
        """
        if not items:
            return

        async with self.get_async_session() as session:
            values = []
            for item in items:
                values.append({
                    "id": str(uuid4()),
                    "item_id": item.get("item_id"),
                    "game": item.get("game"),
                    "item_name": item.get("item_name"),
                    "price_usd": item.get("price_usd"),
                    "price_change_24h": item.get("price_change_24h"),
                    "volume_24h": item.get("volume_24h"),
                    "market_cap": item.get("market_cap"),
                    "data_source": item.get("data_source", "dmarket"),
                    "created_at": datetime.now(UTC),
                })

            # Batch insert
            await session.execute(
                text(
                    """
                    INSERT INTO market_data (
                        id, item_id, game, item_name, price_usd,
                        price_change_24h, volume_24h, market_cap,
                        data_source, created_at
                    ) VALUES (
                        :id, :item_id, :game, :item_name, :price_usd,
                        :price_change_24h, :volume_24h, :market_cap,
                        :data_source, :created_at
                    )
                """
                ),
                values,
            )
            await session.commit()
            logger.debug(f"Bulk saved {len(items)} market data records")

    async def cleanup_old_market_data(self, days: int = 30) -> int:
        """
        Удалить старые записи market_data для экономии места.

        Args:
            days: Количество дней для хранения данных

        Returns:
            Количество удаленных записей
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM market_data
                    WHERE created_at < :cutoff_date
                """
                ),
                {"cutoff_date": cutoff_date},
            )
            await session.commit()
            # Result.rowcount exists but MyPy doesn't see it
            deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]
            logger.info(f"Cleaned up {deleted_count} old market data records")
            return deleted_count

    async def cleanup_expired_cache(self) -> int:
        """
        Удалить просроченные записи из market_data_cache.

        Returns:
            Количество удаленных записей
        """
        now = datetime.now(UTC)

        async with self.get_async_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM market_data_cache
                    WHERE expires_at < :now
                """
                ),
                {"now": now},
            )
            await session.commit()
            # Result.rowcount exists but MyPy doesn't see it
            deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache records")
            return deleted_count

    async def vacuum_database(self) -> None:
        """
        Выполнить VACUUM для SQLite базы данных.

        Освобождает неиспользуемое пространство и оптимизирует БД.
        Работает только для SQLite.
        """
        if "sqlite" not in self.database_url:
            logger.debug("VACUUM skipped - not a SQLite database")
            return

        try:
            async with self.async_engine.begin() as conn:
                # VACUUM не может быть выполнен в транзакции
                await conn.execute(text("PRAGMA incremental_vacuum"))
                logger.info("Database vacuumed successfully")
        except Exception as e:
            logger.warning(f"Failed to vacuum database: {e}")


# Global database manager instance (lazy initialization)
_db_manager: DatabaseManager | None = None


def get_database_manager() -> DatabaseManager:
    """Get or create the global DatabaseManager instance.

    Returns:
        DatabaseManager instance configured from environment.
    """
    global _db_manager
    if _db_manager is None:
        import os

        database_url = os.getenv("DATABASE_URL", "sqlite:///data/bot_database.db")
        _db_manager = DatabaseManager(database_url)
    return _db_manager


async def get_db_session() -> AsyncSession:
    """Get a database session (async context manager compatible).

    This is a convenience function for FastAPI Depends() and other uses.

    Returns:
        AsyncSession that should be used as async context manager.

    Example:
        async with get_db_session() as session:
            result = await session.execute(...)
    """
    db = get_database_manager()
    return db.get_async_session()


async def get_async_session() -> AsyncSession:
    """Alias for get_db_session for compatibility.

    Returns:
        AsyncSession that should be used as async context manager.
    """
    return await get_db_session()
