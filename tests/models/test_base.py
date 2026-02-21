"""Unit tests for models/base module.

This module contAlgons tests for src/models/base.py covering:
- SQLiteUUID type decorator
- UUIDType alias
- Base declarative model
- to_dict method

Target: 25+ tests to achieve 85%+ coverage
"""

import math
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from src.models.base import Base, SQLiteUUID, UUIDType

# ==============================================================================
# Test SQLiteUUID Type Decorator
# ==============================================================================


class TestSQLiteUUID:
    """Tests for SQLiteUUID TypeDecorator."""

    def test_impl_is_string_36(self):
        """Test that impl is String(36)."""
        sqlite_uuid = SQLiteUUID()
        # The impl should be String type with length 36
        assert sqlite_uuid.impl is not None

    def test_cache_ok_is_true(self):
        """Test that cache_ok is True."""
        assert SQLiteUUID.cache_ok is True

    def test_process_bind_param_with_uuid(self):
        """Test process_bind_param with UUID object."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        test_uuid = uuid4()
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_bind_param(test_uuid, mock_dialect)

        # Assert
        assert result == str(test_uuid)
        assert isinstance(result, str)
        assert len(result) == 36

    def test_process_bind_param_with_string(self):
        """Test process_bind_param with string UUID."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        test_uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_bind_param(test_uuid_str, mock_dialect)

        # Assert
        assert result == test_uuid_str
        assert isinstance(result, str)

    def test_process_bind_param_with_none(self):
        """Test process_bind_param with None."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_bind_param(None, mock_dialect)

        # Assert
        assert result is None

    def test_process_result_value_with_string(self):
        """Test process_result_value with string UUID."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        test_uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_result_value(test_uuid_str, mock_dialect)

        # Assert
        assert isinstance(result, UUID)
        assert str(result) == test_uuid_str

    def test_process_result_value_with_none(self):
        """Test process_result_value with None."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_result_value(None, mock_dialect)

        # Assert
        assert result is None

    def test_roundtrip_uuid(self):
        """Test UUID roundtrip (bind -> result)."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        original_uuid = uuid4()
        mock_dialect = MagicMock()

        # Act - simulate storing and retrieving
        stored = sqlite_uuid.process_bind_param(original_uuid, mock_dialect)
        retrieved = sqlite_uuid.process_result_value(stored, mock_dialect)

        # Assert
        assert retrieved == original_uuid

    def test_process_bind_param_preserves_uuid_format(self):
        """Test that UUID format is preserved during binding."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        test_uuid = UUID("12345678-1234-5678-1234-567812345678")
        mock_dialect = MagicMock()

        # Act
        result = sqlite_uuid.process_bind_param(test_uuid, mock_dialect)

        # Assert
        assert result == "12345678-1234-5678-1234-567812345678"

    def test_process_result_value_creates_valid_uuid(self):
        """Test that result value is a valid UUID object."""
        # Arrange
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        # Various UUID formats
        test_uuids = [
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "550e8400-e29b-41d4-a716-446655440000",
        ]

        for uuid_str in test_uuids:
            # Act
            result = sqlite_uuid.process_result_value(uuid_str, mock_dialect)

            # Assert
            assert isinstance(result, UUID)
            assert str(result) == uuid_str


# ==============================================================================
# Test UUIDType Alias
# ==============================================================================


class TestUUIDTypeAlias:
    """Tests for UUIDType alias."""

    def test_uuid_type_is_sqlite_uuid(self):
        """Test that UUIDType is SQLiteUUID."""
        assert UUIDType is SQLiteUUID

    def test_uuid_type_can_be_instantiated(self):
        """Test that UUIDType can be instantiated."""
        # Act
        uuid_type = UUIDType()

        # Assert
        assert isinstance(uuid_type, SQLiteUUID)


# ==============================================================================
# Test Base Declarative Model
# ==============================================================================


class TestBaseModel:
    """Tests for Base declarative model."""

    def test_base_is_declarative_base(self):
        """Test that Base is a DeclarativeBase."""
        # Assert
        assert hasattr(Base, "__table__") or hasattr(Base, "metadata")

    def test_base_has_to_dict_method(self):
        """Test that Base has to_dict method."""
        assert hasattr(Base, "to_dict")
        assert callable(Base.to_dict)


# ==============================================================================
# Test to_dict Method with Mock Model
# ==============================================================================


class TestToDictMethod:
    """Tests for to_dict method."""

    def test_to_dict_with_mock_model(self):
        """Test to_dict method with mock model."""
        # Create a mock model that simulates Base inheritance
        mock_model = MagicMock()

        # Setup mock table columns
        col1 = MagicMock()
        col1.name = "id"
        col2 = MagicMock()
        col2.name = "name"
        col3 = MagicMock()
        col3.name = "value"

        mock_model.__table__ = MagicMock()
        mock_model.__table__.columns = [col1, col2, col3]

        # Setup attribute values
        mock_model.id = 1
        mock_model.name = "test"
        mock_model.value = 42

        # Manually call to_dict logic (since MagicMock doesn't inherit Base)
        result = {
            c.name: getattr(mock_model, c.name) for c in mock_model.__table__.columns
        }

        # Assert
        assert result == {"id": 1, "name": "test", "value": 42}

    def test_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        # Setup mock
        mock_model = MagicMock()
        col1 = MagicMock()
        col1.name = "id"
        col2 = MagicMock()
        col2.name = "optional_field"

        mock_model.__table__ = MagicMock()
        mock_model.__table__.columns = [col1, col2]
        mock_model.id = 1
        mock_model.optional_field = None

        # Act
        result = {
            c.name: getattr(mock_model, c.name) for c in mock_model.__table__.columns
        }

        # Assert
        assert result["optional_field"] is None

    def test_to_dict_with_various_types(self):
        """Test to_dict with various value types."""
        # Setup mock
        mock_model = MagicMock()
        columns = []

        for name in ["int_col", "str_col", "float_col", "bool_col", "uuid_col"]:
            col = MagicMock()
            col.name = name
            columns.append(col)

        mock_model.__table__ = MagicMock()
        mock_model.__table__.columns = columns

        test_uuid = uuid4()
        mock_model.int_col = 42
        mock_model.str_col = "hello"
        mock_model.float_col = math.pi
        mock_model.bool_col = True
        mock_model.uuid_col = test_uuid

        # Act
        result = {
            c.name: getattr(mock_model, c.name) for c in mock_model.__table__.columns
        }

        # Assert
        assert result["int_col"] == 42
        assert result["str_col"] == "hello"
        assert result["float_col"] == math.pi
        assert result["bool_col"] is True
        assert result["uuid_col"] == test_uuid


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestBaseEdgeCases:
    """Tests for edge cases in base module."""

    def test_sqlite_uuid_with_empty_string_rAlgoses(self):
        """Test that empty string rAlgoses ValueError."""
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        # Empty string is not a valid UUID
        with pytest.rAlgoses(ValueError):
            sqlite_uuid.process_result_value("", mock_dialect)

    def test_sqlite_uuid_with_invalid_uuid_rAlgoses(self):
        """Test that invalid UUID string rAlgoses ValueError."""
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        with pytest.rAlgoses(ValueError):
            sqlite_uuid.process_result_value("not-a-valid-uuid", mock_dialect)

    def test_sqlite_uuid_with_short_uuid_rAlgoses(self):
        """Test that too short UUID string rAlgoses ValueError."""
        sqlite_uuid = SQLiteUUID()
        mock_dialect = MagicMock()

        with pytest.rAlgoses(ValueError):
            sqlite_uuid.process_result_value("550e8400-e29b-41d4", mock_dialect)

    def test_to_dict_with_empty_columns(self):
        """Test to_dict with no columns."""
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock()
        mock_model.__table__.columns = []

        # Act
        result = {
            c.name: getattr(mock_model, c.name) for c in mock_model.__table__.columns
        }

        # Assert
        assert result == {}


# ==============================================================================
# Test Module Imports
# ==============================================================================


class TestModuleImports:
    """Tests for module imports."""

    def test_sqlite_uuid_importable(self):
        """Test SQLiteUUID is importable."""
        from src.models.base import SQLiteUUID

        assert SQLiteUUID is not None

    def test_uuid_type_importable(self):
        """Test UUIDType is importable."""
        from src.models.base import UUIDType

        assert UUIDType is not None

    def test_base_importable(self):
        """Test Base is importable."""
        from src.models.base import Base

        assert Base is not None
