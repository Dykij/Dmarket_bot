"""
api/exceptions.py — Shared API exceptions (v14.9).

Shared across all oracle implementations.
"""

from __future__ import annotations


class RateLimitException(Exception):
    """Rate limit hit (429). Transient — auto-resolves after cooldown."""


class OracleError(Exception):
    """Base exception for oracle failures."""


class OracleTimeout(OracleError):
    """Oracle request timed out."""


class OracleAuthError(OracleError):
    """Oracle authentication failed (401/403)."""
