"""Modular DMarket API client package."""

from src.dmarket.api.client import BaseDMarketClient, GAME_MAP
from src.dmarket.api.market import MarketMixin
from src.dmarket.api.wallet import WalletMixin
from src.dmarket.api.trading import TradingMixin
from src.dmarket.api.inventory import InventoryMixin
from src.dmarket.api.extended import ExtendedMixin

__all__ = [
    "BaseDMarketClient",
    "GAME_MAP",
    "MarketMixin",
    "WalletMixin",
    "TradingMixin",
    "InventoryMixin",
    "ExtendedMixin",
]
