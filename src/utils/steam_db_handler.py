"""
Database handler для Steam API кэширования и арбитража.

Этот модуль обрабатывает:
- Кэширование цен Steam Market
- Сохранение истории арбитражных возможностей
- Управление настройками пользователя
- Blacklist предметов
"""

from datetime import datetime, timedelta
import logging
from pathlib import Path
import sqlite3


logger = logging.getLogger(__name__)


class SteamDatabaseHandler:
    """Обработчик БД для Steam API интеграции."""

    def __init__(self, db_path: str = "data/steam_cache.db"):
        """
        Инициализация обработчика БД.

        Args:
            db_path: Путь к файлу базы данных
        """
        # Создаем директорию если не существует
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Доступ к полям по имени
        self.create_tables()
        logger.info(f"Steam database initialized: {db_path}")

    def create_tables(self) -> None:
        """Создает все необходимые таблицы."""
        with self.conn:
            # Таблица кэша цен Steam
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS steam_cache (
                    market_hash_name TEXT PRIMARY KEY,
                    lowest_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    median_price REAL,
                    app_id INTEGER DEFAULT 730,
                    last_updated TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Индекс для быстрого поиска по времени обновления
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_steam_cache_updated
                ON steam_cache(last_updated)
            """)

            # Таблица истории арбитража
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS arbitrage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    dmarket_price REAL NOT NULL,
                    steam_price REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    volume INTEGER,
                    liquidity_status TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Индекс для быстрого поиска по времени
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_arbitrage_logs_timestamp
                ON arbitrage_logs(timestamp)
            """)

            # Таблица настроек пользователя
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    min_profit REAL DEFAULT 10.0,
                    min_volume INTEGER DEFAULT 50,
                    is_paused INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Инициализация настроек по умолчанию
            self.conn.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")

            # Таблица Blacklist (заблокированные предметы)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    market_hash_name TEXT PRIMARY KEY,
                    reason TEXT DEFAULT 'Manual',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        logger.info("All tables created successfully")

    # ==================== Steam Cache ====================

    def update_steam_price(
        self,
        name: str,
        price: float,
        volume: int,
        median_price: float | None = None,
        app_id: int = 730,
    ):
        """
        Обновляет или добавляет цену Steam в кэш.

        Args:
            name: Название предмета (market_hash_name)
            price: Цена (lowest_price)
            volume: Объем продаж за 24 часа
            median_price: Медианная цена (опционально)
            app_id: ID игры (730 = CS:GO/CS2)
        """
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO steam_cache
                (market_hash_name, lowest_price, volume, median_price, app_id, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, price, volume, median_price, app_id, datetime.now()),
            )
        logger.debug(f"Updated Steam price: {name} = ${price}")

    def get_steam_data(self, name: str) -> dict | None:
        """
        Получает данные о цене из кэша.

        Args:
            name: Название предмета

        Returns:
            Dict с данными о цене или None если не найдено
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT lowest_price, volume, median_price, last_updated, app_id
            FROM steam_cache
            WHERE market_hash_name = ?
            """,
            (name,),
        )

        row = cursor.fetchone()

        if row:
            return {
                "price": row["lowest_price"],
                "volume": row["volume"],
                "median_price": row["median_price"],
                "last_updated": datetime.fromisoformat(row["last_updated"])
                if isinstance(row["last_updated"], str)
                else row["last_updated"],
                "app_id": row["app_id"],
            }
        return None

    def is_cache_actual(self, last_updated: datetime, hours: int = 6) -> bool:
        """
        Проверяет, актуальны ли данные в кэше.

        Args:
            last_updated: Время последнего обновления
            hours: Количество часов актуальности

        Returns:
            True если данные актуальны
        """
        if not last_updated:
            return False
        return datetime.now() - last_updated < timedelta(hours=hours)

    def get_cache_stats(self) -> dict:
        """Получает статистику кэша."""
        cursor = self.conn.cursor()

        # Всего записей
        cursor.execute("SELECT COUNT(*) as total FROM steam_cache")
        total = cursor.fetchone()["total"]

        # Актуальных записей (< 6 часов)
        cursor.execute(
            """
            SELECT COUNT(*) as actual
            FROM steam_cache
            WHERE last_updated >= datetime('now', '-6 hours')
            """
        )
        actual = cursor.fetchone()["actual"]

        # Устаревших записей
        stale = total - actual

        return {"total": total, "actual": actual, "stale": stale}

    def clear_stale_cache(self, hours: int = 24) -> int:
        """
        Очищает устаревший кэш.

        Args:
            hours: Удалить записи старше N часов

        Returns:
            Количество удаленных записей
        """
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM steam_cache WHERE last_updated < ?",
                (cutoff_time,),
            )
            deleted = cursor.rowcount

        logger.info(f"Cleared {deleted} stale cache entries (older than {hours}h)")
        return deleted

    # ==================== Arbitrage Logs ====================

    def log_opportunity(
        self,
        name: str,
        dmarket_price: float,
        steam_price: float,
        profit: float,
        volume: int = 0,
        liquidity_status: str = "Unknown",
    ):
        """
        Записывает найденную арбитражную возможность.

        Args:
            name: Название предмета
            dmarket_price: Цена на DMarket
            steam_price: Цена в Steam
            profit: Процент прибыли
            volume: Объем продаж
            liquidity_status: Статус ликвидности
        """
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO arbitrage_logs
                (item_name, dmarket_price, steam_price, profit_pct, volume, liquidity_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, dmarket_price, steam_price, profit, volume, liquidity_status),
            )
        logger.debug(f"Logged arbitrage opportunity: {name} ({profit}%)")

    def get_daily_stats(self) -> dict:
        """Получает статистику за последние 24 часа."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) as count,
                AVG(profit_pct) as avg_profit,
                MAX(profit_pct) as max_profit,
                MIN(profit_pct) as min_profit
            FROM arbitrage_logs
            WHERE timestamp >= datetime('now', '-1 day')
            """
        )
        row = cursor.fetchone()

        return {
            "count": row["count"] or 0,
            "avg_profit": round(row["avg_profit"] or 0, 2),
            "max_profit": round(row["max_profit"] or 0, 2),
            "min_profit": round(row["min_profit"] or 0, 2),
        }

    def get_top_items_today(self, limit: int = 5) -> list[tuple]:
        """
        Получает топ предметов по профиту за сегодня.

        Args:
            limit: Количество предметов

        Returns:
            List of tuples (item_name, profit_pct, timestamp)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT item_name, profit_pct, timestamp
            FROM arbitrage_logs
            WHERE timestamp >= datetime('now', '-1 day')
            ORDER BY profit_pct DESC
            LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()

    # ==================== Settings ====================

    def get_settings(self) -> dict:
        """Получает настройки пользователя."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT min_profit, min_volume, is_paused FROM settings WHERE id = 1")
        row = cursor.fetchone()

        return {
            "min_profit": row["min_profit"],
            "min_volume": row["min_volume"],
            "is_paused": bool(row["is_paused"]),
        }

    def update_settings(
        self,
        min_profit: float | None = None,
        min_volume: int | None = None,
        is_paused: bool | None = None,
    ):
        """
        Обновляет настройки пользователя.

        Args:
            min_profit: Минимальный процент прибыли
            min_volume: Минимальный объем продаж
            is_paused: Флаг паузы
        """
        updates = []
        params = []

        if min_profit is not None:
            updates.append("min_profit = ?")
            params.append(min_profit)

        if min_volume is not None:
            updates.append("min_volume = ?")
            params.append(min_volume)

        if is_paused is not None:
            updates.append("is_paused = ?")
            params.append(int(is_paused))

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now())

            with self.conn:
                self.conn.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = 1", params)  # noqa: S608 nosec B608

            logger.info(f"Updated settings: {updates}")

    # ==================== Blacklist ====================

    def add_to_blacklist(self, name: str, reason: str = "Manual"):
        """
        Добавляет предмет в черный список.

        Args:
            name: Название предмета
            reason: Причина добавления
        """
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO blacklist (market_hash_name, reason) VALUES (?, ?)",
                (name, reason),
            )
        logger.info(f"Added to blacklist: {name} (reason: {reason})")

    def is_blacklisted(self, name: str) -> bool:
        """
        Проверяет, находится ли предмет в черном списке.

        Args:
            name: Название предмета

        Returns:
            True если предмет в blacklist
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM blacklist WHERE market_hash_name = ?", (name,))
        return cursor.fetchone() is not None

    def remove_from_blacklist(self, name: str):
        """Удаляет предмет из черного списка."""
        with self.conn:
            cursor = self.conn.execute("DELETE FROM blacklist WHERE market_hash_name = ?", (name,))
            deleted = cursor.rowcount

        if deleted:
            logger.info(f"Removed from blacklist: {name}")
        return deleted > 0

    def get_blacklist(self) -> list[tuple]:
        """Получает весь черный список."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT market_hash_name, reason, added_at FROM blacklist ORDER BY added_at DESC"
        )
        return cursor.fetchall()

    def clear_blacklist(self):
        """Очищает весь черный список."""
        with self.conn:
            cursor = self.conn.execute("DELETE FROM blacklist")
            deleted = cursor.rowcount

        logger.info(f"Cleared blacklist: {deleted} items removed")
        return deleted

    # ==================== Utility ====================

    def close(self) -> None:
        """Закрывает соединение с БД."""
        self.conn.close()
        logger.info("Database connection closed")

    def __enter__(self) -> "SteamDatabaseHandler":
        """Context manager support."""
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None
    ) -> None:
        """Context manager support."""
        self.close()


# Singleton instance
_db_instance = None


def get_steam_db() -> SteamDatabaseHandler:
    """Получает singleton instance базы данных."""
    global _db_instance
    if _db_instance is None:
        _db_instance = SteamDatabaseHandler()
    return _db_instance
