"""
Waxpeer Integration Module.

Модуль для интеграции с P2P-площадкой Waxpeer для продажи CS2 скинов.
"""

from src.waxpeer.waxpeer_api import WaxpeerAPI
from src.waxpeer.waxpeer_manager import WaxpeerManager

__all__ = ["WaxpeerAPI", "WaxpeerManager"]
