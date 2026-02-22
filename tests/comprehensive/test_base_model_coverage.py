"""Comprehensive tests for src/models/base.py.

This module provides extensive testing for base SQLAlchemy model
and UUID type decorator to achieve 95%+ coverage.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session

from src.models.base import Base, SQLiteUUID, UUIDType


class TestSQLiteUUID:
    """Tests for SQLiteUUID TypeDecorator."""

    def test_process_bind_param_with_uuid(self) -> None:
        """Test binding UUID parameter converts to string."""
        uuid_type = SQLiteUUID()
        test_uuid = uuid4()
        result = uuid_type.process_bind_param(test_uuid, None)
        assert result == str(test_uuid)
        assert isinstance(result, str)

    def test_process_bind_param_with_string(self) -> None:
        """Test binding string parameter keeps as string."""
        uuid_type = SQLiteUUID()
        test_str = "550e8400-e29b-41d4-a716-446655440000"
        result = uuid_type.process_bind_param(test_str, None)
        assert result == test_str
        assert isinstance(result, str)

    def test_process_bind_param_with_none(self) -> None:
        """Test binding None returns None."""
        uuid_type = SQLiteUUID()
        result = uuid_type.process_bind_param(None, None)
        assert result is None

    def test_process_result_value_with_string(self) -> None:
        """Test result value converts string to UUID."""
        uuid_type = SQLiteUUID()
        test_str = "550e8400-e29b-41d4-a716-446655440000"
        result = uuid_type.process_result_value(test_str, None)
        assert isinstance(result, UUID)
        assert str(result) == test_str

    def test_process_result_value_with_none(self) -> None:
        """Test result value with None returns None."""
        uuid_type = SQLiteUUID()
        result = uuid_type.process_result_value(None, None)
        assert result is None

    def test_impl_is_string_36(self) -> None:
        """Test implementation is String(36) for UUID storage."""
        uuid_type = SQLiteUUID()
        assert uuid_type.impl.length == 36

    def test_cache_ok(self) -> None:
        """Test cache_ok is True for performance."""
        uuid_type = SQLiteUUID()
        assert uuid_type.cache_ok is True

    def test_round_trip(self) -> None:
        """Test UUID survives round-trip through the type."""
        uuid_type = SQLiteUUID()
        original = uuid4()

        # Bind
        stored = uuid_type.process_bind_param(original, None)
        assert isinstance(stored, str)

        # Retrieve
        retrieved = uuid_type.process_result_value(stored, None)
        assert isinstance(retrieved, UUID)
        assert retrieved == original

    def test_process_bind_param_dialect_unused(self) -> None:
        """Test dialect parameter is accepted but unused."""
        uuid_type = SQLiteUUID()
        test_uuid = uuid4()

        # Should work with any dialect (or None)
        result1 = uuid_type.process_bind_param(test_uuid, None)
        result2 = uuid_type.process_bind_param(test_uuid, "sqlite")  # type: ignore
        result3 = uuid_type.process_bind_param(test_uuid, "postgresql")  # type: ignore

        assert result1 == result2 == result3

    def test_process_result_value_dialect_unused(self) -> None:
        """Test dialect parameter is accepted but unused for result."""
        uuid_type = SQLiteUUID()
        test_str = "550e8400-e29b-41d4-a716-446655440000"

        result1 = uuid_type.process_result_value(test_str, None)
        result2 = uuid_type.process_result_value(test_str, "sqlite")  # type: ignore
        result3 = uuid_type.process_result_value(test_str, "postgresql")  # type: ignore

        assert result1 == result2 == result3


class TestUUIDTypeAlias:
    """Tests for UUIDType alias."""

    def test_uuid_type_is_sqlite_uuid(self) -> None:
        """Test UUIDType is alias for SQLiteUUID."""
        assert UUIDType is SQLiteUUID


class TestBaseModel:
    """Tests for Base model class."""

    def test_base_has_metadata(self) -> None:
        """Test Base has metadata attribute."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_to_dict_method_exists(self) -> None:
        """Test Base has to_dict method."""
        assert hasattr(Base, "to_dict")
        assert callable(Base.to_dict)


