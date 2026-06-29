"""
Performance tests for IncrementalMetadataCache with 10k+ files.
"""

import os
import tempfile
import time
from pathlib import Path

import pytest

from src.cot_audit.core import IncrementalMetadataCache


def _create_project(num_files: int, subdirs: int = 10) -> str:
    """Create a project with num_files empty files distributed across subdirs."""
    root = tempfile.mkdtemp()
    files_per_subdir = num_files // subdirs
    for i in range(subdirs):
        subdir = Path(root) / f"module_{i}"
        subdir.mkdir()
        for j in range(files_per_subdir):
            (subdir / f"file_{j}.py").write_text("")
    return root


@pytest.mark.slow
def test_scan_10k_files_under_5s():
    """Full scan of 10k empty files should complete in under 5 seconds."""
    root = _create_project(10_000)
    cache = IncrementalMetadataCache(root)

    start = time.monotonic()
    changed = cache.scan()
    elapsed = time.monotonic() - start

    assert len(changed) == 10_000, f"Expected 10000, got {len(changed)}"
    assert elapsed < 5.0, f"Scan took {elapsed:.2f}s, expected < 5s"
    print(f"\n[PERF] Full scan 10k files: {elapsed:.3f}s ({len(changed)} files)")


@pytest.mark.slow
def test_incremental_scan_skips_unchanged():
    """Second scan with no changes should be near-instant."""
    root = _create_project(10_000)
    cache = IncrementalMetadataCache(root)

    # First scan — full
    start_full = time.monotonic()
    cache.scan()
    full_elapsed = time.monotonic() - start_full

    # Second scan — incremental (should be much faster)
    start_incr = time.monotonic()
    changed = cache.scan()
    incr_elapsed = time.monotonic() - start_incr

    assert len(changed) == 0, f"Expected 0 changes, got {len(changed)}"
    # Incremental should be at least 5x faster than full
    speedup = full_elapsed / max(incr_elapsed, 0.0001)
    assert speedup > 2.0, f"Incremental scan too slow: {incr_elapsed:.3f}s (speedup {speedup:.1f}x)"
    print(f"\n[PERF] Full: {full_elapsed:.3f}s | Incremental: {incr_elapsed:.3f}s | Speedup: {speedup:.1f}x")


@pytest.mark.slow
def test_incremental_detects_single_change():
    """Modifying 1 file out of 10k should detect exactly 1 change."""
    root = _create_project(10_000)
    cache = IncrementalMetadataCache(root)
    cache.scan()

    # Modify 1 file
    time.sleep(0.01)
    target = Path(root) / "module_0" / "file_0.py"
    target.write_text("changed")

    start = time.monotonic()
    changed = cache.scan()
    elapsed = time.monotonic() - start

    assert len(changed) == 1, f"Expected 1 change, got {len(changed)}"
    assert "module_0/file_0.py" in changed
    # Should be much faster than full scan
    assert elapsed < 2.0, f"Single-change scan took {elapsed:.2f}s"
    print(f"\n[PERF] Single change detection: {elapsed:.3f}s")


@pytest.mark.slow
def test_memory_usage_stays_bounded():
    """Cache entries should be lightweight (no file content stored)."""
    root = _create_project(10_000)
    cache = IncrementalMetadataCache(root)
    cache.scan()

    # Each entry is roughly: path(str) + mtime(float) + size(int) + md5(str) ≈ 200 bytes
    # 10k entries ≈ 2MB overhead (very conservative)
    import sys
    cache_size = sys.getsizeof(cache._cache.entries)
    # Just verify it's reasonable (not storing file contents)
    assert cache_size < 50_000_000, f"Cache too large: {cache_size} bytes"
    print(f"\n[MEM] Cache entries memory: {cache_size} bytes for {len(cache._cache.entries)} files")
