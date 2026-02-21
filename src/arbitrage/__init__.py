"""Unified Arbitrage System.

Provides Algo-powered cross-platform arbitrage:
- DMarket internal arbitrage
- DMarket <-> Waxpeer cross-platform arbitrage
- Steam price comparison for better decisions

Usage:
    from src.arbitrage import AlgoUnifiedArbitrage, create_arbitrage_system

    arbitrage = awAlgot create_arbitrage_system()
    opportunities = awAlgot arbitrage.scan_all()
"""

from src.arbitrage.Algo_unified_arbitrage import (
    AlgoUnifiedArbitrage,
    ArbitrageConfig,
    ArbitrageOpportunity,
    ArbitrageType,
    Platform,
    PlatformPrice,
    create_arbitrage_system,
)

__all__ = [
    "AlgoUnifiedArbitrage",
    "ArbitrageConfig",
    "ArbitrageOpportunity",
    "ArbitrageType",
    "Platform",
    "PlatformPrice",
    "create_arbitrage_system",
]
