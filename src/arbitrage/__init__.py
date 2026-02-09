"""Unified Arbitrage System.

Provides AI-powered cross-platform arbitrage:
- DMarket internal arbitrage
- DMarket <-> Waxpeer cross-platform arbitrage
- Steam price comparison for better decisions

Usage:
    from src.arbitrage import AIUnifiedArbitrage, create_arbitrage_system

    arbitrage = await create_arbitrage_system()
    opportunities = await arbitrage.scan_all()
"""

from src.arbitrage.ai_unified_arbitrage import (
    AIUnifiedArbitrage,
    ArbitrageConfig,
    ArbitrageOpportunity,
    ArbitrageType,
    Platform,
    PlatformPrice,
    create_arbitrage_system,
)

__all__ = [
    "AIUnifiedArbitrage",
    "ArbitrageConfig",
    "ArbitrageOpportunity",
    "ArbitrageType",
    "Platform",
    "PlatformPrice",
    "create_arbitrage_system",
]
