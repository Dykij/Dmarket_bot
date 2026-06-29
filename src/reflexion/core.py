"""
Reflexive Engine — модуль States/Snapshot + rollback для OpenCode.
Паттерн: State/Snapshot + Memento для восстановления состояния.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Union

from pydantic import BaseModel, Field, ValidationError


class SnapshotState(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FileSnapshot(BaseModel):
    path: str
    sha256: str
    size: int
    mtime: float
    content_b64: Optional[str] = None  # lazy


class SnapshotManifest(BaseModel):
    id: str
    timestamp: str
    state: SnapshotState = SnapshotState.PENDING
    files: List[FileSnapshot] = Field(default_factory=list)
    git_commit: Optional[str] = None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


class ReflexionConfig(BaseModel):
    repo_root: str
    max_snapshots: int = 50
    auto_commit_on_snapshot: bool = True

    class Config:
        frozen = True


class StateStore:
    """CRUD for snapshots on disk."""

    def __init__(self, root: str):
        self.root = Path(root) / ".reflexion"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, manifest: SnapshotManifest) -> None:
        path = self.root / f"{manifest.id}.json"
        path.write_text(manifest.to_json())

    def load(self, snapshot_id: str) -> SnapshotManifest:
        path = self.root / f"{snapshot_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Snapshot {snapshot_id} not found")
        return SnapshotManifest.model_validate_json(path.read_text())

    def list_all(self) -> List[SnapshotManifest]:
        manifests = []
        for f in sorted(self.root.glob("*.json")):
            try:
                manifests.append(SnapshotManifest.model_validate_json(f.read_text()))
            except ValidationError:
                continue
        return manifests

    def prune(self, keep: int) -> int:
        """Return number of deleted snapshots."""
        all_manifests = self.list_all()
        if len(all_manifests) <= keep:
            return 0
        to_delete = all_manifests[:-keep]
        for manifest in to_delete:
            (self.root / f"{manifest.id}.json").unlink(missing_ok=True)
        return len(to_delete)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class SnapshotManager:
    """
    Orchestrates snapshot creation, validation, and rollback.
    """

    def __init__(self, config: ReflexionConfig):
        self.config = config
        self.store = StateStore(config.repo_root)

    def create(self, label: str = "snapshot") -> SnapshotManifest:
        """Create a new snapshot of the current repo state."""
        repo = Path(self.config.repo_root)
        snapshot_id = f"{label}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        files: List[FileSnapshot] = []

        for root, _, filenames in os.walk(repo):
            if ".git" in root:
                continue
            for name in filenames:
                fpath = Path(root) / name
                if not fpath.is_file():
                    continue
                files.append(
                    FileSnapshot(
                        path=str(fpath.relative_to(repo)),
                        sha256=_hash_file(fpath),
                        size=fpath.stat().st_size,
                        mtime=fpath.stat().st_mtime,
                    )
                )

        manifest = SnapshotManifest(
            id=snapshot_id,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            state=SnapshotState.PENDING,
            files=files,
        )

        # Backup file contents for non-git fallback rollback
        backup_dir = Path(self.config.repo_root) / ".reflexion" / "backups" / snapshot_id
        for f in files:
            src = Path(self.config.repo_root) / f.path
            if src.exists():
                dst = backup_dir / f.path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        if self.config.auto_commit_on_snapshot:
            try:
                result = subprocess.run(
                    ["git", "add", "-A"],
                    cwd=self.config.repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"git add failed: {result.stderr}")
                result = subprocess.run(
                    ["git", "commit", "-m", f"[reflexion] snapshot {snapshot_id}"],
                    cwd=self.config.repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    commit_hash = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=self.config.repo_root,
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout.strip()
                    manifest.git_commit = commit_hash
            except Exception:
                pass  # Non-critical: best-effort git commit

        self.store.save(manifest)
        self.store.prune(self.config.max_snapshots)
        return manifest

    def validate(self, snapshot_id: str) -> bool:
        manifest = self.store.load(snapshot_id)
        for f in manifest.files:
            full_path = Path(self.config.repo_root) / f.path
            if not full_path.exists():
                return False
            if _hash_file(full_path) != f.sha256:
                return False
        manifest.state = SnapshotState.VALIDATED
        self.store.save(manifest)
        return True

    def rollback(self, snapshot_id: str) -> bool:
        manifest = self.store.load(snapshot_id)
        if manifest.git_commit:
            try:
                subprocess.run(
                    ["git", "reset", "--hard", manifest.git_commit],
                    cwd=self.config.repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                manifest.state = SnapshotState.ROLLED_BACK
                self.store.save(manifest)
                return True
            except subprocess.CalledProcessError:
                pass

        # Fallback: restore from content backup if git unavailable
        backup_dir = Path(self.config.repo_root) / ".reflexion" / "backups" / snapshot_id
        if backup_dir.exists():
            for root, _, filenames in os.walk(backup_dir):
                for name in filenames:
                    src = Path(root) / name
                    rel = src.relative_to(backup_dir)
                    dst = Path(self.config.repo_root) / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        manifest.state = SnapshotState.ROLLED_BACK
        self.store.save(manifest)
        return True


# ── Convenience entry ──

def make_snapshot(repo_root: str, label: str = "auto") -> SnapshotManifest:
    cfg = ReflexionConfig(repo_root=repo_root)
    mgr = SnapshotManager(cfg)
    return mgr.create(label)


def rollback_to(repo_root: str, snapshot_id: str) -> bool:
    cfg = ReflexionConfig(repo_root=repo_root)
    mgr = SnapshotManager(cfg)
    return mgr.rollback(snapshot_id)
