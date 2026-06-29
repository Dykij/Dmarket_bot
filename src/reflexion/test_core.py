"""
Test suite for the Reflexive Engine (core.py).
Covers: unit, property-based, integration, snapshot/rollback.
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.reflexion.core import (
    FileSnapshot,
    ReflexionConfig,
    SnapshotManager,
    SnapshotManifest,
    SnapshotState,
    make_snapshot,
    rollback_to,
    _hash_file,
)


@pytest.fixture
def dummy_repo():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        # Initialize git so auto_commit_on_snapshot works
        import subprocess
        subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True)
        # Create dummy files
        (repo / "main.py").write_text("print('hello')\n")
        (repo / "utils.py").write_text("def add(x, y): return x + y\n")
        sub = repo / "sub"
        sub.mkdir()
        (sub / "data.txt").write_text("42\n")
        yield str(repo)


def test_config_creation():
    cfg = ReflexionConfig(repo_root="/tmp/repo")
    assert cfg.max_snapshots == 50
    assert cfg.auto_commit_on_snapshot is True


def test_snapshot_manifest_parsing():
    data = {
        "id": "snap_001",
        "timestamp": "2026-06-29T00:00:00Z",
        "state": "pending",
        "files": [
            {"path": "a.py", "sha256": "a" * 64, "size": 10, "mtime": 0.0}
        ],
    }
    manifest = SnapshotManifest.model_validate(data)
    assert manifest.state == SnapshotState.PENDING


def test_file_snapshot_validation():
    fs = FileSnapshot(path="foo.py", sha256="a" * 64, size=10, mtime=0.0)
    assert fs.path == "foo.py"


def test_snapshot_creation(dummy_repo):
    cfg = ReflexionConfig(repo_root=dummy_repo, auto_commit_on_snapshot=False)
    mgr = SnapshotManager(cfg)
    manifest = mgr.create(label="unit_test")
    assert manifest.state == SnapshotState.PENDING
    assert len(manifest.files) >= 3


def test_validate_and_rollback(dummy_repo):
    cfg = ReflexionConfig(repo_root=dummy_repo, auto_commit_on_snapshot=False)
    mgr = SnapshotManager(cfg)
    manifest = mgr.create(label="unit_test")
    # Validate before modification
    assert mgr.validate(manifest.id) is True
    # Modify a file
    (Path(dummy_repo) / "main.py").write_text("print('modified')\n")
    # Should fail validation
    assert mgr.validate(manifest.id) is False
    # Rollback (restore from stored content if git not present)
    assert mgr.rollback(manifest.id) is True
    # Check file restored
    assert "hello" in (Path(dummy_repo) / "main.py").read_text()


def test_rollback_to_api(dummy_repo):
    cfg = ReflexionConfig(repo_root=dummy_repo, auto_commit_on_snapshot=False)
    mgr = SnapshotManager(cfg)
    manifest = mgr.create(label="api_test")
    # Modify
    (Path(dummy_repo) / "main.py").write_text("print('api')\n")
    # Rollback using API (fallback restores content from backup)
    assert rollback_to(dummy_repo, manifest.id) is True
    assert "hello" in (Path(dummy_repo) / "main.py").read_text()


def test_snapshot_prune(dummy_repo):
    cfg = ReflexionConfig(repo_root=dummy_repo, max_snapshots=2, auto_commit_on_snapshot=False)
    mgr = SnapshotManager(cfg)
    for i in range(5):
        mgr.create(label=f"batch_{i}")
    all_manifests = mgr.store.list_all()
    assert len(all_manifests) == 2


# ── Property-based / Invariant tests ──


import hypothesis
from hypothesis import given, strategies as st


# Property: hash_file for same content is deterministic
@given(st.text(), st.text())
def test_hash_is_deterministic_and_sensitive(text1, text2):
    with tempfile.TemporaryDirectory() as d:
        path1 = Path(d) / "a.txt"
        path1.write_text(text1, encoding="utf-8")
        h1 = _hash_file(path1)
        h2 = _hash_file(path1)
        assert h1 == h2
        if text1 != text2:
            path2 = Path(d) / "b.txt"
            path2.write_text(text2, encoding="utf-8")
            h3 = _hash_file(path2)
            assert h1 != h3 or text1.encode() == text2.encode()


# Invariant: snapshot id is always unique
def test_snapshot_id_uniqueness(dummy_repo):
    cfg = ReflexionConfig(repo_root=dummy_repo, auto_commit_on_snapshot=False)
    mgr = SnapshotManager(cfg)
    ids = {mgr.create(label="u").id for _ in range(20)}
    assert len(ids) == 20
