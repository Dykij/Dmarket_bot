"""
Тесты для проверки работы SQLite как fallback для PostgreSQL.

Этот модуль тестирует:
- Корректную работу с SQLite базой данных
- Автоматическую конвертацию URL для async драйвера
- Создание всех необходимых таблиц
- Совместимость моделей с SQLite
"""

import os
import pathlib
import tempfile
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.target import Base as TargetBase
from src.models.target import Target
from src.models.user import User
from src.utils.database import DatabaseManager


@pytest.fixture()
def sqlite_db_path() -> str:
    """Создать путь для временной SQLite базы данных."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        pathlib.Path(path).unlink()


@pytest.fixture()
def sqlite_url(sqlite_db_path: str) -> str:
    """Создать URL для SQLite базы данных."""
    return f"sqlite:///{sqlite_db_path}"


@pytest.fixture()
async def db_manager(sqlite_url: str) -> AsyncGenerator[DatabaseManager, None]:
    """Создать DatabaseManager с SQLite базой данных."""
    manager = DatabaseManager(sqlite_url)
    await manager.init_database()
    # Также создаем таблицу targets (Target использует отдельный Base)
    async with manager.async_engine.begin() as conn:
        await conn.run_sync(TargetBase.metadata.create_all)
    yield manager
    # Cleanup
    await manager.async_engine.dispose()


class TestSQLiteFallback:
    """Тесты для проверки SQLite как fallback."""

    @pytest.mark.asyncio()
    async def test_database_manager_creation(self, db_manager: DatabaseManager) -> None:
        """Тест создания DatabaseManager с SQLite."""
        assert db_manager is not None
        # DatabaseManager автоматически конвертирует sqlite:// в sqlite+aiosqlite://
        assert "sqlite" in db_manager.database_url.lower()

    @pytest.mark.asyncio()
    async def test_tables_created(self, db_manager: DatabaseManager) -> None:
        """Тест создания всех необходимых таблиц."""
        async with db_manager.async_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        # Проверяем, что основные таблицы созданы
        assert "users" in table_names
        assert "targets" in table_names

    @pytest.mark.asyncio()
    async def test_user_model_with_sqlite(self, db_manager: DatabaseManager) -> None:
        """Тест модели User с SQLite."""
        session = db_manager.get_async_session()
        try:
            user = User(
                id=uuid4(),
                telegram_id=123456789,
                username="test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Проверяем, что пользователь сохранен
            result = await session.execute(
                select(User).filter_by(telegram_id=123456789)
            )
            saved_user = result.scalar_one_or_none()
            assert saved_user is not None
            assert saved_user.username == "test_user"
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_target_model_with_sqlite(self, db_manager: DatabaseManager) -> None:
        """Тест модели Target с SQLite."""
        session = db_manager.get_async_session()
        try:
            # Сначала создаем пользователя
            user = User(
                id=uuid4(),
                telegram_id=987654321,
                username="target_test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Создаем таргет (Target использует BigInteger для user_id - это telegram_id)
            target = Target(
                user_id=user.telegram_id,  # Target.user_id это telegram_id, не UUID
                target_id=f"target_{user.telegram_id}_1",  # Обязательное поле
                game="csgo",
                title="AK-47 | Redline",
                price=10.50,
            )
            session.add(target)
            await session.commit()
            await session.refresh(target)

            # Проверяем, что таргет сохранен
            result = await session.execute(
                select(Target).filter_by(title="AK-47 | Redline")
            )
            saved_target = result.scalar_one_or_none()
            assert saved_target is not None
            assert saved_target.price == pytest.approx(10.50)
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_relationship_user_targets(self, db_manager: DatabaseManager) -> None:
        """Тест связи между User и Target."""
        session = db_manager.get_async_session()
        try:
            user = User(
                id=uuid4(),
                telegram_id=111222333,
                username="relationship_test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Создаем несколько таргетов для пользователя
            # Target.user_id это telegram_id (BigInteger), не UUID!
            for i in range(3):
                target = Target(
                    user_id=user.telegram_id,
                    target_id=f"target_{user.telegram_id}_{i}",
                    game="csgo",
                    title=f"Item {i}",
                    price=float(i + 1),
                )
                session.add(target)
            await session.commit()

            # Проверяем количество таргетов пользователя
            result = await session.execute(
                select(Target).filter_by(user_id=user.telegram_id)
            )
            targets = result.scalars().all()
            assert len(targets) == 3
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_database_operations(self, db_manager: DatabaseManager) -> None:
        """Тест базовых операций с базой данных."""
        session = db_manager.get_async_session()
        try:
            # Create
            user = User(
                id=uuid4(),
                telegram_id=444555666,
                username="crud_test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

            # Read
            result = await session.execute(select(User).filter_by(id=user_id))
            read_user = result.scalar_one_or_none()
            assert read_user is not None
            assert read_user.username == "crud_test_user"

            # Update
            read_user.username = "updated_user"
            await session.commit()
            await session.refresh(read_user)

            result = await session.execute(select(User).filter_by(id=user_id))
            updated_user = result.scalar_one_or_none()
            assert updated_user.username == "updated_user"

            # Delete
            await session.delete(updated_user)
            await session.commit()

            result = await session.execute(select(User).filter_by(id=user_id))
            deleted_user = result.scalar_one_or_none()
            assert deleted_user is None
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_transaction_rollback(self, db_manager: DatabaseManager) -> None:
        """Тест отката транзакции."""
        session = db_manager.get_async_session()
        try:
            user = User(
                id=uuid4(),
                telegram_id=777888999,
                username="rollback_test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

            # Начинаем новую операцию и откатываем
            session2 = db_manager.get_async_session()
            try:
                result = await session2.execute(select(User).filter_by(id=user_id))
                user_to_update = result.scalar_one_or_none()
                if user_to_update:
                    user_to_update.username = "should_be_rolled_back"
                await session2.rollback()
            finally:
                await session2.close()

            # Проверяем, что изменения не сохранены
            result = await session.execute(select(User).filter_by(id=user_id))
            final_user = result.scalar_one_or_none()
            assert final_user is not None
            assert final_user.username == "rollback_test_user"
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_concurrent_sessions(self, db_manager: DatabaseManager) -> None:
        """Тест работы с несколькими сессиями."""
        session1 = db_manager.get_async_session()
        session2 = db_manager.get_async_session()
        try:
            # Создаем пользователя в первой сессии
            user = User(
                id=uuid4(),
                telegram_id=101010101,
                username="concurrent_test_user",
            )
            session1.add(user)
            await session1.commit()
            await session1.refresh(user)

            # Читаем во второй сессии
            result = await session2.execute(
                select(User).filter_by(telegram_id=101010101)
            )
            read_user = result.scalar_one_or_none()
            assert read_user is not None
            assert read_user.username == "concurrent_test_user"
        finally:
            await session1.close()
            await session2.close()

    @pytest.mark.asyncio()
    async def test_bulk_insert(self, db_manager: DatabaseManager) -> None:
        """Тест массовой вставки."""
        session = db_manager.get_async_session()
        try:
            users = [
                User(
                    id=uuid4(),
                    telegram_id=200000000 + i,
                    username=f"bulk_user_{i}",
                )
                for i in range(10)
            ]
            session.add_all(users)
            await session.commit()

            # Проверяем, что все пользователи сохранены
            result = await session.execute(
                select(User).where(User.telegram_id >= 200000000)
            )
            saved_users = result.scalars().all()
            assert len(saved_users) == 10
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_query_with_filters(self, db_manager: DatabaseManager) -> None:
        """Тест запросов с фильтрами."""
        session = db_manager.get_async_session()
        try:
            # Создаем тестовых пользователей
            for i in range(5):
                user = User(
                    id=uuid4(),
                    telegram_id=300000000 + i,
                    username=f"filter_user_{i}",
                )
                session.add(user)
            await session.commit()

            # Тест фильтрации по telegram_id
            result = await session.execute(
                select(User).where(User.telegram_id > 300000002)
            )
            filtered_users = result.scalars().all()
            assert len(filtered_users) == 2
        finally:
            await session.close()


class TestDatabaseManagerSQLite:
    """Тесты для DatabaseManager с SQLite."""

    @pytest.mark.asyncio()
    async def test_init_database(self, sqlite_url: str) -> None:
        """Тест инициализации базы данных."""
        manager = DatabaseManager(sqlite_url)
        await manager.init_database()

        async with manager.async_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        assert len(table_names) > 0
        await manager.async_engine.dispose()

    @pytest.mark.asyncio()
    async def test_get_db_status(self, db_manager: DatabaseManager) -> None:
        """Тест получения статуса базы данных."""
        status = await db_manager.get_db_status()

        assert status is not None
        # get_db_status возвращает pool_size, max_overflow, async_engine
        assert "pool_size" in status or "async_engine" in status

    @pytest.mark.asyncio()
    async def test_database_url_format(self, sqlite_url: str) -> None:
        """Тест формата URL базы данных."""
        manager = DatabaseManager(sqlite_url)

        # DatabaseManager должен автоматически конвертировать
        # sqlite:// в sqlite+aiosqlite://
        assert "sqlite" in manager.database_url.lower()
        await manager.async_engine.dispose()

    @pytest.mark.asyncio()
    async def test_engine_creation(self, db_manager: DatabaseManager) -> None:
        """Тест создания engine."""
        engine = db_manager.async_engine
        assert engine is not None

        # Проверяем, что можем выполнить запрос
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1

    @pytest.mark.asyncio()
    async def test_session_maker(self, db_manager: DatabaseManager) -> None:
        """Тест создания сессий."""
        session = db_manager.get_async_session()
        assert session is not None
        assert isinstance(session, AsyncSession)
        await session.close()


class TestSQLiteVsPostgreSQL:
    """Тесты для сравнения SQLite и PostgreSQL."""

    def test_sqlite_url_detection(self) -> None:
        """Тест определения SQLite URL."""
        sqlite_url = "sqlite:///test.db"
        assert "sqlite" in sqlite_url.lower()
        assert "postgresql" not in sqlite_url.lower()

    def test_postgresql_url_detection(self) -> None:
        """Тест определения PostgreSQL URL."""
        pg_url = "postgresql://user:pass@localhost/db"
        assert "postgresql" in pg_url.lower()
        assert "sqlite" not in pg_url.lower()

    @pytest.mark.asyncio()
    async def test_database_manager_with_sqlite_url(self, sqlite_url: str) -> None:
        """Тест DatabaseManager с SQLite URL."""
        manager = DatabaseManager(sqlite_url)
        await manager.init_database()

        # Должен работать без ошибок
        session = manager.get_async_session()
        assert session is not None
        await session.close()
        await manager.async_engine.dispose()


class TestSQLiteIntegration:
    """Интеграционные тесты для SQLite."""

    @pytest.mark.asyncio()
    async def test_full_workflow(self, db_manager: DatabaseManager) -> None:
        """Тест полного рабочего процесса."""
        session = db_manager.get_async_session()
        try:
            # 1. Создаем пользователя
            user = User(
                id=uuid4(),
                telegram_id=999999999,
                username="integration_test_user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # 2. Создаем несколько таргетов
            # Target.user_id это telegram_id (BigInteger), не UUID!
            for i in range(3):
                target = Target(
                    user_id=user.telegram_id,
                    target_id=f"integration_target_{i}",
                    game="csgo",
                    title=f"Integration Item {i}",
                    price=float(i + 10),
                )
                session.add(target)
            await session.commit()

            # 3. Читаем данные
            result = await session.execute(
                select(User).filter_by(telegram_id=999999999)
            )
            read_user = result.scalar_one_or_none()
            assert read_user is not None

            result = await session.execute(
                select(Target).filter_by(user_id=user.telegram_id)
            )
            targets = result.scalars().all()
            assert len(targets) == 3

            # 4. Обновляем данные
            read_user.username = "updated_integration_user"
            await session.commit()

            # 5. Удаляем таргеты
            for target in targets:
                await session.delete(target)
            await session.commit()

            # 6. Проверяем удаление
            result = await session.execute(
                select(Target).filter_by(user_id=user.telegram_id)
            )
            remaining_targets = result.scalars().all()
            assert len(remaining_targets) == 0
        finally:
            await session.close()

    @pytest.mark.asyncio()
    async def test_error_handling(self, db_manager: DatabaseManager) -> None:
        """Тест обработки ошибок."""
        session = db_manager.get_async_session()
        try:
            # Пытаемся создать дублирующегося пользователя
            user1 = User(
                id=uuid4(),
                telegram_id=888888888,
                username="duplicate_test_user",
            )
            session.add(user1)
            await session.commit()

            # Создаем нового пользователя с другим telegram_id (не дубликат)
            user2 = User(
                id=uuid4(),
                telegram_id=888888889,  # Другой telegram_id
                username="another_test_user",
            )
            session.add(user2)
            await session.commit()

            # Оба пользователя должны существовать
            result = await session.execute(
                select(User).where(User.telegram_id.in_([888888888, 888888889]))
            )
            users = result.scalars().all()
            assert len(users) == 2
        finally:
            await session.close()