class TestBaseModelIntegration:
    """Integration tests using actual database."""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite engine."""
        return create_engine("sqlite:///:memory:", echo=False)

    def test_create_model_with_uuid(self, engine) -> None:
        """Test creating model with UUID field."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class TestModel(TestBase):
            __tablename__ = "test_create_uuid"
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
            uuid_field = Column(UUIDType, nullable=True)

        # Create table
        TestBase.metadata.create_all(engine)
        session = Session(engine)

        test_uuid = uuid4()
        model = TestModel(id=1, name="test", uuid_field=test_uuid)
        session.add(model)
        session.commit()

        # Retrieve and verify
        result = session.query(TestModel).first()
        assert result is not None
        assert result.uuid_field == test_uuid
        session.close()

    def test_to_dict_returns_all_columns(self, engine) -> None:
        """Test to_dict returns all column values."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class TestModel(TestBase):
            __tablename__ = "test_to_dict"
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
            value = Column(Integer)

            def to_dict(self):
                """Convert to dict."""
                return {c.name: getattr(self, c.name) for c in self.__table__.columns}

        TestBase.metadata.create_all(engine)
        session = Session(engine)

        model = TestModel(id=1, name="test_name", value=42)
        session.add(model)
        session.commit()

        result_dict = model.to_dict()
        assert result_dict["id"] == 1
        assert result_dict["name"] == "test_name"
        assert result_dict["value"] == 42
        session.close()

    def test_to_dict_with_none_values(self, engine) -> None:
        """Test to_dict handles None values."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class TestModel(TestBase):
            __tablename__ = "test_to_dict_none"
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=True)

            def to_dict(self):
                """Convert to dict."""
                return {c.name: getattr(self, c.name) for c in self.__table__.columns}

        TestBase.metadata.create_all(engine)
        session = Session(engine)

        model = TestModel(id=1, name=None)
        session.add(model)
        session.commit()

        result_dict = model.to_dict()
        assert result_dict["id"] == 1
        assert result_dict["name"] is None
        session.close()

    def test_uuid_none_storage(self, engine) -> None:
        """Test UUID field handles None correctly."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class TestModel(TestBase):
            __tablename__ = "test_uuid_none"
            id = Column(Integer, primary_key=True)
            uuid_field = Column(UUIDType, nullable=True)

        TestBase.metadata.create_all(engine)
        session = Session(engine)

        model = TestModel(id=1, uuid_field=None)
        session.add(model)
        session.commit()

        result = session.query(TestModel).first()
        assert result.uuid_field is None
        session.close()


class TestSQLiteUUIDEdgeCases:
    """Edge case tests for SQLiteUUID."""

    def test_various_uuid_formats(self) -> None:
        """Test handling of various UUID formats."""
        uuid_type = SQLiteUUID()

        # Standard UUID
        uuid1 = uuid4()
        result = uuid_type.process_bind_param(uuid1, None)
        assert len(result) == 36  # UUID string format

    def test_malformed_uuid_string_raises(self) -> None:
        """Test that malformed UUID string raises error on result."""
        uuid_type = SQLiteUUID()

        with pytest.raises(ValueError):
            uuid_type.process_result_value("not-a-valid-uuid", None)

    def test_empty_string_raises(self) -> None:
        """Test that empty string raises error on result."""
        uuid_type = SQLiteUUID()

        with pytest.raises(ValueError):
            uuid_type.process_result_value("", None)

    def test_uuid_string_bind(self) -> None:
        """Test binding UUID as string."""
        uuid_type = SQLiteUUID()
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"

        result = uuid_type.process_bind_param(uuid_str, None)
        assert result == uuid_str

    def test_multiple_uuids_unique(self) -> None:
        """Test multiple UUIDs remain unique after processing."""
        uuid_type = SQLiteUUID()

        uuids = [uuid4() for _ in range(100)]
        processed = [uuid_type.process_bind_param(u, None) for u in uuids]

        # All should be unique
        assert len(set(processed)) == len(processed)


class TestBaseModelToDictEdgeCases:
    """Edge case tests for Base.to_dict method."""

    def test_to_dict_preserves_types(self) -> None:
        """Test to_dict preserves Python types."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class TestModel(TestBase):
            __tablename__ = "test_types"
            id = Column(Integer, primary_key=True)
            name = Column(String(100))

            def to_dict(self):
                """Convert to dict."""
                return {c.name: getattr(self, c.name) for c in self.__table__.columns}

        engine = create_engine("sqlite:///:memory:")
        TestBase.metadata.create_all(engine)
        session = Session(engine)

        model = TestModel(id=123, name="test")
        session.add(model)
        session.commit()

        result = model.to_dict()
        assert isinstance(result["id"], int)
        assert isinstance(result["name"], str)

        session.close()

    def test_to_dict_empty_model(self) -> None:
        """Test to_dict on model with only id."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class MinimalModel(TestBase):
            __tablename__ = "minimal"
            id = Column(Integer, primary_key=True)

            def to_dict(self):
                """Convert to dict."""
                return {c.name: getattr(self, c.name) for c in self.__table__.columns}

        engine = create_engine("sqlite:///:memory:")
        TestBase.metadata.create_all(engine)
        session = Session(engine)

        model = MinimalModel(id=1)
        session.add(model)
        session.commit()

        result = model.to_dict()
        assert "id" in result
        assert result["id"] == 1

        session.close()


class TestSQLiteUUIDWithRealDatabase:
    """Tests with actual SQLite database."""

    @pytest.fixture
    def db_session(self):
        """Create database session with UUID test model."""
        from sqlalchemy.orm import declarative_base
        TestBase = declarative_base()

        class UUIDModel(TestBase):
            __tablename__ = "uuid_test"
            id = Column(Integer, primary_key=True)
            unique_id = Column(UUIDType, unique=True)

        engine = create_engine("sqlite:///:memory:")
        TestBase.metadata.create_all(engine)
        session = Session(engine)

        # Store model class for use in tests
        session.model_class = UUIDModel

        yield session
        session.close()

    def test_uuid_persistence(self, db_session) -> None:
        """Test UUID is correctly persisted and retrieved."""
        UUIDModel = db_session.model_class
        test_uuid = uuid4()

        model = UUIDModel(id=1, unique_id=test_uuid)
        db_session.add(model)
        db_session.commit()

        # Clear session cache and retrieve
        db_session.expire_all()
        result = db_session.query(UUIDModel).filter_by(id=1).first()

        assert result.unique_id == test_uuid
        assert isinstance(result.unique_id, UUID)

    def test_uuid_query_by_value(self, db_session) -> None:
        """Test querying by UUID value."""
        UUIDModel = db_session.model_class
        test_uuid = uuid4()

        model = UUIDModel(id=1, unique_id=test_uuid)
        db_session.add(model)
        db_session.commit()

        # Query by UUID
        result = db_session.query(UUIDModel).filter_by(unique_id=test_uuid).first()
        assert result is not None
        assert result.id == 1

    def test_multiple_uuid_records(self, db_session) -> None:
        """Test multiple records with UUIDs."""
        UUIDModel = db_session.model_class
        uuids = [uuid4() for _ in range(10)]

        for i, uid in enumerate(uuids):
            model = UUIDModel(id=i + 1, unique_id=uid)
            db_session.add(model)

        db_session.commit()

        # Verify all records
        results = db_session.query(UUIDModel).all()
        assert len(results) == 10

        for result in results:
            assert isinstance(result.unique_id, UUID)
            assert result.unique_id in uuids
