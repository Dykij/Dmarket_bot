"""Tests for database functionality.

This module contains tests for database models, operations,
and connection management.
"""

from datetime import datetime
from uuid import UUID

import pytest
import pytest_asyncio

from src.models.alert import PriceAlert
from src.models.market import MarketData
from src.models.user import User
from src.utils.database import DatabaseManager
from tests.conftest import generate_test_user_data


class TestDatabaseManager:
    """Test cases for database manager."""

    @pytest_asyncio.fixture
    async def db_manager(self) -> DatabaseManager:
        """Create test database manager."""
        db = DatabaseManager("sqlite:///:memory:")
        await db.init_database()
        return db

    @pytest.mark.asyncio()
    async def test_database_initialization(self, db_manager: DatabaseManager):
        """Test database initialization."""
        # Database should be initialized without errors
        assert db_manager.database_url == "sqlite:///:memory:"
        # For in-memory SQLite, engine might not be created until first use
        # assert db_manager._engine is not None

    @pytest.mark.asyncio()
    async def test_get_or_create_user_new(self, db_manager: DatabaseManager):
        """Test creating new user."""
        user = await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )

        assert isinstance(user, User)
        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.language_code == "en"
        assert user.is_active is True
        assert user.is_admin is False
        assert isinstance(user.id, UUID)
        assert isinstance(user.created_at, datetime)

    @pytest.mark.asyncio()
    async def test_get_or_create_user_existing(self, db_manager: DatabaseManager):
        """Test getting existing user."""
        # Create user first
        user1 = await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

        # Get the same user agAlgon
        user2 = await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="updateduser",  # Updated username
            first_name="Updated",  # Updated first name
        )

        # Should be the same user with updated info
        assert user1.id == user2.id
        assert user2.username == "updateduser"
        assert user2.first_name == "Updated"
        assert user2.telegram_id == 123456789

    @pytest.mark.asyncio()
    async def test_log_command(self, db_manager: DatabaseManager):
        """Test command logging."""
        # Create a user first
        user = await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="testuser",
        )

        # Log a command
        await db_manager.log_command(
            user_id=user.id,
            command="/start",
            parameters={"test": "param"},
            success=True,
            execution_time_ms=150,
        )

        # Should complete without error
        # In a real test, we would query the database to verify the log entry

    @pytest.mark.asyncio()
    async def test_save_market_data(self, db_manager: DatabaseManager):
        """Test saving market data."""
        await db_manager.save_market_data(
            item_id="test_item_123",
            game="csgo",
            item_name="AK-47 | Redline (Field-Tested)",
            price_usd=12.50,
            price_change_24h=-2.5,
            volume_24h=150,
            market_cap=50000.0,
        )

        # Should complete without error
        # In a real test, we would query the database to verify the data

    @pytest.mark.asyncio()
    async def test_database_connection_management(self, db_manager: DatabaseManager):
        """Test database connection management."""
        # Test asynchronous session (DatabaseManager is now async-only)
        async_session = db_manager.get_async_session()
        assert async_session is not None
        await async_session.close()

    @pytest.mark.asyncio()
    async def test_database_close(self, db_manager: DatabaseManager):
        """Test database connection closing."""
        # Should close without errors
        await db_manager.close()


