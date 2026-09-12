from typing import Any, Protocol

class IDMarketAPI(Protocol):
    async def get_sales_history(self, game: str, title: str, period: str) -> dict[str, Any]:
        ...

    async def get_aggregated_prices_bulk(self, game: str, titles: list[str], limit: int = 1) -> dict[str, Any]:
        ...
