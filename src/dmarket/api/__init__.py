"""Modular DMarket API client package."""

from src.dmarket.api.client import GAME_MAP, BaseDMarketClient
from src.dmarket.api.extended import ExtendedMixin
from src.dmarket.api.inventory import InventoryMixin
from src.dmarket.api.market import MarketMixin
from src.dmarket.api.trading import TradingMixin
from src.dmarket.api.wallet import WalletMixin

__all__ = [
    "BaseDMarketClient",
    "GAME_MAP",
    "MarketMixin",
    "WalletMixin",
    "TradingMixin",
    "InventoryMixin",
    "ExtendedMixin",
]
