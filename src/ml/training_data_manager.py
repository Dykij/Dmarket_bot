"""
TrAlgoning Data Manager Module.

Manages storage, versioning, and preparation of training data
for ML price prediction models.

Version: 1.0.0
Created: January 2026
"""

from __future__ import annotations

import hashlib
import json
import pickle
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import structlog

from src.ml.price_normalizer import NormalizedPrice, PriceSource

if TYPE_CHECKING:
    from src.ml.real_price_collector import CollectedPrice, GameType

logger = structlog.get_logger(__name__)


# Default paths
DEFAULT_DATA_DIR = Path("data/ml_training")
DEFAULT_VERSIONS_DIR = DEFAULT_DATA_DIR / "versions"
DEFAULT_CACHE_DIR = DEFAULT_DATA_DIR / "cache"


@dataclass
class DatasetMetadata:
    """Metadata for a training dataset version."""

    version_id: str
    created_at: datetime
    game: str
    sources: list[str]
    total_samples: int
    price_range: tuple[float, float]
    features_count: int
    checksum: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "created_at": self.created_at.isoformat(),
            "game": self.game,
            "sources": self.sources,
            "total_samples": self.total_samples,
            "price_range": list(self.price_range),
            "features_count": self.features_count,
            "checksum": self.checksum,
            "description": self.description,
            "tags": self.tags,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetMetadata:
        """Create from dictionary."""
        return cls(
            version_id=data["version_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            game=data["game"],
            sources=data["sources"],
            total_samples=data["total_samples"],
            price_range=tuple(data["price_range"]),
            features_count=data["features_count"],
            checksum=data["checksum"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
            metrics=data.get("metrics", {}),
        )


@dataclass
class TrAlgoningDataset:
    """ContAlgoner for training data."""

    features: np.ndarray
    labels: np.ndarray
    item_names: list[str]
    metadata: DatasetMetadata
    feature_names: list[str] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, int]:
        """Get shape of features array."""
        return self.features.shape

    def train_test_split(
        self,
        test_size: float = 0.2,
        random_state: int | None = 42,
    ) -> tuple[TrAlgoningDataset, TrAlgoningDataset]:
        """
        Split dataset into training and test sets.

        Args:
            test_size: Proportion for test set
            random_state: Random seed for reproducibility

        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        from sklearn.model_selection import train_test_split

        (
            X_train,
            X_test,
            y_train,
            y_test,
            names_train,
            names_test,
        ) = train_test_split(
            self.features,
            self.labels,
            self.item_names,
            test_size=test_size,
            random_state=random_state,
        )

        train_meta = DatasetMetadata(
            version_id=f"{self.metadata.version_id}_train",
            created_at=datetime.now(UTC),
            game=self.metadata.game,
            sources=self.metadata.sources,
            total_samples=len(X_train),
            price_range=self.metadata.price_range,
            features_count=self.metadata.features_count,
            checksum="",
            description=f"TrAlgoning split of {self.metadata.version_id}",
            tags=[*self.metadata.tags, "split:train"],
        )

        test_meta = DatasetMetadata(
            version_id=f"{self.metadata.version_id}_test",
            created_at=datetime.now(UTC),
            game=self.metadata.game,
            sources=self.metadata.sources,
            total_samples=len(X_test),
            price_range=self.metadata.price_range,
            features_count=self.metadata.features_count,
            checksum="",
            description=f"Test split of {self.metadata.version_id}",
            tags=[*self.metadata.tags, "split:test"],
        )

        return (
            TrAlgoningDataset(
                features=X_train,
                labels=y_train,
                item_names=names_train,
                metadata=train_meta,
                feature_names=self.feature_names,
            ),
            TrAlgoningDataset(
                features=X_test,
                labels=y_test,
                item_names=names_test,
                metadata=test_meta,
                feature_names=self.feature_names,
            ),
        )


class TrAlgoningDataManager:
    """
    Manager for training data storage, versioning, and preparation.

    Features:
    - Version control for datasets
    - Automatic feature extraction
    - Data normalization and validation
    - TrAlgon/test splitting
    - Caching for performance

    Example:
        ```python
        manager = TrAlgoningDataManager()

        # Create dataset from collected prices
        dataset = manager.create_dataset(
            prices=collected_prices,
            game=GameType.CSGO,
            description="CS:GO January 2026 prices"
        )

        # Save version
        version_id = manager.save_version(dataset)

        # Load later
        loaded = manager.load_version(version_id)

        # Get train/test split
        train_data, test_data = loaded.train_test_split(test_size=0.2)
        ```
    """

    def __init__(
        self,
        data_dir: Path | str | None = None,
        max_versions: int = 10,
        enable_cache: bool = True,
    ) -> None:
        """
        Initialize the training data manager.

        Args:
            data_dir: Base directory for data storage
            max_versions: Maximum versions to keep per game
            enable_cache: Whether to enable caching
        """
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.versions_dir = self.data_dir / "versions"
        self.cache_dir = self.data_dir / "cache"
        self.max_versions = max_versions
        self.enable_cache = enable_cache

        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load metadata index
        self._metadata_index: dict[str, DatasetMetadata] = {}
        self._load_metadata_index()

        # Statistics
        self._stats = {
            "datasets_created": 0,
            "datasets_loaded": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        logger.info(
            "training_data_manager_initialized",
            data_dir=str(self.data_dir),
            versions_count=len(self._metadata_index),
        )

    def _load_metadata_index(self) -> None:
        """Load metadata index from disk."""
        index_path = self.data_dir / "metadata_index.json"
        if index_path.exists():
            try:
                with open(index_path) as f:
                    data = json.load(f)
                    for version_id, meta_dict in data.items():
                        self._metadata_index[version_id] = DatasetMetadata.from_dict(
                            meta_dict
                        )
            except Exception as e:
                logger.warning("failed_to_load_metadata_index", error=str(e))

    def _save_metadata_index(self) -> None:
        """Save metadata index to disk."""
        index_path = self.data_dir / "metadata_index.json"
        try:
            data = {
                version_id: meta.to_dict()
                for version_id, meta in self._metadata_index.items()
            }
            with open(index_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_metadata_index", error=str(e))

    def _generate_version_id(self, game: str) -> str:
        """Generate unique version ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"{game}_{timestamp}"

    def _compute_checksum(self, features: np.ndarray, labels: np.ndarray) -> str:
        """Compute checksum for data integrity."""
        data_bytes = features.tobytes() + labels.tobytes()
        return hashlib.sha256(data_bytes).hexdigest()[:16]

    def _extract_features(
        self,
        price: NormalizedPrice,
        item_name: str,
    ) -> dict[str, float]:
        """
        Extract features from a normalized price.

        Args:
            price: Normalized price object
            item_name: Item name for text features

        Returns:
            Dictionary of features
        """
        features = {
            # Price features
            "price_usd": float(price.price_usd),
            "original_price": float(price.original_price),
            "commission_rate": float(price.commission_rate),
            "net_price": float(price.net_price),
            # Source encoding (one-hot)
            "source_dmarket": 1.0 if price.source == PriceSource.DMARKET else 0.0,
            "source_waxpeer": 1.0 if price.source == PriceSource.WAXPEER else 0.0,
            "source_steam": 1.0 if price.source == PriceSource.STEAM else 0.0,
            # Time features
            "hour_of_day": price.timestamp.hour,
            "day_of_week": price.timestamp.weekday(),
            "month": price.timestamp.month,
        }

        # Item name features
        name_lower = item_name.lower()

        # Quality indicators
        features["is_factory_new"] = 1.0 if "factory new" in name_lower else 0.0
        features["is_minimal_wear"] = 1.0 if "minimal wear" in name_lower else 0.0
        features["is_field_tested"] = 1.0 if "field-tested" in name_lower else 0.0
        features["is_well_worn"] = 1.0 if "well-worn" in name_lower else 0.0
        features["is_battle_scarred"] = 1.0 if "battle-scarred" in name_lower else 0.0

        # Special attributes
        features["is_stattrak"] = 1.0 if "stattrak" in name_lower else 0.0
        features["is_souvenir"] = 1.0 if "souvenir" in name_lower else 0.0
        features["is_star"] = 1.0 if "★" in item_name else 0.0  # Knives

        # Item type indicators
        features["is_knife"] = 1.0 if "knife" in name_lower or "★" in item_name else 0.0
        features["is_glove"] = 1.0 if "glove" in name_lower else 0.0
        features["is_ak47"] = 1.0 if "ak-47" in name_lower else 0.0
        features["is_awp"] = 1.0 if "awp" in name_lower else 0.0
        features["is_m4a4"] = 1.0 if "m4a4" in name_lower else 0.0
        features["is_m4a1"] = 1.0 if "m4a1-s" in name_lower else 0.0

        # Name length (can correlate with rarity)
        features["name_length"] = float(len(item_name))

        # Price tier
        price_usd = float(price.price_usd)
        features["tier_budget"] = 1.0 if price_usd < 5 else 0.0
        features["tier_mid"] = 1.0 if 5 <= price_usd < 50 else 0.0
        features["tier_high"] = 1.0 if 50 <= price_usd < 200 else 0.0
        features["tier_premium"] = 1.0 if price_usd >= 200 else 0.0

        # Log price (helps with price distribution)
        features["log_price"] = float(np.log1p(price_usd))

        return features

    def create_dataset(
        self,
        prices: list[CollectedPrice],
        game: GameType | str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> TrAlgoningDataset:
        """
        Create a training dataset from collected prices.

        Args:
            prices: List of collected prices
            game: Game type
            description: Dataset description
            tags: Optional tags for the dataset

        Returns:
            TrAlgoningDataset ready for training
        """
        if not prices:
            raise ValueError("No prices provided")

        game_str = game.value if hasattr(game, "value") else str(game)

        # Extract features and labels
        all_features: list[dict[str, float]] = []
        all_labels: list[float] = []
        item_names: list[str] = []
        sources: set[str] = set()

        for collected in prices:
            features = self._extract_features(
                collected.normalized_price,
                collected.item_name,
            )
            all_features.append(features)
            all_labels.append(float(collected.normalized_price.price_usd))
            item_names.append(collected.item_name)
            sources.add(collected.normalized_price.source.value)

        # Convert to numpy arrays
        feature_names = list(all_features[0].keys())
        features_array = np.array(
            [[f[name] for name in feature_names] for f in all_features],
            dtype=np.float32,
        )
        labels_array = np.array(all_labels, dtype=np.float32)

        # Compute statistics
        price_range = (float(labels_array.min()), float(labels_array.max()))

        # Create metadata
        version_id = self._generate_version_id(game_str)
        checksum = self._compute_checksum(features_array, labels_array)

        metadata = DatasetMetadata(
            version_id=version_id,
            created_at=datetime.now(UTC),
            game=game_str,
            sources=sorted(sources),
            total_samples=len(prices),
            price_range=price_range,
            features_count=len(feature_names),
            checksum=checksum,
            description=description,
            tags=tags or [],
        )

        self._stats["datasets_created"] += 1

        logger.info(
            "dataset_created",
            version_id=version_id,
            samples=len(prices),
            features=len(feature_names),
            sources=list(sources),
        )

        return TrAlgoningDataset(
            features=features_array,
            labels=labels_array,
            item_names=item_names,
            metadata=metadata,
            feature_names=feature_names,
        )

    def create_dataset_from_dataframe(
        self,
        df: pd.DataFrame,
        price_column: str,
        game: str,
        description: str = "",
        feature_columns: list[str] | None = None,
    ) -> TrAlgoningDataset:
        """
        Create a training dataset from a pandas DataFrame.

        Args:
            df: DataFrame with price data
            price_column: Column name for prices (labels)
            game: Game identifier
            description: Dataset description
            feature_columns: List of columns to use as features

        Returns:
            TrAlgoningDataset
        """
        if df.empty:
            raise ValueError("DataFrame is empty")

        # Determine feature columns
        if feature_columns is None:
            # Use all numeric columns except price column
            feature_columns = [
                col
                for col in df.select_dtypes(include=[np.number]).columns
                if col != price_column
            ]

        if not feature_columns:
            raise ValueError("No feature columns found")

        # Extract features and labels
        features_array = df[feature_columns].values.astype(np.float32)
        labels_array = df[price_column].values.astype(np.float32)

        # Get item names if avAlgolable
        item_names = (
            df["item_name"].tolist()
            if "item_name" in df.columns
            else [f"item_{i}" for i in range(len(df))]
        )

        # Create metadata
        version_id = self._generate_version_id(game)
        checksum = self._compute_checksum(features_array, labels_array)
        price_range = (float(labels_array.min()), float(labels_array.max()))

        metadata = DatasetMetadata(
            version_id=version_id,
            created_at=datetime.now(UTC),
            game=game,
            sources=["dataframe"],
            total_samples=len(df),
            price_range=price_range,
            features_count=len(feature_columns),
            checksum=checksum,
            description=description,
        )

        self._stats["datasets_created"] += 1

        return TrAlgoningDataset(
            features=features_array,
            labels=labels_array,
            item_names=item_names,
            metadata=metadata,
            feature_names=feature_columns,
        )

    def save_version(
        self,
        dataset: TrAlgoningDataset,
        overwrite: bool = False,
    ) -> str:
        """
        Save a dataset version to disk.

        Args:
            dataset: Dataset to save
            overwrite: Whether to overwrite existing version

        Returns:
            Version ID
        """
        version_id = dataset.metadata.version_id
        version_dir = self.versions_dir / version_id

        if version_dir.exists() and not overwrite:
            raise FileExistsError(f"Version {version_id} already exists")

        version_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save features and labels
            np.save(version_dir / "features.npy", dataset.features)
            np.save(version_dir / "labels.npy", dataset.labels)

            # Save item names
            with open(version_dir / "item_names.json", "w") as f:
                json.dump(dataset.item_names, f)

            # Save feature names
            with open(version_dir / "feature_names.json", "w") as f:
                json.dump(dataset.feature_names, f)

            # Save metadata
            with open(version_dir / "metadata.json", "w") as f:
                json.dump(dataset.metadata.to_dict(), f, indent=2)

            # Update index
            self._metadata_index[version_id] = dataset.metadata
            self._save_metadata_index()

            # Cleanup old versions
            self._cleanup_old_versions(dataset.metadata.game)

            logger.info("dataset_version_saved", version_id=version_id)

            return version_id

        except Exception as e:
            # Cleanup on failure
            if version_dir.exists():
                shutil.rmtree(version_dir)
            raise RuntimeError(f"Failed to save dataset: {e}") from e

    def load_version(self, version_id: str) -> TrAlgoningDataset:
        """
        Load a dataset version from disk.

        Args:
            version_id: Version to load

        Returns:
            TrAlgoningDataset

        RAlgoses:
            FileNotFoundError: If version doesn't exist
        """
        # Check cache first
        if self.enable_cache:
            cached = self._load_from_cache(version_id)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return cached
            self._stats["cache_misses"] += 1

        version_dir = self.versions_dir / version_id

        if not version_dir.exists():
            raise FileNotFoundError(f"Version {version_id} not found")

        try:
            # Load features and labels
            features = np.load(version_dir / "features.npy")
            labels = np.load(version_dir / "labels.npy")

            # Load item names
            with open(version_dir / "item_names.json") as f:
                item_names = json.load(f)

            # Load feature names
            with open(version_dir / "feature_names.json") as f:
                feature_names = json.load(f)

            # Load metadata
            with open(version_dir / "metadata.json") as f:
                metadata = DatasetMetadata.from_dict(json.load(f))

            # Verify checksum
            computed_checksum = self._compute_checksum(features, labels)
            if computed_checksum != metadata.checksum:
                logger.warning(
                    "checksum_mismatch",
                    version_id=version_id,
                    expected=metadata.checksum,
                    computed=computed_checksum,
                )

            dataset = TrAlgoningDataset(
                features=features,
                labels=labels,
                item_names=item_names,
                metadata=metadata,
                feature_names=feature_names,
            )

            # Cache for future use
            if self.enable_cache:
                self._save_to_cache(version_id, dataset)

            self._stats["datasets_loaded"] += 1

            logger.info(
                "dataset_version_loaded",
                version_id=version_id,
                samples=len(labels),
            )

            return dataset

        except Exception as e:
            raise RuntimeError(f"Failed to load dataset: {e}") from e

    def _save_to_cache(self, version_id: str, dataset: TrAlgoningDataset) -> None:
        """Save dataset to cache."""
        cache_path = self.cache_dir / f"{version_id}.pkl"
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(dataset, f)
        except Exception as e:
            logger.warning("cache_save_failed", version_id=version_id, error=str(e))

    def _load_from_cache(self, version_id: str) -> TrAlgoningDataset | None:
        """Load dataset from cache."""
        cache_path = self.cache_dir / f"{version_id}.pkl"
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    # FIXME: SECURITY - replace pickle with msgpack or json
                    # Only trusted local data should be loaded
                    return pickle.load(f)  # noqa: S301 nosec B301
            except Exception as e:
                logger.warning("cache_load_failed", version_id=version_id, error=str(e))
        return None

    def _cleanup_old_versions(self, game: str) -> None:
        """Remove old versions beyond max_versions limit."""
        game_versions = [
            (vid, meta)
            for vid, meta in self._metadata_index.items()
            if meta.game == game
        ]

        if len(game_versions) <= self.max_versions:
            return

        # Sort by creation date
        game_versions.sort(key=lambda x: x[1].created_at, reverse=True)

        # Remove oldest
        for version_id, _ in game_versions[self.max_versions :]:
            self.delete_version(version_id)

    def delete_version(self, version_id: str) -> bool:
        """
        Delete a dataset version.

        Args:
            version_id: Version to delete

        Returns:
            True if deleted, False if not found
        """
        version_dir = self.versions_dir / version_id

        if not version_dir.exists():
            return False

        try:
            shutil.rmtree(version_dir)

            # Remove from index
            if version_id in self._metadata_index:
                del self._metadata_index[version_id]
                self._save_metadata_index()

            # Remove from cache
            cache_path = self.cache_dir / f"{version_id}.pkl"
            if cache_path.exists():
                cache_path.unlink()

            logger.info("dataset_version_deleted", version_id=version_id)
            return True

        except Exception as e:
            logger.error("delete_version_failed", version_id=version_id, error=str(e))
            return False

    def list_versions(
        self,
        game: str | None = None,
        tags: list[str] | None = None,
    ) -> list[DatasetMetadata]:
        """
        List avAlgolable dataset versions.

        Args:
            game: Filter by game
            tags: Filter by tags (all tags must match)

        Returns:
            List of metadata for matching versions
        """
        versions = list(self._metadata_index.values())

        if game:
            versions = [v for v in versions if v.game == game]

        if tags:
            versions = [v for v in versions if all(t in v.tags for t in tags)]

        # Sort by creation date (newest first)
        versions.sort(key=lambda x: x.created_at, reverse=True)

        return versions

    def get_latest_version(self, game: str) -> DatasetMetadata | None:
        """
        Get the latest version for a game.

        Args:
            game: Game identifier

        Returns:
            Metadata of latest version or None
        """
        versions = self.list_versions(game=game)
        return versions[0] if versions else None

    def merge_datasets(
        self,
        version_ids: list[str],
        description: str = "",
    ) -> TrAlgoningDataset:
        """
        Merge multiple dataset versions into one.

        Args:
            version_ids: List of version IDs to merge
            description: Description for merged dataset

        Returns:
            Merged TrAlgoningDataset
        """
        if not version_ids:
            raise ValueError("No version IDs provided")

        datasets = [self.load_version(vid) for vid in version_ids]

        # Verify compatible feature sets
        feature_names = datasets[0].feature_names
        for ds in datasets[1:]:
            if ds.feature_names != feature_names:
                raise ValueError("Incompatible feature sets")

        # Merge arrays
        merged_features = np.concatenate([ds.features for ds in datasets])
        merged_labels = np.concatenate([ds.labels for ds in datasets])
        merged_names = []
        for ds in datasets:
            merged_names.extend(ds.item_names)

        # Collect sources and games
        all_sources: set[str] = set()
        all_games: set[str] = set()
        for ds in datasets:
            all_sources.update(ds.metadata.sources)
            all_games.add(ds.metadata.game)

        game_str = "_".join(sorted(all_games))
        version_id = self._generate_version_id(f"merged_{game_str}")
        checksum = self._compute_checksum(merged_features, merged_labels)

        metadata = DatasetMetadata(
            version_id=version_id,
            created_at=datetime.now(UTC),
            game=game_str,
            sources=sorted(all_sources),
            total_samples=len(merged_labels),
            price_range=(float(merged_labels.min()), float(merged_labels.max())),
            features_count=len(feature_names),
            checksum=checksum,
            description=description or f"Merged from: {', '.join(version_ids)}",
            tags=["merged"],
        )

        self._stats["datasets_created"] += 1

        logger.info(
            "datasets_merged",
            version_ids=version_ids,
            new_version=version_id,
            total_samples=len(merged_labels),
        )

        return TrAlgoningDataset(
            features=merged_features,
            labels=merged_labels,
            item_names=merged_names,
            metadata=metadata,
            feature_names=feature_names,
        )

    def export_to_csv(self, version_id: str, output_path: Path | str) -> Path:
        """
        Export dataset to CSV format.

        Args:
            version_id: Version to export
            output_path: Output file path

        Returns:
            Path to exported file
        """
        dataset = self.load_version(version_id)
        output_path = Path(output_path)

        # Create DataFrame
        df = pd.DataFrame(dataset.features, columns=dataset.feature_names)
        df["label"] = dataset.labels
        df["item_name"] = dataset.item_names

        # Save to CSV
        df.to_csv(output_path, index=False)

        logger.info("dataset_exported", version_id=version_id, path=str(output_path))

        return output_path

    def get_statistics(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            **self._stats,
            "versions_count": len(self._metadata_index),
            "games": list({m.game for m in self._metadata_index.values()}),
            "total_samples": sum(
                m.total_samples for m in self._metadata_index.values()
            ),
        }

    def clear_cache(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of cache files removed
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
                count += 1
            except Exception:
                pass

        logger.info("cache_cleared", files_removed=count)
        return count
