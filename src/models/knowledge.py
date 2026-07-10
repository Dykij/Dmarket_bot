"""Knowledge models."""
from dataclasses import dataclass


@dataclass
class KnowledgeEntry:
    id: str = ""
    title: str = ""
    content: dict | None = None


@dataclass
class LessonLearned:
    id: str = ""
    lesson: str = ""


@dataclass
class TradingPattern:
    id: str = ""
    pattern_name: str = ""
