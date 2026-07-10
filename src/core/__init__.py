"""
Core package — application infrastructure.
"""

from src.core.app_initialization import ComponentInitializer
from src.core.app_lifecycle import ApplicationLifecycle
from src.core.app_notifications import NotificationManager
from src.core.app_recovery import TradeRecovery
from src.core.app_signals import SignalHandler
from src.core.application import Application

__all__ = [
    "Application",
    "SignalHandler",
    "ApplicationLifecycle",
    "TradeRecovery",
    "NotificationManager",
    "ComponentInitializer",
]
