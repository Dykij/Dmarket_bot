"""item_utils.py — Shared helpers for DMarket item dict normalization.

DMarket API V1 uses top-level 'title', V2 nests it under 'attributes'.
This module provides a single extraction point to avoid scattered fallbacks.
"""

from __future__ import annotations

from typing import Any


def get_item_title(item: dict[str, Any]) -> str:
    """Extract item title from V1 or V2 DMarket API format.

    V1: {"title": "AK-47 | Redline"}
    V2: {"attributes": [{"key": "title", "value": "AK-47 | Redline"}]}
    V2 flat (some endpoints): {"attributes": {"title": "AK-47 | Redline"}}
    """
    title = item.get("title", "")
    if title:
        return title
    attrs = item.get("attributes")
    if isinstance(attrs, dict):
        return attrs.get("title", "")
    if isinstance(attrs, list):
        for attr in attrs:
            if isinstance(attr, dict) and attr.get("key") == "title":
                return attr.get("value", "")
    return ""
