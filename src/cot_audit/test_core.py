"""
Test suite for CoT Audit & Metadata Cache (core.py).
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.cot_audit.core import (
    CoTLogEntry,
    CoTReport,
    FormatStyle,
    IncrementalMetadataCache,
    MetadataEntry,
)


# ── CoT Report Tests ──

async def test_cot_report_markdown():
    report = CoTReport(session_id="test-001")
    report.entries.append(CoTLogEntry(step_number=1, title="Analyze", content="Looking at data..."))
    report.entries.append(CoTLogEntry(step_number=2, title="Decide", content="Going with plan A", reasoning="Best ROI"))
    report.final_answer = "Deploy"
    md = report.to_markdown()
    assert "# Chain-of-Thought Report: test-001" in md
    assert "## Step 1: Analyze" in md
    assert "**Final Answer:** Deploy" in md


async def test_cot_user_friendly():
    report = CoTReport(session_id="test-002")
    report.entries.append(CoTLogEntry(step_number=1, title="A", content="B"))
    report.entries.append(CoTLogEntry(step_number=2, title="C", content="D"))
    text = report.to_user_friendly(FormatStyle.NUMBERED)
    assert "1. A: B" in text
    assert "2. C: D" in text


# ── Metadata Cache Tests ──

@pytest.fixture
def dummy_project():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "project"
        root.mkdir()
        (root / "main.py").write_text("print('hello')", encoding="utf-8")
        (root / "utils.py").write_text("def add(): pass", encoding="utf-8")
        sub = root / "sub"
        sub.mkdir()
        (sub / "data.txt").write_text("42", encoding="utf-8")
        yield str(root)


async def test_scan_picks_up_files(dummy_project):
    cache = IncrementalMetadataCache(dummy_project)
    changed = cache.scan()
    assert len(changed) == 3
    assert "main.py" in changed
    assert "utils.py" in changed
    assert "sub/data.txt" in changed


async def test_incremental_scan_no_changes(dummy_project):
    cache = IncrementalMetadataCache(dummy_project)
    cache.scan()
    # Second scan should find nothing changed
    changed = cache.scan()
    assert len(changed) == 0


async def test_incremental_detects_modification(dummy_project):
    cache = IncrementalMetadataCache(dummy_project)
    cache.scan()
    # Modify a file
    import time
    time.sleep(0.01)
    (Path(dummy_project) / "main.py").write_text("print('changed')", encoding="utf-8")
    changed = cache.scan()
    assert "main.py" in changed
    assert len(changed) == 1


async def test_invalidate(dummy_project):
    cache = IncrementalMetadataCache(dummy_project)
    cache.scan()
    cache.invalidate(os.path.join(dummy_project, "main.py"))
    assert cache.get(os.path.join(dummy_project, "main.py")) is None


async def test_get_entry(dummy_project):
    cache = IncrementalMetadataCache(dummy_project)
    cache.scan()
    entry = cache.get(os.path.join(dummy_project, "main.py"))
    assert entry is not None
    assert entry.path == "main.py"
