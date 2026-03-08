"""
Tests for TrAlgoningDataManager - ML dataset management.

Based on actual implementation in src/ml/training_data_manager.py:
- DatasetMetadata dataclass (version_id, game, total_samples, sources, etc.)
- TrAlgoningDataset dataclass (features, labels, item_names, metadata, feature_names)
- TrAlgoningDataManager class (create_dataset, save_version, load_version, etc.)
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ml.training_data_manager import DatasetMetadata, TrAlgoningDataManager, TrAlgoningDataset

# ============================================================================
# Test DatasetMetadata
# ============================================================================


class TestDatasetMetadata:
    """Tests for DatasetMetadata dataclass."""

    def test_create_metadata_minimal(self) -> None:
        """Test creating metadata with minimal fields."""
        metadata = DatasetMetadata(
            version_id="v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=100,
            price_range=(1.0, 100.0),
            features_count=5,
            checksum="test_checksum_minimal",
        )
        assert metadata.version_id == "v1"
        assert metadata.game == "csgo"
        assert metadata.total_samples == 100
        assert metadata.features_count == 5
        assert metadata.sources == ["dmarket"]
        assert metadata.price_range == (1.0, 100.0)

    def test_create_metadata_full(self) -> None:
        """Test creating metadata with all fields."""
        now = datetime.now(UTC)
        metadata = DatasetMetadata(
            version_id="v2",
            created_at=now,
            game="dota2",
            sources=["dmarket", "waxpeer", "steam"],
            total_samples=500,
            price_range=(0.5, 250.0),
            features_count=10,
            checksum="abc123",
            description="Test dataset",
            tags=["test", "csgo"],
            metrics={"accuracy": 0.95},
        )
        assert metadata.version_id == "v2"
        assert metadata.created_at == now
        assert metadata.game == "dota2"
        assert len(metadata.sources) == 3
        assert metadata.total_samples == 500
        assert metadata.price_range == (0.5, 250.0)
        assert metadata.features_count == 10
        assert metadata.checksum == "abc123"
        assert metadata.description == "Test dataset"
        assert "test" in metadata.tags
        assert metadata.metrics["accuracy"] == 0.95

    def test_metadata_to_dict(self) -> None:
        """Test converting metadata to dictionary."""
        now = datetime.now(UTC)
        metadata = DatasetMetadata(
            version_id="v1",
            created_at=now,
            game="csgo",
            sources=["dmarket"],
            total_samples=100,
            price_range=(1.0, 100.0),
            features_count=5,
            checksum="test_checksum_to_dict",
            description="Test",
        )
        data = metadata.to_dict()
        assert data["version_id"] == "v1"
        assert data["game"] == "csgo"
        assert data["total_samples"] == 100
        assert data["description"] == "Test"
        assert data["checksum"] == "test_checksum_to_dict"

    def test_metadata_from_dict(self) -> None:
        """Test creating metadata from dictionary."""
        now = datetime.now(UTC)
        data = {
            "version_id": "v1",
            "created_at": now.isoformat(),
            "game": "csgo",
            "sources": ["dmarket"],
            "total_samples": 100,
            "price_range": [1.0, 100.0],
            "features_count": 5,
            "checksum": "test_checksum_from_dict",
        }
        metadata = DatasetMetadata.from_dict(data)
        assert metadata.version_id == "v1"
        assert metadata.game == "csgo"
        assert metadata.total_samples == 100
        assert metadata.checksum == "test_checksum_from_dict"


# ============================================================================
# Test TrAlgoningDataset
# ============================================================================


class TestTrAlgoningDataset:
    """Tests for TrAlgoningDataset dataclass."""

    @pytest.fixture()
    def sample_metadata(self) -> DatasetMetadata:
        """Create sample metadata for tests."""
        return DatasetMetadata(
            version_id="test_v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=5,
            price_range=(1.0, 10.0),
            features_count=3,
            checksum="sample_checksum",
        )

    def test_create_dataset_with_numpy_arrays(self, sample_metadata: DatasetMetadata) -> None:
        """Test creating dataset with numpy arrays."""
        features = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12], [13, 14, 15]])
        labels = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        item_names = ["item1", "item2", "item3", "item4", "item5"]
        feature_names = ["f1", "f2", "f3"]

        dataset = TrAlgoningDataset(
            features=features,
            labels=labels,
            item_names=item_names,
            metadata=sample_metadata,
            feature_names=feature_names,
        )

        assert dataset.features.shape == (5, 3)
        assert dataset.labels.shape == (5,)
        assert len(dataset.item_names) == 5
        assert len(dataset.feature_names) == 3
        assert dataset.metadata.version_id == "test_v1"

    def test_dataset_shape_property(self, sample_metadata: DatasetMetadata) -> None:
        """Test shape property of dataset."""
        features = np.random.rand(10, 5)
        labels = np.random.rand(10)

        dataset = TrAlgoningDataset(
            features=features,
            labels=labels,
            item_names=["item" + str(i) for i in range(10)],
            metadata=sample_metadata,
            feature_names=["f" + str(i) for i in range(5)],
        )

        assert dataset.shape == (10, 5)

    def test_dataset_train_test_split(self, sample_metadata: DatasetMetadata) -> None:
        """Test train/test split functionality."""
        features = np.random.rand(100, 5)
        labels = np.random.rand(100)

        dataset = TrAlgoningDataset(
            features=features,
            labels=labels,
            item_names=["item" + str(i) for i in range(100)],
            metadata=sample_metadata,
            feature_names=["f" + str(i) for i in range(5)],
        )

        train, test = dataset.train_test_split(test_size=0.2)

        # Check split sizes (approximately)
        assert train.features.shape[0] == 80
        assert test.features.shape[0] == 20
        assert train.labels.shape[0] == 80
        assert test.labels.shape[0] == 20


# ============================================================================
# Test TrAlgoningDataManager
# ============================================================================


class TestTrAlgoningDataManager:
    """Tests for TrAlgoningDataManager class."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture()
    def manager(self, temp_dir: Path) -> TrAlgoningDataManager:
        """Create TrAlgoningDataManager instance for tests."""
        return TrAlgoningDataManager(
            data_dir=temp_dir,
            max_versions=5,
            enable_cache=True,
        )

    @pytest.fixture()
    def sample_dataset(self) -> TrAlgoningDataset:
        """Create sample dataset for tests."""
        metadata = DatasetMetadata(
            version_id="test_v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=10,
            price_range=(1.0, 100.0),
            features_count=5,
            checksum="dataset_checksum",
        )
        return TrAlgoningDataset(
            features=np.random.rand(10, 5),
            labels=np.random.rand(10),
            item_names=["item" + str(i) for i in range(10)],
            metadata=metadata,
            feature_names=["f" + str(i) for i in range(5)],
        )

    def test_manager_initialization(self, temp_dir: Path) -> None:
        """Test manager initialization."""
        manager = TrAlgoningDataManager(
            data_dir=temp_dir,
            max_versions=10,
            enable_cache=True,
        )
        assert manager is not None

    def test_save_and_load_version(
        self, manager: TrAlgoningDataManager, sample_dataset: TrAlgoningDataset
    ) -> None:
        """Test saving and loading dataset version."""
        # Save version
        version_id = manager.save_version(sample_dataset)
        assert version_id is not None
        assert isinstance(version_id, str)

        # Load version
        loaded = manager.load_version(version_id)
        assert loaded is not None
        assert loaded.features.shape == sample_dataset.features.shape
        assert loaded.labels.shape == sample_dataset.labels.shape

    def test_list_versions(
        self, manager: TrAlgoningDataManager, sample_dataset: TrAlgoningDataset
    ) -> None:
        """Test listing dataset versions."""
        # Save multiple versions
        manager.save_version(sample_dataset)

        # Create another dataset with different game
        metadata2 = DatasetMetadata(
            version_id="test_v2",
            created_at=datetime.now(UTC),
            game="dota2",
            sources=["waxpeer"],
            total_samples=5,
            price_range=(1.0, 50.0),
            features_count=3,
            checksum="list_versions_checksum2",
        )
        dataset2 = TrAlgoningDataset(
            features=np.random.rand(5, 3),
            labels=np.random.rand(5),
            item_names=["item" + str(i) for i in range(5)],
            metadata=metadata2,
            feature_names=["f" + str(i) for i in range(3)],
        )
        manager.save_version(dataset2)

        # List all versions
        versions = manager.list_versions()
        assert len(versions) >= 2

        # Filter by game
        csgo_versions = manager.list_versions(game="csgo")
        assert all(v.game == "csgo" for v in csgo_versions)

    def test_delete_version(
        self, manager: TrAlgoningDataManager, sample_dataset: TrAlgoningDataset
    ) -> None:
        """Test deleting dataset version."""
        version_id = manager.save_version(sample_dataset)

        # Verify it exists
        loaded = manager.load_version(version_id)
        assert loaded is not None

        # Delete
        result = manager.delete_version(version_id)
        assert result is True

        # Verify deleted
        with pytest.raises(Exception):
            manager.load_version(version_id)

    def test_get_latest_version(
        self, manager: TrAlgoningDataManager, sample_dataset: TrAlgoningDataset
    ) -> None:
        """Test getting latest version for a game."""
        manager.save_version(sample_dataset)

        latest = manager.get_latest_version("csgo")
        assert latest is not None
        assert latest.game == "csgo"

    def test_get_latest_version_no_data(self, manager: TrAlgoningDataManager) -> None:
        """Test getting latest version when no data exists."""
        result = manager.get_latest_version("nonexistent_game")
        assert result is None

    def test_get_statistics(
        self, manager: TrAlgoningDataManager, sample_dataset: TrAlgoningDataset
    ) -> None:
        """Test getting manager statistics."""
        manager.save_version(sample_dataset)

        stats = manager.get_statistics()
        assert "datasets_created" in stats or "versions_count" in stats
        assert isinstance(stats, dict)

    def test_clear_cache(self, manager: TrAlgoningDataManager) -> None:
        """Test clearing cache."""
        result = manager.clear_cache()
        assert isinstance(result, int)
        assert result >= 0


