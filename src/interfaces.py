"""Protocol интерфейсы для Dependency Injection.

Этот модуль определяет абстрактные интерфейсы (Protocol) для основных
компонентов системы, что позволяет легко заменять реализации в тестах
и для разных окружений.

Example:
    >>> from src.interfaces import IDMarketAPI
    >>> def process_items(api: IDMarketAPI):
    ...     items = await api.get_market_items("csgo")
    ...     return items
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IDMarketAPI(Protocol):
    """Protocol интерфейс для DMarket API клиента.

    Определяет минимальный набор методов, необходимых для работы
    с DMarket API. Позволяет создавать mock-реализации для тестов.

    Example:
        >>> class MockAPI:
        ...     async def get_balance(self) -> dict[str, Any]:
        ...         return {"balance": 100.0}
        >>> mock = MockAPI()
        >>> isinstance(mock, IDMarketAPI)
        True
    """

    async def get_balance(self) -> dict[str, Any]:
        """Получить баланс аккаунта.

        Returns:
            Словарь с информацией о балансе:
            - balance: float - баланс в USD
            - usd: dict - детали баланса в USD
            - error: bool - флаг ошибки
        """
        ...

    async def get_market_items(
        self,
        game: str,
        limit: int = 100,
        offset: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Получить предметы с маркета.

        Args:
            game: Код игры (csgo, dota2, tf2, rust)
            limit: Максимальное количество предметов
            offset: Смещение для пагинации
            **kwargs: Дополнительные фильтры

        Returns:
            Словарь с предметами и метаданными
        """
        ...

    async def buy_item(self, item_id: str, price: float) -> dict[str, Any]:
        """Купить предмет.

        Args:
            item_id: ID предмета для покупки
            price: Цена покупки в USD

        Returns:
            Результат операции покупки
        """
        ...

    async def sell_item(
        self,
        asset_id: str,
        price: float,
    ) -> dict[str, Any]:
        """Выставить предмет на продажу.

        Args:
            asset_id: ID актива для продажи
            price: Цена продажи в USD

        Returns:
            Результат операции
        """
        ...

    async def create_targets(
        self,
        targets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Создать таргеты (buy orders).

        Args:
            targets: Список таргетов для создания

        Returns:
            Результат создания таргетов
        """
        ...

    async def get_user_targets(
        self,
        game_id: str | None = None,
    ) -> dict[str, Any]:
        """Получить активные таргеты пользователя.

        Args:
            game_id: Опциональный фильтр по игре

        Returns:
            Список активных таргетов
        """
        ...

    async def get_sales_history(
        self,
        game: str,
        title: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Получить историю продаж предмета.

        Args:
            game: Код игры
            title: Название предмета
            limit: Максимальное количество записей

        Returns:
            История продаж с ценами и датами
        """
        ...

    async def get_aggregated_prices_bulk(
        self,
        titles: list[str],
        game: str = "csgo",
    ) -> dict[str, Any]:
        """Получить агрегированные цены для нескольких предметов.

        Args:
            titles: Список названий предметов
            game: Код игры

        Returns:
            Агрегированные цены для каждого предмета
        """
        ...

    async def get_user_inventory(
        self,
        game_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить инвентарь пользователя.

        Args:
            game_id: Опциональный фильтр по игре
            limit: Максимальное количество предметов
            offset: Смещение для пагинации

        Returns:
            Список предметов в инвентаре
        """
        ...


@runtime_checkable
class ICache(Protocol):
    """Protocol интерфейс для кэша.

    Абстрактный интерфейс для кэширования данных.
    Поддерживает как in-memory, так и распределенные кэши (Redis).
    """

    async def get(self, key: str) -> Any | None:
        """Получить значение из кэша.

        Args:
            key: Ключ для поиска

        Returns:
            Значение или None если не найдено/устарело
        """
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Сохранить значение в кэш.

        Args:
            key: Ключ для хранения
            value: Значение для сохранения
            ttl: Время жизни в секундах (опционально)
        """
        ...

    async def delete(self, key: str) -> bool:
        """Удалить значение из кэша.

        Args:
            key: Ключ для удаления

        Returns:
            True если значение было удалено
        """
        ...

    async def clear(self, pattern: str | None = None) -> int:
        """Очистить кэш.

        Args:
            pattern: Паттерн для выборочной очистки (опционально)

        Returns:
            Количество удаленных записей
        """
        ...


@runtime_checkable
class IArbitrageScanner(Protocol):
    """Protocol интерфейс для сканера арбитража."""

    async def scan_game(
        self,
        game: str,
        level: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Сканировать игру на арбитражные возможности.

        Args:
            game: Код игры
            level: Уровень арбитража (boost, standard, medium, advanced, pro)
            max_results: Максимальное количество результатов

        Returns:
            Список найденных возможностей
        """
        ...

    async def find_opportunities(
        self,
        games: list[str] | None = None,
        levels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Найти арбитражные возможности.

        Args:
            games: Список игр для сканирования (или все)
            levels: Список уровней (или все)

        Returns:
            Список найденных возможностей
        """
        ...


@runtime_checkable
class ITargetManager(Protocol):
    """Protocol интерфейс для менеджера таргетов."""

    async def create_target(
        self,
        game: str,
        title: str,
        price: float,
        amount: int = 1,
        attrs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Создать таргет (buy order).

        Args:
            game: Код игры
            title: Название предмета
            price: Цена покупки в USD
            amount: Количество (макс: 100)
            attrs: Дополнительные атрибуты

        Returns:
            Результат создания
        """
        ...

    async def delete_targets(
        self,
        target_ids: list[str],
    ) -> dict[str, Any]:
        """Удалить таргеты.

        Args:
            target_ids: Список ID таргетов для удаления

        Returns:
            Результат удаления
        """
        ...

    async def get_active_targets(
        self,
        game: str | None = None,
    ) -> list[dict[str, Any]]:
        """Получить активные таргеты.

        Args:
            game: Опциональный фильтр по игре

        Returns:
            Список активных таргетов
        """
        ...


@runtime_checkable
class IDatabase(Protocol):
    """Protocol интерфейс для базы данных."""

    async def init_database(self) -> None:
        """Инициализировать базу данных и создать таблицы."""
        ...

    def get_async_session(self) -> Any:
        """Получить async session для работы с БД.

        Returns:
            AsyncSession или session factory
        """
        ...

    async def close(self) -> None:
        """Закрыть соединения с базой данных."""
        ...


__all__ = [
    "IArbitrageScanner",
    "ICache",
    "IDMarketAPI",
    "IDatabase",
    "ITargetManager",
]
