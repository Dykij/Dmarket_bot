"""Стандартизированные mock данные для тестов DMarket Bot.

Этот модуль предоставляет единый источник mock данных для всех тестов,
что обеспечивает консистентность и упрощает обслуживание тестов.

Usage:
    from tests.fixtures.mock_responses import (
        MockBalance,
        MockItem,
        MockTarget,
        create_mock_item,
        create_mock_balance_response,
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# =============================================================================
# КОНСТАНТЫ
# =============================================================================

# DMarket комиссия
DMARKET_COMMISSION = 0.07  # 7%

# Waxpeer комиссия
WAXPEER_COMMISSION = 0.06  # 6%

# Steam комиссия
STEAM_COMMISSION = 0.13  # 13% (Valve 5% + Publisher 10%)


# =============================================================================
# MOCK BALANCE
# =============================================================================


@dataclass
class MockBalance:
    """Mock данные баланса DMarket.

    DMarket возвращает баланс в центах (USD * 100).
    """

    usd_cents: int = 100000  # $1000.00 по умолчанию
    dmc_cents: int = 50000  # $500.00 DMC

    def to_dmarket_response(self) -> dict[str, Any]:
        """Формат ответа DMarket API /account/v1/balance."""
        return {
            "usd": {
                "amount": str(self.usd_cents),
                "currency": "USD",
            },
            "dmc": {
                "amount": str(self.dmc_cents),
                "currency": "DMC",
            },
        }

    def to_usd(self) -> float:
        """Возвращает баланс в долларах."""
        return self.usd_cents / 100

    @classmethod
    def from_usd(cls, usd: float, dmc: float = 0) -> MockBalance:
        """Создает MockBalance из долларов."""
        return cls(
            usd_cents=int(usd * 100),
            dmc_cents=int(dmc * 100),
        )


def create_mock_balance_response(
    usd: float = 1000.0,
    dmc: float = 500.0,
) -> dict[str, Any]:
    """Создает mock ответ баланса DMarket.

    Args:
        usd: Баланс в USD
        dmc: Баланс в DMC

    Returns:
        Dict в формате DMarket API
    """
    return MockBalance.from_usd(usd, dmc).to_dmarket_response()


# =============================================================================
# MOCK ITEMS
# =============================================================================


@dataclass
class MockItem:
    """Mock данные предмета DMarket.

    Цены в центах (USD * 100).
    """

    item_id: str = field(default_factory=lambda: f"item_{uuid.uuid4().hex[:8]}")
    title: str = "AK-47 | Redline (Field-Tested)"
    price_cents: int = 1500  # $15.00
    suggested_price_cents: int = 1800  # $18.00
    game_id: str = "a8db"  # CS2
    image: str = "https://example.com/item.png"
    exterior: str = "Field-Tested"
    rarity: str = "Classified"
    tradable: bool = True
    instant_price_cents: int | None = None

    def to_dmarket_response(self) -> dict[str, Any]:
        """Формат ответа DMarket API для предмета."""
        response = {
            "itemId": self.item_id,
            "title": self.title,
            "price": {"USD": str(self.price_cents)},
            "suggestedPrice": {"USD": str(self.suggested_price_cents)},
            "gameId": self.game_id,
            "image": self.image,
            "tradable": self.tradable,
            "extra": {
                "exterior": self.exterior,
                "rarity": self.rarity,
            },
        }
        if self.instant_price_cents:
            response["instantPrice"] = {"USD": str(self.instant_price_cents)}
        return response

    def to_price_usd(self) -> float:
        """Возвращает цену в долларах."""
        return self.price_cents / 100

    def to_suggested_price_usd(self) -> float:
        """Возвращает рекомендованную цену в долларах."""
        return self.suggested_price_cents / 100

    def calculate_profit(self, commission: float = DMARKET_COMMISSION) -> float:
        """Рассчитывает профит с учетом комиссии.

        Args:
            commission: Комиссия площадки (0.07 = 7%)

        Returns:
            Профит в USD
        """
        sell_price = self.suggested_price_cents / 100
        buy_price = self.price_cents / 100
        net_sell = sell_price * (1 - commission)
        return net_sell - buy_price

    def calculate_roi(self, commission: float = DMARKET_COMMISSION) -> float:
        """Рассчитывает ROI с учетом комиссии.

        Returns:
            ROI в процентах
        """
        profit = self.calculate_profit(commission)
        buy_price = self.price_cents / 100
        if buy_price == 0:
            return 0
        return (profit / buy_price) * 100


def create_mock_item(
    title: str = "AK-47 | Redline (Field-Tested)",
    price_usd: float = 15.0,
    suggested_price_usd: float | None = None,
    game: str = "csgo",
    exterior: str = "Field-Tested",
    tradable: bool = True,
    item_id: str | None = None,
) -> dict[str, Any]:
    """Создает mock предмет в формате DMarket API.

    Args:
        title: Название предмета
        price_usd: Цена в USD
        suggested_price_usd: Рекомендованная цена (по умолчанию price * 1.2)
        game: Игра (csgo, dota2, tf2, rust)
        exterior: Состояние (Factory New, Field-Tested, etc.)
        tradable: Можно ли торговать
        item_id: ID предмета (генерируется если не указан)

    Returns:
        Dict в формате DMarket API
    """
    if suggested_price_usd is None:
        suggested_price_usd = price_usd * 1.2

    game_ids = {
        "csgo": "a8db",
        "cs2": "a8db",
        "dota2": "9a92",
        "tf2": "tf2",
        "rust": "rust",
    }

    item = MockItem(
        item_id=item_id or f"item_{uuid.uuid4().hex[:8]}",
        title=title,
        price_cents=int(price_usd * 100),
        suggested_price_cents=int(suggested_price_usd * 100),
        game_id=game_ids.get(game.lower(), "a8db"),
        exterior=exterior,
        tradable=tradable,
    )
    return item.to_dmarket_response()


def create_mock_items_list(
    count: int = 10,
    base_price_usd: float = 10.0,
    price_spread: float = 0.2,
    game: str = "csgo",
) -> dict[str, Any]:
    """Создает список mock предметов в формате DMarket API.

    Args:
        count: Количество предметов
        base_price_usd: Базовая цена
        price_spread: Разброс цен (0.2 = ±20%)
        game: Игра

    Returns:
        Dict с objects и total
    """
    items = []
    for i in range(count):
        spread = 1 + (price_spread * (i / count - 0.5) * 2)
        price = base_price_usd * spread
        items.append(
            create_mock_item(
                title=f"Test Item {i + 1}",
                price_usd=price,
                game=game,
            )
        )

    return {
        "objects": items,
        "total": {"items": count},
    }


# =============================================================================
# MOCK TARGETS
# =============================================================================


@dataclass
class MockTarget:
    """Mock данные таргета (buy order) DMarket."""

    target_id: str = field(default_factory=lambda: f"target_{uuid.uuid4().hex[:8]}")
    title: str = "AK-47 | Redline (Field-Tested)"
    price_cents: int = 1400  # $14.00
    game_id: str = "a8db"
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dmarket_response(self) -> dict[str, Any]:
        """Формат ответа DMarket API для таргета."""
        return {
            "targetId": self.target_id,
            "title": self.title,
            "price": {"USD": str(self.price_cents)},
            "gameId": self.game_id,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
        }


def create_mock_target(
    title: str = "AK-47 | Redline (Field-Tested)",
    price_usd: float = 14.0,
    game: str = "csgo",
    status: str = "active",
    target_id: str | None = None,
) -> dict[str, Any]:
    """Создает mock таргет в формате DMarket API."""
    game_ids = {
        "csgo": "a8db",
        "cs2": "a8db",
        "dota2": "9a92",
        "tf2": "tf2",
        "rust": "rust",
    }

    target = MockTarget(
        target_id=target_id or f"target_{uuid.uuid4().hex[:8]}",
        title=title,
        price_cents=int(price_usd * 100),
        game_id=game_ids.get(game.lower(), "a8db"),
        status=status,
    )
    return target.to_dmarket_response()


# =============================================================================
# MOCK ARBITRAGE OPPORTUNITIES
# =============================================================================


def create_mock_arbitrage_opportunity(
    title: str = "AK-47 | Redline (Field-Tested)",
    buy_price_usd: float = 14.0,
    sell_price_usd: float = 17.0,
    game: str = "csgo",
    commission: float = DMARKET_COMMISSION,
) -> dict[str, Any]:
    """Создает mock арбитражную возможность.

    Args:
        title: Название предмета
        buy_price_usd: Цена покупки
        sell_price_usd: Цена продажи
        game: Игра
        commission: Комиссия

    Returns:
        Dict с данными арбитража
    """
    net_sell = sell_price_usd * (1 - commission)
    profit = net_sell - buy_price_usd
    roi = (profit / buy_price_usd) * 100 if buy_price_usd > 0 else 0

    return {
        "title": title,
        "game": game,
        "buyPrice": buy_price_usd,
        "sellPrice": sell_price_usd,
        "netSellPrice": round(net_sell, 2),
        "profit": round(profit, 2),
        "roi": round(roi, 2),
        "commission": commission,
    }


# =============================================================================
# MOCK WAXPEER DATA
# =============================================================================


def create_mock_waxpeer_item(
    title: str = "AK-47 | Redline (Field-Tested)",
    price_mils: int = 15000,  # $15.00 (1 USD = 1000 mils)
    steam_price_mils: int | None = None,
) -> dict[str, Any]:
    """Создает mock предмет Waxpeer.

    Waxpeer использует mils: 1 USD = 1000 mils.
    """
    return {
        "name": title,
        "price": price_mils,
        "steam_price": steam_price_mils or int(price_mils * 1.1),
        "item_id": f"waxpeer_{uuid.uuid4().hex[:8]}",
        "image": "https://example.com/item.png",
    }


def create_mock_waxpeer_balance(usd: float = 100.0) -> dict[str, Any]:
    """Создает mock баланс Waxpeer."""
    return {
        "success": True,
        "balance": int(usd * 1000),  # В mils
    }


# =============================================================================
# MOCK SALES HISTORY
# =============================================================================


def create_mock_sales_history(
    count: int = 30,
    base_price_usd: float = 15.0,
    volatility: float = 0.1,
) -> dict[str, Any]:
    """Создает mock историю продаж.

    Args:
        count: Количество продаж
        base_price_usd: Базовая цена
        volatility: Волатильность цен (0.1 = ±10%)

    Returns:
        Dict с историей продаж
    """
    import random

    sales = []
    now = datetime.now(tz=timezone.utc)

    for i in range(count):
        # Случайное отклонение от базовой цены
        price_factor = 1 + random.uniform(-volatility, volatility)
        price_cents = int(base_price_usd * 100 * price_factor)

        sale_time = now.replace(hour=now.hour - i) if i < 24 else now

        sales.append({
            "price": {"USD": str(price_cents)},
            "date": sale_time.isoformat(),
        })

    return {
        "sales": sales,
        "total": count,
    }


# =============================================================================
# MOCK API RESPONSES
# =============================================================================


class MockAPIResponses:
    """Класс для генерации типичных API ответов."""

    @staticmethod
    def success(data: Any = None) -> dict[str, Any]:
        """Успешный ответ API."""
        return {
            "success": True,
            "data": data or {},
        }

    @staticmethod
    def error(
        message: str = "Error occurred",
        code: str = "ERROR",
        status: int = 400,
    ) -> dict[str, Any]:
        """Ответ API с ошибкой."""
        return {
            "success": False,
            "error": {
                "message": message,
                "code": code,
            },
            "status": status,
        }

    @staticmethod
    def rate_limited(retry_after: int = 60) -> dict[str, Any]:
        """Ответ при превышении rate limit."""
        return {
            "success": False,
            "error": {
                "message": "Rate limit exceeded",
                "code": "RATE_LIMIT",
            },
            "retryAfter": retry_after,
            "status": 429,
        }

    @staticmethod
    def unauthorized() -> dict[str, Any]:
        """Ответ при ошибке авторизации."""
        return {
            "success": False,
            "error": {
                "message": "Invalid API key",
                "code": "UNAUTHORIZED",
            },
            "status": 401,
        }

    @staticmethod
    def not_found(item_id: str = "unknown") -> dict[str, Any]:
        """Ответ когда предмет не найден."""
        return {
            "success": False,
            "error": {
                "message": f"Item {item_id} not found",
                "code": "NOT_FOUND",
            },
            "status": 404,
        }
