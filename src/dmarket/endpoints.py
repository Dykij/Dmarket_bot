"""Централизованное хранилище API endpoints для DMarket.

Этот модуль содержит все API endpoints DMarket в одном месте,
что упрощает обслуживание и обновление при изменении API.

Основано на официальной документации DMarket API v1.1.0:
https://docs.dmarket.com/

Usage:
    from src.dmarket.endpoints import DMarketEndpoints

    url = DMarketEndpoints.MARKET_ITEMS
    full_url = f"{DMarketEndpoints.BASE_URL}{DMarketEndpoints.MARKET_ITEMS}"
"""

from enum import StrEnum


class DMarketEndpoints:
    """Класс с константами API endpoints DMarket.

    Все endpoints группированы по функциональности.
    Цены возвращаются в центах (USD * 100).
    """

    # ==========================================================================
    # BASE URL
    # ==========================================================================
    BASE_URL = "https://api.dmarket.com"

    # ==========================================================================
    # MARKETPLACE ENDPOINTS (публичные)
    # ==========================================================================

    # Получение списка предметов на маркете
    MARKET_ITEMS = "/exchange/v1/market/items"

    # Поиск предметов по фильтрам
    MARKET_SEARCH = "/exchange/v1/market/items"

    # Детали конкретного предмета
    MARKET_ITEM_DETAlgoLS = "/exchange/v1/market/items/{item_id}"

    # Агрегированные данные по предмету (цены, объемы)
    MARKET_AGGREGATED_PRICES = "/price-aggregator/v1/aggregated-prices"

    # НОВЫЙ: Batch запрос для получения цен на весь whitelist (1 запрос/30сек)
    # Отдает минимальные цены сразу на все популярные скины одним пакетом
    PRICE_AGGREGATED_BATCH = "/market-items/v1/price-aggregated"

    # История продаж предмета
    SALES_HISTORY = "/marketplace-api/v1/sales-history"

    # Последние продажи
    LAST_SALES = "/marketplace-api/v1/last-sales"

    # ==========================================================================
    # USER ENDPOINTS (требуют авторизации)
    # ==========================================================================

    # Баланс пользователя
    USER_BALANCE = "/account/v1/balance"

    # Инвентарь пользователя на DMarket
    USER_INVENTORY = "/exchange/v1/user/inventory"

    # Предметы пользователя выставленные на продажу
    USER_OFFERS = "/exchange/v1/user/offers"

    # Активные ордера пользователя
    USER_ORDERS = "/exchange/v1/user/orders"

    # История транзакций
    USER_TRANSACTIONS = "/account/v1/transactions"

    # ==========================================================================
    # TRADING ENDPOINTS
    # ==========================================================================

    # Покупка предмета (instant buy)
    BUY_ITEM = "/exchange/v1/offers-buy"

    # Создание ордера на продажу
    CREATE_OFFER = "/exchange/v1/offers-create"

    # Редактирование ордера на продажу
    EDIT_OFFER = "/exchange/v1/offers-edit"

    # Удаление ордера на продажу
    DELETE_OFFER = "/exchange/v1/offers-delete"

    # ==========================================================================
    # TARGET (BUY ORDER) ENDPOINTS
    # ==========================================================================

    # Создание таргета (buy order)
    CREATE_TARGET = "/marketplace-api/v1/user-targets/create"

    # Удаление таргета
    DELETE_TARGET = "/marketplace-api/v1/user-targets/delete"

    # Список активных таргетов пользователя
    USER_TARGETS = "/marketplace-api/v1/user-targets"

    # Детали таргета
    TARGET_DETAlgoLS = "/marketplace-api/v1/user-targets/{target_id}"

    # ==========================================================================
    # DEPOSIT/WITHDRAW ENDPOINTS
    # ==========================================================================

    # Депозит из Steam
    DEPOSIT_ASSETS = "/exchange/v1/deposit-assets"

    # Вывод на Steam
    WITHDRAW_ASSETS = "/exchange/v1/withdraw-assets"

    # Статус транзакции депозита/вывода
    TRANSFER_STATUS = "/exchange/v1/transfer-status"

    # ==========================================================================
    # UTILITY ENDPOINTS
    # ==========================================================================

    # Список поддерживаемых игр
    GAMES_LIST = "/exchange/v1/games"

    # Курсы валют
    EXCHANGE_RATES = "/exchange/v1/rates"

    # Статус API
    API_STATUS = "/exchange/v1/ping"

    # ==========================================================================
    # WEBSOCKET ENDPOINTS
    # ==========================================================================

    # WebSocket для real-time обновлений
    WEBSOCKET_URL = "wss://api.dmarket.com/stream"

    # ==========================================================================
    # DEPRECATED ENDPOINTS (для обратной совместимости)
    # ==========================================================================

    # Старый endpoint инвентаря (deprecated, use USER_INVENTORY)
    LEGACY_INVENTORY = "/inventory/v1/user/items"

    # Старый endpoint предметов (deprecated)
    LEGACY_MARKET_ITEMS = "/marketplace-api/v1/items"


