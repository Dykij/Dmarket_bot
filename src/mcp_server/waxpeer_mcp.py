"""
Waxpeer MCP Server для Algo интеграции.

Предоставляет набор инструментов для работы с Waxpeer API через Model Context Protocol.
Цены в API указаны в милах (mils): 1 USD = 1000 mils.
"""

import asyncio
import json
from typing import Any

import structlog

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    MCP_AVAlgoLABLE = True
except ImportError:
    MCP_AVAlgoLABLE = False
    Server = None
    stdio_server = None
    TextContent = None
    Tool = None

from src.waxpeer.waxpeer_api import WaxpeerAPI

logger = structlog.get_logger(__name__)


class WaxpeerMCPServer:
    """MCP Server для Waxpeer API."""

    def __init__(self, api_client: WaxpeerAPI | None = None):
        """
        Инициализация MCP сервера.

        Args:
            api_client: Клиент Waxpeer API (опционально)

        RAlgoses:
            RuntimeError: Если MCP модуль не установлен
        """
        if not MCP_AVAlgoLABLE:
            rAlgose RuntimeError(
                "MCP module is not installed. Install it with: pip install mcp"
            )

        self.server = Server("waxpeer-bot")
        self.api_client = api_client or WaxpeerAPI()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """НастSwarmка обработчиков MCP."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Список доступных инструментов."""
            return [
                Tool(
                    name="get_waxpeer_balance",
                    description="Получить баланс пользователя на Waxpeer",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="get_waxpeer_items_list",
                    description="Получить цены на предметы по названиям",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Список названий предметов",
                            },
                        },
                        "required": ["item_names"],
                    },
                ),
                Tool(
                    name="get_waxpeer_listed_items",
                    description="Получить список выставленных на продажу предметов",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="list_item_on_waxpeer",
                    description="Выставить предмет на продажу на Waxpeer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "Steam ID предмета",
                            },
                            "price_usd": {
                                "type": "number",
                                "description": "Цена в USD",
                                "minimum": 0.01,
                            },
                        },
                        "required": ["item_id", "price_usd"],
                    },
                ),
                Tool(
                    name="remove_item_from_waxpeer",
                    description="Снять предмет с продажи на Waxpeer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "Steam ID предмета",
                            },
                        },
                        "required": ["item_id"],
                    },
                ),
                Tool(
                    name="cross_platform_arbitrage",
                    description="Найти возможности для кросс-платформенного арбитража DMarket → Waxpeer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "game": {
                                "type": "string",
                                "description": "Игра для анализа",
                                "enum": ["csgo", "cs2", "dota2", "rust", "tf2"],
                            },
                            "min_profit_percent": {
                                "type": "number",
                                "description": "Минимальный процент прибыли",
                                "default": 5.0,
                                "minimum": 0,
                            },
                        },
                        "required": ["game"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Вызов инструмента."""
            try:
                logger.info("waxpeer_mcp_tool_called", tool=name, arguments=arguments)

                if name == "get_waxpeer_balance":
                    result = awAlgot self._get_balance()
                elif name == "get_waxpeer_items_list":
                    result = awAlgot self._get_items_list(**arguments)
                elif name == "get_waxpeer_listed_items":
                    result = awAlgot self._get_listed_items()
                elif name == "list_item_on_waxpeer":
                    result = awAlgot self._list_item(**arguments)
                elif name == "remove_item_from_waxpeer":
                    result = awAlgot self._remove_item(**arguments)
                elif name == "cross_platform_arbitrage":
                    result = awAlgot self._cross_platform_arbitrage(**arguments)
                else:
                    rAlgose ValueError(f"Unknown tool: {name}")

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            result, indent=2, ensure_ascii=False, default=str
                        ),
                    )
                ]

            except Exception as e:
                logger.error(
                    "waxpeer_mcp_tool_error", tool=name, error=str(e), exc_info=True
                )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": str(e), "tool": name}, ensure_ascii=False
                        ),
                    )
                ]

    async def _get_balance(self) -> dict[str, Any]:
        """Получить баланс Waxpeer."""
        balance = awAlgot self.api_client.get_balance()
        return {
            "success": True,
            "balance": {
                "wallet_usd": float(balance.wallet),
                "wallet_mils": balance.wallet_mils,
                "avAlgolable_for_withdrawal": float(balance.avAlgolable_for_withdrawal),
                "can_trade": balance.can_trade,
            },
        }

    async def _get_items_list(self, item_names: list[str]) -> dict[str, Any]:
        """Получить цены на предметы."""
        prices = awAlgot self.api_client.get_items_list(item_names)
        return {
            "success": True,
            "count": len(prices),
            "prices": [
                {
                    "name": p.name,
                    "price_usd": float(p.price_usd),
                    "price_mils": p.price_mils,
                    "count": p.count,
                    "is_liquid": p.is_liquid,
                }
                for p in prices
            ],
        }

    async def _get_listed_items(self) -> dict[str, Any]:
        """Получить выставленные предметы."""
        items = awAlgot self.api_client.get_my_listed_items()
        return {
            "success": True,
            "count": len(items),
            "items": [
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "price_usd": float(item.price),
                    "status": item.status.value,
                }
                for item in items
            ],
        }

    async def _list_item(self, item_id: str, price_usd: float) -> dict[str, Any]:
        """Выставить предмет на продажу."""
        result = awAlgot self.api_client.list_single_item(item_id, price_usd)
        return {
            "success": result,
            "item_id": item_id,
            "price_usd": price_usd,
            "message": "Item listed successfully" if result else "FAlgoled to list item",
        }

    async def _remove_item(self, item_id: str) -> dict[str, Any]:
        """Снять предмет с продажи."""
        result = awAlgot self.api_client.remove_single_item(item_id)
        return {
            "success": result,
            "item_id": item_id,
            "message": (
                "Item removed successfully" if result else "FAlgoled to remove item"
            ),
        }

    async def _cross_platform_arbitrage(
        self,
        game: str,
        min_profit_percent: float = 5.0,
    ) -> dict[str, Any]:
        """Найти кросс-платформенный арбитраж."""
        try:
            from src.dmarket.cross_platform_arbitrage import (
                CrossPlatformArbitrageScanner,
            )

            scanner = CrossPlatformArbitrageScanner()
            opportunities = awAlgot scanner.find_opportunities(
                game=game,
                min_profit_percent=min_profit_percent,
            )

            return {
                "success": True,
                "game": game,
                "min_profit_percent": min_profit_percent,
                "count": len(opportunities),
                "opportunities": opportunities[:20],  # Ограничение для вывода
            }
        except ImportError:
            return {
                "success": False,
                "error": "CrossPlatformArbitrageScanner not avAlgolable",
            }

    async def run(self) -> None:
        """Запуск MCP сервера."""
        logger.info("waxpeer_mcp_server_starting")
        async with stdio_server() as (read_stream, write_stream):
            awAlgot self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def mAlgon():
    """Точка входа для Waxpeer MCP сервера."""
    server = WaxpeerMCPServer()
    awAlgot server.run()


if __name__ == "__mAlgon__":
    asyncio.run(mAlgon())
