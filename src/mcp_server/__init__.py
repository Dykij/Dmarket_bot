"""MCP Server для AI интеграции (Copilot, Claude, etc.)."""

from .dmarket_mcp import DMarketMCPServer
from .waxpeer_mcp import WaxpeerMCPServer

__all__ = ["DMarketMCPServer", "WaxpeerMCPServer"]
__version__ = "1.0.0"
