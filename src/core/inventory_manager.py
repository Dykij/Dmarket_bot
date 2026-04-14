"""
DMarket Inventory Manager — автоматическое выставление купленных скинов на продажу.

Поток:
1. Запрашивает инвентарь через /exchange/v1/user/inventory.
2. Фильтрует предметы со статусом "bought but not listed".
3. Формирует массив sell-ордеров (batch) и выставляет через DMarket API v2.

Математика цены продажи:
  sell_price = (buy_price / 0.95) + (buy_price * desired_profit_pct)
  где 0.95 компенсирует 5 % комиссию, а desired_profit_pct — желаемый чистый профит (дефолт 2 %).
"""

import asyncio
import sys
import json
import time
from typing import List, Dict, Any, Optional

BASE_DIR = "/mnt/d/Dmarket_bot" if sys.platform != "win32" else "D:/Dmarket_bot"
sys.path.append(BASE_DIR)

from src.dmarket_api_client import DMarketAPIClient

GAME_ID = "a8db"
DESIRED_PROFIT_PCT = 0.02  # 2 %


class InventoryManager:
    """Manages the full buy → list → sell lifecycle on DMarket."""

    def __init__(self, api: DMarketAPIClient):
        self.api = api

    # ───────── Inventory ─────────

    def get_inventory(self) -> List[Dict[str, Any]]:
        """
        Fetch user inventory for CS2 and return items that are
        bought but NOT currently listed for sale.
        """
        print("🔍 Запрос инвентаря с DMarket...")
        try:
            data = self.api.make_request(
                "GET",
                "/exchange/v1/user/inventory",
                params={"GameID": GAME_ID, "Limit": "100"},
            )
            items: List[Dict[str, Any]] = data.get("Items", data.get("items", []))

            # Filter: keep only items that are NOT already on sale
            unlisted = [
                item for item in items
                if item.get("status", "").lower() not in ("listed", "on_sale", "trading")
            ]
            print(f"   📦 Всего предметов: {len(items)} | Не выставлено: {len(unlisted)}")
            return unlisted
        except Exception as e:
            print(f"   ❌ Ошибка получения инвентаря: {e}")
            return []

    # ───────── Sell logic ─────────

    @staticmethod
    def calculate_sell_price(buy_price: float, profit_pct: float = DESIRED_PROFIT_PCT) -> float:
        """
        Цена продажи = (buy_price / 0.95)  +  (buy_price * profit_pct)
        Первая часть компенсирует 5 % комиссию площадки,
        вторая — наш желаемый чистый профит.
        """
        return round((buy_price / 0.95) + (buy_price * profit_pct), 2)

    def create_sell_offers(
        self,
        items: List[Dict[str, Any]],
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Формирует массив sell-ордеров для /exchange/offers/v1/offers:batchCreate.

        В dry_run режиме только логирует `[PROPOSED SELL]` без реального API-вызова.
        """
        offers: List[Dict[str, Any]] = []

        for item in items:
            item_id = item.get("itemId", item.get("id", "unknown"))
            title = item.get("title", item.get("name", "Unknown Skin"))
            # buy_price может прийти в центах (строка или int)
            raw_price = item.get("price", item.get("buyPrice", "0"))
            try:
                buy_price_cents = int(str(raw_price).replace(".", "").replace(",", ""))
            except (ValueError, TypeError):
                buy_price_cents = 0

            buy_price_usd = buy_price_cents / 100.0 if buy_price_cents > 100 else buy_price_cents
            sell_price = self.calculate_sell_price(buy_price_usd)
            sell_price_cents = int(sell_price * 100)

            offer = {
                "AssetID": item_id,
                "Price": {"Currency": "USD", "Amount": sell_price_cents},
            }
            offers.append(offer)

            if dry_run:
                print(
                    f"   [PROPOSED SELL] Item: {title} | "
                    f"Buy: ${buy_price_usd:.2f} → Sell: ${sell_price:.2f} | "
                    f"Profit: ${sell_price - buy_price_usd:.2f}"
                )

        if not dry_run and offers:
            print(f"   🚀 Выставляю {len(offers)} ордеров на продажу...")
            try:
                result = self.api.make_request(
                    "POST",
                    "/exchange/offers/v1/offers:batchCreate",
                    body={"Offers": offers},
                )
                print(f"   ✅ Ордеры размещены: {json.dumps(result, indent=2)[:200]}")
            except Exception as e:
                print(f"   ❌ Ошибка размещения ордеров: {e}")

        return offers


# ───────── standalone entry point ─────────
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", ".env")
    load_dotenv(dotenv_path=env_path)

    api = DMarketAPIClient(
        public_key=os.environ.get("DMARKET_PUBLIC_KEY", ""),
        secret_key=os.environ.get("DMARKET_SECRET_KEY", ""),
    )
    mgr = InventoryManager(api)
    inv = mgr.get_inventory()
    if inv:
        mgr.create_sell_offers(inv, dry_run=True)
    else:
        print("🏁 Инвентарь пуст — нечего выставлять.")