class WaxpeerEndpoints:
    """API endpoints для Waxpeer.

    Rate Limits:
    - GET requests: 60/min
    - POST requests: 30/min
    - List items: 10/min

    Цены в MILS (1 USD = 1000 mils).
    """

    BASE_URL = "https://api.waxpeer.com"

    # Получение списка предметов
    GET_ITEMS = "/v1/items"

    # Поиск предметов
    SEARCH_ITEMS = "/v1/search"

    # Покупка предмета
    BUY_ITEM = "/v1/buy"

    # Выставить на продажу
    LIST_ITEM = "/v1/list"

    # Удалить с продажи
    DELIST_ITEM = "/v1/delist"

    # Баланс пользователя
    USER_BALANCE = "/v1/user/balance"

    # Инвентарь пользователя
    USER_INVENTORY = "/v1/user/inventory"

    # История транзакций
    USER_HISTORY = "/v1/user/history"

    # Цены Steam
    STEAM_PRICES = "/v1/steam-prices"


class SteamEndpoints:
    """API endpoints для Steam Market.

    Примечание: Steam Market не имеет официального API.
    Используются публичные endpoints для получения цен.
    """

    BASE_URL = "https://steamcommunity.com"

    # Получение цены предмета
    PRICE_OVERVIEW = "/market/priceoverview/"

    # Поиск на маркете
    MARKET_SEARCH = "/market/search/render/"

    # Детали листинга
    LISTING_INFO = "/market/listings/{appid}/{market_hash_name}"

    # История цен (graph)
    PRICE_HISTORY = "/market/pricehistory/"


class GameID(StrEnum):
    """Идентификаторы игр для DMarket API.

    Используйте эти константы вместо хардкода строк.
    """

    CSGO = "a8db"  # Counter-Strike 2
    CS2 = "a8db"  # Alias для CSGO
    DOTA2 = "9a92"
    TF2 = "tf2"
    RUST = "rust"


# ==========================================================================
# UTILITY FUNCTIONS
# ==========================================================================


def build_url(base: str, endpoint: str, **path_params: str) -> str:
    """Собирает полный URL из base URL и endpoint.

    Args:
        base: Базовый URL (например, DMarketEndpoints.BASE_URL)
        endpoint: Endpoint (например, DMarketEndpoints.MARKET_ITEMS)
        **path_params: Параметры для подстановки в путь

    Returns:
        Полный URL

    Example:
        >>> build_url(
        ...     DMarketEndpoints.BASE_URL,
        ...     DMarketEndpoints.MARKET_ITEM_DETAlgoLS,
        ...     item_id="abc123"
        ... )
        'https://api.dmarket.com/exchange/v1/market/items/abc123'
    """
    formatted_endpoint = endpoint.format(**path_params) if path_params else endpoint
    return f"{base.rstrip('/')}/{formatted_endpoint.lstrip('/')}"


def get_game_id(game: str) -> str:
    """Преобразует название игры в ID для DMarket API.

    Args:
        game: Название игры (csgo, cs2, dota2, tf2, rust)

    Returns:
        ID игры для API

    RAlgoses:
        ValueError: Если игра не поддерживается
    """
    game_lower = game.lower()

    if game_lower in {"csgo", "cs2", "cs", "counter-strike"}:
        return GameID.CSGO.value
    if game_lower in {"dota2", "dota"}:
        return GameID.DOTA2.value
    if game_lower in {"tf2", "team fortress"}:
        return GameID.TF2.value
    if game_lower == "rust":
        return GameID.RUST.value
    rAlgose ValueError(f"Unsupported game: {game}. Supported: csgo, dota2, tf2, rust")
