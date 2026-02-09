"""Модуль проверки адекватности цен для защиты от аномальных покупок.

Этот модуль предоставляет механизмы для предотвращения покупок по завышенным ценам:
- Сравнение с исторической ценой (7 дней)
- Проверка отклонений от средней цены
- Логирование подозрительных операций
- Интеграция с системой уведомлений

Используется перед каждой покупкой для защиты от:
- Ошибок API
- Манипуляций ценами
- Устаревших данных
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PriceSanityCheckFailed(Exception):
    """Исключение при провале проверки адекватности цены."""

    def __init__(
        self,
        message: str,
        item_name: str,
        current_price: Decimal,
        average_price: Decimal | None = None,
        max_allowed_price: Decimal | None = None,
    ):
        self.message = message
        self.item_name = item_name
        self.current_price = current_price
        self.average_price = average_price
        self.max_allowed_price = max_allowed_price
        super().__init__(message)


class PriceSanityChecker:
    """Проверка адекватности цен перед покупкой."""

    # Константы для проверки
    MAX_PRICE_MULTIPLIER: float = 1.5  # Максимум 50% выше средней
    HISTORY_DAYS: int = 7  # Период анализа истории цен
    MIN_HISTORY_SAMPLES: int = 3  # Минимум сэмплов для расчета средней

    def __init__(
        self,
        database_manager: Any | None = None,
        notifier: Any | None = None,
    ):
        """Инициализация проверки цен.

        Args:
            database_manager: Менеджер БД для получения истории цен
            notifier: Сервис уведомлений для критических алертов
        """
        self.db = database_manager
        self.notifier = notifier
        self._enabled = True

    async def check_price_sanity(
        self,
        item_name: str,
        current_price: Decimal,
        game: str = "csgo",
    ) -> dict[str, Any]:
        """Проверить адекватность цены перед покупкой.

        Args:
            item_name: Название предмета
            current_price: Текущая цена покупки (USD)
            game: Игра (csgo, dota2, etc.)

        Returns:
            dict: Результат проверки:
                - passed (bool): Прошла ли проверка
                - reason (str): Причина провала (если не прошла)
                - average_price (Decimal): Средняя цена за период
                - max_allowed_price (Decimal): Максимальная разрешенная цена
                - price_deviation_percent (float): Отклонение от средней (%)

        Raises:
            PriceSanityCheckFailed: Если проверка не прошла
        """
        if not self._enabled:
            logger.warning(
                "price_sanity_check_disabled",
                item=item_name,
                price=float(current_price),
            )
            return {
                "passed": True,
                "reason": "Disabled",
            }

        try:
            # Получить историю цен за последние 7 дней
            history = await self._get_price_history(
                item_name=item_name,
                game=game,
                days=self.HISTORY_DAYS,
            )

            if not history or len(history) < self.MIN_HISTORY_SAMPLES:
                logger.warning(
                    "price_sanity_check_insufficient_history",
                    item=item_name,
                    price=float(current_price),
                    samples=len(history) if history else 0,
                    required=self.MIN_HISTORY_SAMPLES,
                )
                # Недостаточно данных - разрешаем покупку с предупреждением
                return {
                    "passed": True,
                    "reason": "Insufficient history (allowing purchase)",
                    "warning": True,
                }

            # Рассчитать среднюю цену
            avg_price = sum(h["price_usd"] for h in history) / len(history)
            avg_price_decimal = Decimal(str(avg_price))

            # Рассчитать максимальную разрешенную цену
            max_allowed = avg_price_decimal * Decimal(str(self.MAX_PRICE_MULTIPLIER))

            # Рассчитать отклонение
            deviation_percent = float(
                ((current_price - avg_price_decimal) / avg_price_decimal) * 100
            )

            logger.info(
                "price_sanity_check_analyzing",
                item=item_name,
                current_price=float(current_price),
                average_price=float(avg_price_decimal),
                max_allowed=float(max_allowed),
                deviation_percent=round(deviation_percent, 2),
                history_samples=len(history),
            )

            # Проверить превышение лимита
            if current_price > max_allowed:
                error_msg = (
                    f"Price sanity check FAILED for '{item_name}': "
                    f"Current price ${current_price:.2f} exceeds max allowed "
                    f"${max_allowed:.2f} (avg: ${avg_price_decimal:.2f}, "
                    f"+{deviation_percent:.1f}%)"
                )

                logger.critical(
                    "PRICE_SANITY_CHECK_FAILED",
                    item=item_name,
                    current_price=float(current_price),
                    average_price=float(avg_price_decimal),
                    max_allowed=float(max_allowed),
                    deviation_percent=round(deviation_percent, 2),
                    multiplier=self.MAX_PRICE_MULTIPLIER,
                )

                # Отправить критическое уведомление
                if self.notifier:
                    await self._send_critical_alert(
                        item_name=item_name,
                        current_price=current_price,
                        average_price=avg_price_decimal,
                        max_allowed=max_allowed,
                        deviation_percent=deviation_percent,
                    )

                # Выбросить исключение
                raise PriceSanityCheckFailed(
                    message=error_msg,
                    item_name=item_name,
                    current_price=current_price,
                    average_price=avg_price_decimal,
                    max_allowed_price=max_allowed,
                )

            # Проверка прошла успешно
            logger.info(
                "price_sanity_check_passed",
                item=item_name,
                current_price=float(current_price),
                average_price=float(avg_price_decimal),
                deviation_percent=round(deviation_percent, 2),
            )

            return {
                "passed": True,
                "average_price": avg_price_decimal,
                "max_allowed_price": max_allowed,
                "price_deviation_percent": deviation_percent,
                "history_samples": len(history),
            }

        except PriceSanityCheckFailed:
            # Пробросить дальше
            raise
        except Exception as e:
            logger.error(
                "price_sanity_check_error",
                item=item_name,
                price=float(current_price),
                error=str(e),
                exc_info=True,
            )
            # При ошибке проверки - блокируем покупку для безопасности
            raise PriceSanityCheckFailed(
                message=f"Price sanity check error: {e}",
                item_name=item_name,
                current_price=current_price,
            ) from e

    async def _get_price_history(
        self,
        item_name: str,
        game: str,
        days: int,
    ) -> list[dict[str, Any]]:
        """Получить историю цен из базы данных.

        Args:
            item_name: Название предмета
            game: Игра
            days: Количество дней истории

        Returns:
            list: Список записей с ценами:
                [{"price_usd": Decimal, "timestamp": datetime}, ...]
        """
        if not self.db:
            logger.warning(
                "price_history_unavailable_no_db",
                item=item_name,
            )
            return []

        try:
            # Рассчитать дату начала периода
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            # Запрос к БД через DatabaseManager
            # Предполагаем наличие метода get_price_history
            history = await self.db.get_price_history(
                item_name=item_name,
                game=game,
                start_date=cutoff_date,
            )

            logger.debug(
                "price_history_fetched",
                item=item_name,
                game=game,
                days=days,
                samples=len(history),
            )

            return history

        except AttributeError:
            # Метод get_price_history не реализован
            logger.warning(
                "price_history_method_not_implemented",
                item=item_name,
            )
            return []
        except Exception as e:
            logger.error(
                "price_history_fetch_error",
                item=item_name,
                game=game,
                error=str(e),
                exc_info=True,
            )
            return []

    async def _send_critical_alert(
        self,
        item_name: str,
        current_price: Decimal,
        average_price: Decimal,
        max_allowed: Decimal,
        deviation_percent: float,
    ) -> None:
        """Отправить критическое уведомление о проваленной проверке.

        Args:
            item_name: Название предмета
            current_price: Текущая цена
            average_price: Средняя цена
            max_allowed: Максимальная разрешенная цена
            deviation_percent: Отклонение в процентах
        """
        if not self.notifier:
            return

        try:
            alert_message = (
                "🚨 <b>КРИТИЧЕСКИЙ АЛЕРТ: Санитарная проверка цены</b>\n\n"
                f"❌ <b>Заблокирована покупка</b>\n"
                f"📦 Предмет: <code>{item_name}</code>\n\n"
                f"💵 Текущая цена: <b>${current_price:.2f}</b>\n"
                f"📊 Средняя (7д): ${average_price:.2f}\n"
                f"🚫 Макс. допустимая: ${max_allowed:.2f}\n"
                f"📈 Превышение: <b>+{deviation_percent:.1f}%</b>\n\n"
                f"⚠️ Возможные причины:\n"
                f"• Ошибка API\n"
                f"• Манипуляция ценой\n"
                f"• Устаревшие данные\n\n"
                f"✅ Покупка заблокирована автоматически"
            )

            await self.notifier.send_message(
                message=alert_message,
                parse_mode="HTML",
            )

            logger.info(
                "critical_alert_sent",
                item=item_name,
                price=float(current_price),
            )

        except Exception as e:
            logger.error(
                "failed_to_send_critical_alert",
                item=item_name,
                error=str(e),
                exc_info=True,
            )

    def disable(self) -> None:
        """Отключить проверку (для тестирования)."""
        self._enabled = False
        logger.warning("price_sanity_checker_disabled")

    def enable(self) -> None:
        """Включить проверку."""
        self._enabled = True
        logger.info("price_sanity_checker_enabled")

    @property
    def is_enabled(self) -> bool:
        """Проверить, включена ли проверка."""
        return self._enabled
