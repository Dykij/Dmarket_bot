"""
exceptions.py — Exceptions raised by the DMarket API client.
"""


class SecurityViolation(Exception):
    """Raised when request parameters violate safety allowlists."""

    pass
