"""
DMarket MCP Server для AI интеграции.

Предоставляет набор инструментов для работы с DMarket API через Model Context Protocol.
"""

import asyncio
import json
from typing import Any

import structlog

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None
    stdio_server = None
    TextContent = None
    Tool = None

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.config import settings

logger = structlog.get_logger(__name__)


import os
import sys

# Windows IO encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class DMarketMCPServer:
    """MCP Server для DMarket API."""

    def __init__(self, api_client: DMarketAPI | None = None):
        """
        Инициализация MCP сервера.

        Args:
            api_client: Клиент DMarket API (опционально)

        Raises:
            RuntimeError: Если MCP модуль не установлен
        """
        if not MCP_AVAILABLE:
            raise RuntimeError(
                "MCP module is not installed. Install it with: pip install mcp"
            )

        self.server = Server("dmarket-bot")

        # Robust API key loading
        public_key = settings.dmarket.public_key or os.getenv("DMARKET_PUBLIC_KEY")
        secret_key = settings.dmarket.secret_key or os.getenv("DMARKET_SECRET_KEY")

        self.api_client = api_client or DMarketAPI(
            public_key=public_key,
            secret_key=secret_key,
        )
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Настройка обработчиков MCP."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Список доступных инструментов."""
            return [
                Tool(
                    name="get_balance",
                    description="Получить баланс пользователя на DMarket",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="get_market_items",
                    description="Получить список предметов на рынке",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "game": {
                                "type": "string",
                                "description": "Игра (csgo, dota2, rust, tf2)",
                                "enum": ["csgo", "dota2", "rust", "tf2"],
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Количество предметов (макс 100)",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                            },
                            "price_from": {
                                "type": "integer",
                                "description": "Минимальная цена в центах USD",
                                "minimum": 0,
                            },
                            "price_to": {
                                "type": "integer",
                                "description": "Максимальная цена в центах USD",
                                "minimum": 0,
                            },
                        },
                        "required": ["game"],
                    },
                ),
                Tool(
                    name="scan_arbitrage",
                    description="Сканировать арбитражные возможности",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "game": {
                                "type": "string",
                                "description": "Игра для сканирования",
                                "enum": ["csgo", "dota2", "rust", "tf2"],
                            },
                            "level": {
                                "type": "string",
                                "description": "Уровень арбитража",
                                "enum": [
                                    "boost",
                                    "standard",
                                    "medium",
                                    "advanced",
                                    "pro",
                                ],
                                "default": "standard",
                            },
                            "min_profit": {
                                "type": "number",
                                "description": "Минимальная прибыль в USD",
                                "default": 0.5,
                                "minimum": 0,
                            },
                        },
                        "required": ["game"],
                    },
                ),
                Tool(
                    name="get_item_details",
                    description="Получить детальную информацию о предмете",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "ID предмета на DMarket",
                            },
                        },
                        "required": ["item_id"],
                    },
                ),
                Tool(
                    name="create_target",
                    description="Создать таргет (buy order) на предмет",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "game": {
                                "type": "string",
                                "description": "Игра",
                                "enum": ["csgo", "dota2", "rust", "tf2"],
                            },
                            "title": {
                                "type": "string",
                                "description": "Название предмета",
                            },
                            "price": {
                                "type": "number",
                                "description": "Цена в USD",
                                "minimum": 0.01,
                            },
                            "amount": {
                                "type": "integer",
                                "description": "Количество предметов",
                                "default": 1,
                                "minimum": 1,
                            },
                        },
                        "required": ["game", "title", "price"],
                    },
                ),
                Tool(
                    name="get_targets",
                    description="Получить список активных таргетов",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Вызов инструмента."""
            try:
                logger.info("mcp_tool_called", tool=name, arguments=arguments)

                if name == "get_balance":
                    result = await self._get_balance()
                elif name == "get_market_items":
                    result = await self._get_market_items(**arguments)
                elif name == "scan_arbitrage":
                    result = await self._scan_arbitrage(**arguments)
                elif name == "get_item_details":
                    result = await self._get_item_details(**arguments)
                elif name == "create_target":
                    result = await self._create_target(**arguments)
                elif name == "get_targets":
                    result = await self._get_targets()
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2, ensure_ascii=False),
                    )
                ]

            except Exception as e:
                logger.error("mcp_tool_error", tool=name, error=str(e), exc_info=True)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": str(e), "tool": name}, ensure_ascii=False
                        ),
                    )
                ]

    async def _get_balance(self) -> dict[str, Any]:
        """Получить баланс."""
        balance = await self.api_client.get_balance()
        return {
            "success": True,
            "balance": balance,
        }

    async def _get_market_items(
        self,
        game: str,
        limit: int = 10,
        price_from: int | None = None,
        price_to: int | None = None,
    ) -> dict[str, Any]:
        """Получить предметы рынка."""
        items = await self.api_client.get_market_items(
            game=game,
            limit=limit,
            price_from=price_from,
            price_to=price_to,
        )
        return {
            "success": True,
            "game": game,
            "count": len(items.get("objects", [])),
            "items": items.get("objects", [])[:limit],
        }

    async def _scan_arbitrage(
        self,
        game: str,
        level: str = "standard",
        min_profit: float = 0.5,
    ) -> dict[str, Any]:
        """Сканировать арбитраж."""
        from src.dmarket.scanner.engine import ArbitrageScanner

        scanner = ArbitrageScanner(api_client=self.api_client)
        opportunities = await scanner.scan_level(level=level, game=game)

        # Фильтрация по минимальной прибыли
        filtered = [opp for opp in opportunities if opp.get("profit", 0) >= min_profit]

        return {
            "success": True,
            "game": game,
            "level": level,
            "min_profit": min_profit,
            "count": len(filtered),
            "opportunities": filtered[:20],  # Ограничение для вывода
        }

    async def _get_item_details(self, item_id: str) -> dict[str, Any]:
        """Получить детали предмета."""
        details = await self.api_client.get_item_by_id(item_id)
        return {
            "success": True,
            "item": details,
        }

    async def _create_target(
        self,
        game: str,
        title: str,
        price: float,
        amount: int = 1,
    ) -> dict[str, Any]:
        """Создать таргет."""
        from src.dmarket.targets import TargetManager

        target_manager = TargetManager(api_client=self.api_client)
        result = await target_manager.create_target(
            game=game,
            title=title,
            price=price,
            amount=amount,
        )

        return {
            "success": True,
            "target": result,
        }

    async def _get_targets(self) -> dict[str, Any]:
        """Получить список таргетов."""
        from src.dmarket.targets import TargetManager

        target_manager = TargetManager(api_client=self.api_client)
        targets = await target_manager.get_all_targets()

        return {
            "success": True,
            "count": len(targets),
            "targets": targets,
        }

    async def run(self) -> None:
        """Запуск MCP сервера."""
        logger.info("mcp_server_starting")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Точка входа для MCP сервера."""
    server = DMarketMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