class TestTrAlgoningDataManagerCreateDataset:
    """Tests for create_dataset methods."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture()
    def manager(self, temp_dir: Path) -> TrAlgoningDataManager:
        """Create TrAlgoningDataManager instance."""
        return TrAlgoningDataManager(data_dir=temp_dir)

    def test_create_dataset_from_dataframe(self, manager: TrAlgoningDataManager) -> None:
        """Test creating dataset from pandas DataFrame."""
        df = pd.DataFrame({
            "price": [10.0, 20.0, 30.0, 40.0, 50.0],
            "feature1": [1, 2, 3, 4, 5],
            "feature2": [0.1, 0.2, 0.3, 0.4, 0.5],
            "item_name": ["a", "b", "c", "d", "e"],
        })

        dataset = manager.create_dataset_from_dataframe(
            df=df,
            price_column="price",
            game="csgo",
            description="Test from DataFrame",
            feature_columns=["feature1", "feature2"],
        )

        assert dataset is not None
        assert dataset.features.shape[0] == 5
        assert dataset.labels.shape[0] == 5
        assert dataset.metadata.game == "csgo"


class TestTrAlgoningDataManagerMerge:
    """Tests for merge_datasets functionality."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture()
    def manager(self, temp_dir: Path) -> TrAlgoningDataManager:
        """Create TrAlgoningDataManager instance."""
        return TrAlgoningDataManager(data_dir=temp_dir)

    def test_merge_datasets(self, manager: TrAlgoningDataManager) -> None:
        """Test merging multiple datasets."""
        # Create first dataset
        metadata1 = DatasetMetadata(
            version_id="merge_v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=5,
            price_range=(1.0, 50.0),
            features_count=3,
            checksum="merge_checksum1",
        )
        dataset1 = TrAlgoningDataset(
            features=np.random.rand(5, 3),
            labels=np.random.rand(5),
            item_names=["item" + str(i) for i in range(5)],
            metadata=metadata1,
            feature_names=["f1", "f2", "f3"],
        )
        version_id1 = manager.save_version(dataset1)

        # Create second dataset
        metadata2 = DatasetMetadata(
            version_id="merge_v2",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["waxpeer"],
            total_samples=5,
            price_range=(10.0, 100.0),
            features_count=3,
            checksum="merge_checksum2",
        )
        dataset2 = TrAlgoningDataset(
            features=np.random.rand(5, 3),
            labels=np.random.rand(5),
            item_names=["item" + str(i + 5) for i in range(5)],
            metadata=metadata2,
            feature_names=["f1", "f2", "f3"],
        )
        version_id2 = manager.save_version(dataset2)

        # Merge
        merged = manager.merge_datasets(
            version_ids=[version_id1, version_id2],
            description="Merged dataset",
        )

        assert merged is not None
        assert merged.features.shape[0] == 10  # 5 + 5


