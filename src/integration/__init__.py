"""Integration module for unified bot improvements.

This module provides a unified interface to integrate all new improvements
into the existing bot architecture without breaking existing functionality.

Components:
- BotIntegrator: Main orchestrator for all improvements
- ServiceRegistry: Dependency injection container
- EventBus: Event-driven communication between modules
- HealthAggregator: Unified health monitoring

Created: January 10, 2026
"""

from src.integration.bot_integrator import BotIntegrator
from src.integration.event_bus import EventBus
from src.integration.health_aggregator import HealthAggregator
from src.integration.service_registry import ServiceRegistry

__all__ = [
    "BotIntegrator",
    "EventBus",
    "HealthAggregator",
    "ServiceRegistry",
]