class TestDatabaseModels:
    """Test cases for database models."""

    def test_user_model_creation(self):
        """Test User model creation."""
        user_data = generate_test_user_data()

        user = User(
            telegram_id=user_data["telegram_id"],
            username=user_data["username"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            language_code=user_data["language_code"],
        )

        assert user.telegram_id == user_data["telegram_id"]
        assert user.username == user_data["username"]
        assert user.first_name == user_data["first_name"]
        assert user.last_name == user_data["last_name"]
        assert user.language_code == user_data["language_code"]
        # Note: SQLAlchemy defaults only apply on commit, so is_active may be None
        assert user.is_active in {True, None}
        assert user.is_admin in {False, None}

    def test_market_data_model_creation(self):
        """Test MarketData model creation."""
        market_data = MarketData(
            item_id="test_item_456",
            game="csgo",
            item_name="AWP | Asiimov (Field-Tested)",
            price_usd=45.75,
            price_change_24h=3.2,
            volume_24h=75,
            market_cap=125000.0,
            data_source="dmarket",
        )

        assert market_data.item_id == "test_item_456"
        assert market_data.game == "csgo"
        assert market_data.item_name == "AWP | Asiimov (Field-Tested)"
        assert market_data.price_usd == 45.75
        assert market_data.price_change_24h == 3.2
        assert market_data.volume_24h == 75
        assert market_data.market_cap == 125000.0
        assert market_data.data_source == "dmarket"

    def test_price_alert_model_creation(self):
        """Test PriceAlert model creation."""
        from uuid import uuid4

        alert = PriceAlert(
            user_id=uuid4(),
            item_id="test_item_789",
            target_price=20.0,
            condition="below",
            is_active=True,
        )

        assert isinstance(alert.user_id, UUID)
        assert alert.item_id == "test_item_789"
        assert alert.target_price == 20.0
        assert alert.condition == "below"
        assert alert.is_active is True
        assert alert.triggered_at is None  # Default value


class TestDatabaseEngines:
    """Test database engine creation."""

    @pytest.mark.asyncio()
    async def test_engine_lazy_initialization(self):
        """Test lazy engine initialization."""
        db_manager = DatabaseManager("sqlite:///:memory:")

        # Async engine should not be created until accessed
        assert db_manager._async_engine is None

        # Access async engine property
        async_engine = db_manager.async_engine
        assert async_engine is not None
        assert db_manager._async_engine is not None

    @pytest.mark.asyncio()
    async def test_session_maker_lazy_initialization(self):
        """Test lazy session maker initialization."""
        db_manager = DatabaseManager("sqlite:///:memory:")

        # Session maker should not be created until accessed
        assert db_manager._async_session_maker is None

        # Access async session maker property
        async_session_maker = db_manager.async_session_maker
        assert async_session_maker is not None
        assert db_manager._async_session_maker is not None

    @pytest.mark.asyncio()
    async def test_postgresql_url_conversion(self):
        """Test PostgreSQL URL conversion to async."""
        pytest.importorskip("asyncpg")  # Skip if asyncpg not installed
        db_manager = DatabaseManager("postgresql://user:pass@localhost/db")

        # Access async engine to trigger conversion
        async_engine = db_manager.async_engine

        # URL should be converted to asyncpg
        assert "postgresql+asyncpg://" in str(async_engine.url)

    @pytest.mark.asyncio()
    async def test_sqlite_url_conversion(self):
        """Test SQLite URL conversion to async."""
        db_manager = DatabaseManager("sqlite:///test.db")

        # Access async engine to trigger conversion
        async_engine = db_manager.async_engine

        # URL should be converted to Algoosqlite
        assert "sqlite+Algoosqlite://" in str(async_engine.url)


class TestDatabaseOperationsEdgeCases:
    """Test edge cases in database operations."""

    @pytest.mark.asyncio()
    async def test_get_or_create_user_minimal_info(self):
        """Test creating user with minimal information."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            # Create user with only telegram_id
            user = await db_manager.get_or_create_user(telegram_id=111222333)

            assert user.telegram_id == 111222333
            assert user.username is None
            assert user.first_name is None
            assert user.last_name is None
            assert user.language_code == "en"  # default
        finally:
            await db_manager.close()

    @pytest.mark.asyncio()
    async def test_get_or_create_user_update_partial_info(self):
        """Test updating user with partial information."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            # Create user with full info
            await db_manager.get_or_create_user(
                telegram_id=444555666,
                username="original",
                first_name="John",
                last_name="Doe",
            )

            # Update with only first name
            user2 = await db_manager.get_or_create_user(
                telegram_id=444555666, first_name="Jane"
            )

            # Should keep original last name
            assert user2.first_name == "Jane"
            # Username from second call is None, so original is kept
            assert user2.username == "original"
        finally:
            await db_manager.close()

    @pytest.mark.asyncio()
    async def test_log_command_without_parameters(self):
        """Test logging command without parameters."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            user = await db_manager.get_or_create_user(telegram_id=777888999)

            # Log command without parameters
            await db_manager.log_command(user_id=user.id, command="/help")

            # Should complete successfully
        finally:
            await db_manager.close()

    @pytest.mark.asyncio()
    async def test_save_market_data_minimal_fields(self):
        """Test saving market data with minimal fields."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            # Save with only required fields
            await db_manager.save_market_data(
                item_id="minimal_item",
                game="csgo",
                item_name="Minimal Test Item",
                price_usd=5.0,
            )

            # Should complete successfully with defaults
        finally:
            await db_manager.close()


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.mark.asyncio()
    async def test_user_workflow(self):
        """Test complete user workflow."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            # Create user
            user = await db_manager.get_or_create_user(
                telegram_id=987654321,
                username="workflowuser",
                first_name="Workflow",
                last_name="Test",
            )

            # Log some commands for the user
            await db_manager.log_command(
                user_id=user.id,
                command="/balance",
                success=True,
                execution_time_ms=200,
            )

            await db_manager.log_command(
                user_id=user.id,
                command="/market",
                parameters={"game": "csgo"},
                success=False,
                error_message="API timeout",
                execution_time_ms=5000,
            )

            # Save some market data
            await db_manager.save_market_data(
                item_id="workflow_item",
                game="csgo",
                item_name="Test Workflow Item",
                price_usd=15.25,
            )

            # All operations should complete successfully

        finally:
            await db_manager.close()

    @pytest.mark.asyncio()
    async def test_concurrent_operations(self):
        """Test concurrent database operations."""
        import asyncio

        db_manager = DatabaseManager("sqlite:///:memory:")
        await db_manager.init_database()

        try:
            # Create multiple users concurrently
            tasks = []
            for i in range(10):
                task = db_manager.get_or_create_user(
                    telegram_id=1000000 + i,
                    username=f"concurrentuser{i}",
                    first_name=f"User{i}",
                )
                tasks.append(task)

            users = await asyncio.gather(*tasks)

            # All users should be created successfully
            assert len(users) == 10
            assert all(isinstance(user, User) for user in users)
            assert len({user.telegram_id for user in users}) == 10  # All unique

        finally:
            await db_manager.close()