class TestTrAlgoningDataManagerExport:
    """Tests for export functionality."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture()
    def manager(self, temp_dir: Path) -> TrAlgoningDataManager:
        """Create TrAlgoningDataManager instance."""
        return TrAlgoningDataManager(data_dir=temp_dir)

    def test_export_to_csv(self, manager: TrAlgoningDataManager, temp_dir: Path) -> None:
        """Test exporting dataset to CSV."""
        # Create and save dataset
        metadata = DatasetMetadata(
            version_id="export_v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=5,
            price_range=(1.0, 50.0),
            features_count=3,
            checksum="export_checksum",
        )
        dataset = TrAlgoningDataset(
            features=np.random.rand(5, 3),
            labels=np.random.rand(5),
            item_names=["item" + str(i) for i in range(5)],
            metadata=metadata,
            feature_names=["f1", "f2", "f3"],
        )
        version_id = manager.save_version(dataset)

        # Export
        output_path = temp_dir / "export.csv"
        result = manager.export_to_csv(version_id, output_path)

        assert result.exists()
        assert result.suffix == ".csv"

        # Verify content
        df = pd.read_csv(result)
        assert len(df) == 5


class TestTrAlgoningDataManagerIntegration:
    """Integration tests for TrAlgoningDataManager."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    def test_full_workflow(self, temp_dir: Path) -> None:
        """Test complete workflow: create, save, load, modify, export."""
        manager = TrAlgoningDataManager(data_dir=temp_dir)

        # Create from DataFrame
        df = pd.DataFrame({
            "price": [10.0, 20.0, 30.0, 40.0, 50.0],
            "volume": [100, 200, 300, 400, 500],
            "trend": [0.1, 0.2, 0.3, 0.4, 0.5],
        })

        dataset = manager.create_dataset_from_dataframe(
            df=df,
            price_column="price",
            game="csgo",
            description="Workflow test",
            feature_columns=["volume", "trend"],
        )

        # Save
        version_id = manager.save_version(dataset)
        assert version_id is not None

        # List versions
        versions = manager.list_versions()
        assert len(versions) >= 1

        # Get latest
        latest = manager.get_latest_version("csgo")
        assert latest is not None

        # Load
        loaded = manager.load_version(version_id)
        assert loaded.features.shape[0] == 5

        # Export
        csv_path = temp_dir / "workflow_export.csv"
        manager.export_to_csv(version_id, csv_path)
        assert csv_path.exists()

        # Statistics
        stats = manager.get_statistics()
        assert isinstance(stats, dict)

        # Cleanup
        manager.delete_version(version_id)


