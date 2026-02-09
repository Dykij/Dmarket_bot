"""Alembic environment configuration.

This module configures Alembic for database migrations with:
- Naming conventions for constraints
- Include/exclude logic for autogenerate
- Async SQLAlchemy 2.0 support
- Batch operations for SQLite
- Type and default comparison
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import MetaData, pool

from alembic import context

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import models after adding to sys.path
# ruff: noqa: E402
from src.models.target import Base as TargetBase
from src.models.user import Base as UserBase
from src.models.market import Base as MarketBase

# Naming conventions for constraints
# This ensures consistent naming across all migrations
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from environment variable
database_url = os.getenv("DATABASE_URL", "sqlite:///data/bot_database.db")

# For SQLite, we need to replace sqlite:/// with sqlite+pysqlite:///
# For async support with alembic
if database_url.startswith("sqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+pysqlite:///")

config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
# for 'autogenerate' support
# We combine metadata from all our Base classes
target_metadata_list = []

# Add metadata from all Base classes
if hasattr(TargetBase, "metadata"):
    target_metadata_list.append(TargetBase.metadata)

if hasattr(UserBase, "metadata"):
    target_metadata_list.append(UserBase.metadata)

# Combine all metadata with naming conventions
combined_metadata = MetaData(naming_convention=NAMING_CONVENTION)
for metadata in target_metadata_list:
    for table in metadata.tables.values():
        table.to_metadata(combined_metadata)

target_metadata = combined_metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Determine whether to include an object in autogenerate.

    This function helps filter out objects that should not be included
    in migrations (e.g., temporary tables, specific schemas).

    Args:
        obj: The schema object being considered
        name: The name of the object
        type_: The type of object ('table', 'column', 'index', etc.)
        reflected: Whether the object was reflected from the database
        compare_to: The object being compared to (for updates)

    Returns:
        bool: True if the object should be included in migrations
    """
    # Exclude temporary tables
    if type_ == "table" and name.startswith("temp_"):
        return False

    # Exclude SQLite system tables
    if type_ == "table" and name.startswith("sqlite_"):
        return False

    # Exclude alembic version table from autogenerate
    if type_ == "table" and name == "alembic_version":
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")

    # Determine if we should use batch operations (for SQLite)
    render_as_batch = url and url.startswith(("sqlite", "sqlite+"))

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    Includes optimizations for PostgreSQL and SQLite.

    """
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Determine if we should use batch operations (for SQLite)
        render_as_batch = connection.dialect.name == "sqlite"

        # Set PostgreSQL lock timeout to prevent long-running locks
        if connection.dialect.name == "postgresql":
            connection.execute("SET lock_timeout = '10s'")
            connection.execute("SET statement_timeout = '60s'")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            render_as_batch=render_as_batch,
            # Process revision directives for advanced operations
            process_revision_directives=None,
        )

        with context.begin_transaction():
            context.run_migrations()


from typing import Any


def do_run_migrations(connection: Any) -> None:
    """Execute migrations with the provided connection.

    Args:
        connection: SQLAlchemy connection to use for migrations
    """
    # Determine if we should use batch operations (for SQLite)
    render_as_batch = connection.dialect.name == "sqlite"

    # Set PostgreSQL lock timeout to prevent long-running locks
    if connection.dialect.name == "postgresql":
        connection.execute("SET lock_timeout = '10s'")
        connection.execute("SET statement_timeout = '60s'")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode with SQLAlchemy 2.0.

    This is the recommended approach for async applications.
    Uses create_async_engine for proper async support.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    # Get async database URL
    async_url = config.get_main_option("sqlalchemy.url")

    # Create async engine
    connectable = create_async_engine(
        async_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online_async() -> None:
    """Entry point for async migrations.

    Wraps run_async_migrations in asyncio.run for alembic compatibility.
    """
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
# Use async migrations if DATABASE_URL contains asyncpg or aiosqlite
elif "+asyncpg" in database_url or "+aiosqlite" in database_url:
    run_migrations_online_async()
else:
    run_migrations_online()

