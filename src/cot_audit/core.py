"""
CoT Audit & Metadata Cache — форматирование Chain-of-Thought и инкрементальное кэширование.
Паттерн: Observer + LRU Cache с invalidation по mtime/md5.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from functools import lru_cache

from pydantic import BaseModel, Field


class FormatStyle(str, Enum):
    BULLET = "bullet"
    NUMBERED = "numbered"
    HEADING = "heading"
    MARKDOWN = "markdown"


class CoTLogEntry(BaseModel):
    step_number: int
    title: str
    content: str
    reasoning: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class CoTReport(BaseModel):
    session_id: str
    entries: List[CoTLogEntry] = Field(default_factory=list)
    final_answer: Optional[str] = None

    def to_markdown(self) -> str:
        lines = [f"# Chain-of-Thought Report: {self.session_id}\n"]
        for entry in self.entries:
            lines.append(f"## Step {entry.step_number}: {entry.title}\n")
            if entry.reasoning:
                lines.append(f"**Reasoning:** {entry.reasoning}\n")
            lines.append(f"{entry.content}\n")
        if self.final_answer:
            lines.append(f"\n---\n\n**Final Answer:** {self.final_answer}\n")
        return "\n".join(lines)

    def to_user_friendly(self, style: FormatStyle = FormatStyle.BULLET) -> str:
        if style == FormatStyle.BULLET:
            return self.to_markdown().replace("## ", "- ")
        elif style == FormatStyle.NUMBERED:
            lines = []
            for i, entry in enumerate(self.entries, 1):
                lines.append(f"{i}. {entry.title}: {entry.content}")
            return "\n".join(lines)
        return self.to_markdown()


class MetadataEntry(BaseModel):
    path: str
    mtime: float
    size: int
    md5: str


class MetadataCache(BaseModel):
    version: str = "1.0"
    root: str
    entries: Dict[str, MetadataEntry] = Field(default_factory=dict)
    last_scan: float = 0.0


# ── Memory cache for hot paths ──

@lru_cache(maxsize=128)
def _hash_file_path(path: str) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


class IncrementalMetadataCache:
    """
    Инкрементальное кэширование метаданных проекта.
    Перечитывает только изменённые директории.
    """

    def __init__(self, root: str, cache_file: Optional[str] = None):
        self.root = Path(root)
        self.cache_file = Path(cache_file) if cache_file else self.root / ".metadata_cache.json"
        self._cache: MetadataCache = self._load_cache()

    def _load_cache(self) -> MetadataCache:
        if self.cache_file.exists():
            try:
                return MetadataCache.model_validate_json(self.cache_file.read_text())
            except Exception:
                pass
        return MetadataCache(root=str(self.root))

    def _save_cache(self) -> None:
        self.cache_file.write_text(self._cache.model_dump_json(indent=2))

    def scan(self) -> Dict[str, MetadataEntry]:
        """Perform incremental scan. Only reads directories with changed mtime."""
        current_entries: Dict[str, MetadataEntry] = {}
        changed: Set[str] = set()

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.root))
            if rel.startswith("."):
                continue
            stat = path.stat()
            cached = self._cache.entries.get(rel)
            if cached and cached.mtime == stat.st_mtime and cached.size == stat.st_size:
                current_entries[rel] = cached
                continue
            # Re-hash changed or new file
            md5 = hashlib.md5(path.read_bytes()).hexdigest()
            entry = MetadataEntry(path=rel, mtime=stat.st_mtime, size=stat.st_size, md5=md5)
            current_entries[rel] = entry
            changed.add(rel)

        # Detect deletions
        deleted = set(self._cache.entries.keys()) - set(current_entries.keys())
        for d in deleted:
            changed.add(d)

        self._cache.entries = current_entries
        self._cache.last_scan = time.time()
        self._save_cache()
        return {k: v for k, v in current_entries.items() if k in changed}

    def invalidate(self, path: str) -> None:
        """Invalidate a specific path from cache."""
        rel = str(Path(path).relative_to(self.root))
        if rel in self._cache.entries:
            del self._cache.entries[rel]
            self._save_cache()

    def get(self, path: str) -> Optional[MetadataEntry]:
        rel = str(Path(path).relative_to(self.root))
        return self._cache.entries.get(rel)