class TestTrAlgoningDataManagerEdgeCases:
    """Edge case tests for TrAlgoningDataManager."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture()
    def manager(self, temp_dir: Path) -> TrAlgoningDataManager:
        """Create TrAlgoningDataManager instance."""
        return TrAlgoningDataManager(data_dir=temp_dir)

    def test_load_nonexistent_version(self, manager: TrAlgoningDataManager) -> None:
        """Test loading non-existent version raises error."""
        with pytest.raises(Exception):
            manager.load_version("nonexistent_version_id")

    def test_delete_nonexistent_version(self, manager: TrAlgoningDataManager) -> None:
        """Test deleting non-existent version."""
        result = manager.delete_version("nonexistent_version_id")
        assert result is False

    def test_empty_list_versions(self, manager: TrAlgoningDataManager) -> None:
        """Test listing versions when none exist."""
        versions = manager.list_versions()
        assert versions == []

    def test_list_versions_with_tags(self, manager: TrAlgoningDataManager) -> None:
        """Test listing versions filtered by tags."""
        metadata = DatasetMetadata(
            version_id="tagged_v1",
            created_at=datetime.now(UTC),
            game="csgo",
            sources=["dmarket"],
            total_samples=5,
            price_range=(1.0, 50.0),
            features_count=3,
            checksum="tagged_checksum",
            tags=["test", "important"],
        )
        dataset = TrAlgoningDataset(
            features=np.random.rand(5, 3),
            labels=np.random.rand(5),
            item_names=["item" + str(i) for i in range(5)],
            metadata=metadata,
            feature_names=["f1", "f2", "f3"],
        )
        manager.save_version(dataset)

        # Filter by tags
        tagged_versions = manager.list_versions(tags=["important"])
        assert len(tagged_versions) >= 1
