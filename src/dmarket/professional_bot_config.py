"""Профессиональная конфигурация бота (BOT_ULTIMATE_V3).

Оптимизированные настройки для эффективного арбитража:
- AI Predictor: Защита от галлюцинаций с min_samples_leaf=5
- Smart Scanner: Cursor навигация + lockStatus фильтр
- Silent Mode: Логирование в файл вместо спама в Telegram
- Adaptive Limiter: Защита от 429 ошибки с экспоненциальным backoff
- Local Delta: Пропуск дубликатов для экономии CPU

Глобальные настройки обеспечивают баланс между скоростью и безопасностью ToS.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# ГЛОБАЛЬНЫЕ НАСТРОЙКИ БОТА (Config)
# =============================================================================

@dataclass
class ProfessionalBotConfig:
    """Профессиональные настройки бота для арбитража.

    Эти параметры обеспечивают баланс между скоростью и безопасностью ToS.
    """

    # === Настройки прибыли и ликвидности ===
    min_profit_pct: float = 0.05  # Минимум 5% чистой прибыли
    min_profit_usd: float = 0.50  # Минимум $0.50 абсолютной прибыли
    max_item_price: float = 100.0  # Максимальная цена предмета

    # === Lock Status (Трейд-бан) ===
    max_item_lock_days: int = 0  # 0 = берем только скины без трейд-бана
    lock_discount_per_day: float = 0.5  # % дисконта за каждый день блокировки
    max_lock_discount: float = 5.0  # Максимальный дисконт за lock (%)

    # === Навигация ===
    use_cursor_navigation: bool = True  # Использовать быстрые курсоры вместо offset
    items_per_page: int = 100  # Предметов на страницу
    max_pages_per_scan: int = 50  # Максимум страниц за один скан

    # === Silent Mode ===
    silent_mode: bool = True  # Писать в ТГ только о покупках
    log_to_file: bool = True  # Логировать в файл вместо консоли
    log_file_path: str = "logs/bot_trading.log"  # Путь к лог-файлу
    telegram_notify_on_buy: bool = True  # Уведомлять в TG о покупках
    telegram_notify_on_error: bool = True  # Уведомлять в TG об ошибках
    telegram_notify_interval_minutes: int = 30  # Минимальный интервал между сводками

    # === Rate Limiting ===
    enable_adaptive_limiter: bool = True  # Включить умный rate limiter
    base_request_delay: float = 0.5  # Базовая задержка между запросами (сек)
    max_requests_per_minute: int = 60  # Максимум запросов в минуту
    backoff_multiplier: float = 2.0  # Множитель для экспоненциального backoff
    max_backoff_seconds: float = 60.0  # Максимальная задержка backoff

    # === Local Delta (Дедупликация) ===
    enable_local_delta: bool = True  # Пропускать дубликаты
    delta_cache_ttl_seconds: int = 300  # TTL кэша дельты (5 минут)
    delta_hash_algorithm: str = "md5"  # Алгоритм хэширования (md5 быстрее)

    # === AI Predictor ===
    min_samples_leaf: int = 5  # Защита от галлюцинаций (переобучения)
    min_samples_for_prediction: int = 10  # Минимум данных для прогноза
    max_prediction_confidence: float = 0.95  # Максимальная уверенность (защита от overconfidence)
    use_ensemble_voting: bool = True  # Голосование ансамбля моделей

    # === Whitelist/Blacklist ===
    whitelist_priority_boost: float = 0.02  # Бонус к прибыли для whitelist (+2%)
    blacklist_strict: bool = True  # Строгий blacklist (никогда не покупать)

    # === Batch Requests ===
    use_batch_price_requests: bool = True  # Использовать batch endpoint
    batch_update_interval_seconds: int = 30  # Интервал обновления цен
    max_items_per_batch: int = 100  # Максимум предметов в одном batch

    # === Safety ===
    max_balance_percent_per_item: float = 0.25  # Максимум 25% баланса на один предмет
    max_balance_in_locked_items: float = 0.25  # Максимум 25% баланса в locked предметах
    dry_run: bool = True  # По умолчанию безопасный режим


# =============================================================================
# SILENT MODE - Логирование без спама
# =============================================================================

class SilentModeLogger:
    """Логгер для Silent Mode.

    В Silent Mode логи пишутся в файл, а в Telegram отправляются
    только важные события (покупки, ошибки).
    """

    def __init__(
        self,
        config: ProfessionalBotConfig,
        notifier: Any | None = None,
    ):
        """Инициализация логгера.

        Args:
            config: Конфигурация бота
            notifier: Telegram notifier (опционально)
        """
        self.config = config
        self.notifier = notifier
        self._last_summary_time: datetime | None = None
        self._pending_events: list[dict[str, Any]] = []
        self._setup_file_logger()

    def _setup_file_logger(self) -> None:
        """Настройка файлового логгера."""
        if not self.config.log_to_file:
            return

        # Создаем директорию для логов
        log_path = Path(self.config.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Настраиваем file handler
        self._file_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

        # Добавляем к root logger
        logging.getLogger().addHandler(self._file_handler)
        logger.info("Silent Mode: логирование в файл %s", log_path)

    def log_scan_result(
        self,
        items_scanned: int,
        opportunities_found: int,
        scan_time_ms: float,
    ) -> None:
        """Логирует результат сканирования (только в файл в Silent Mode).

        Args:
            items_scanned: Количество просканированных предметов
            opportunities_found: Найденных возможностей
            scan_time_ms: Время сканирования в мс
        """
        msg = (
            f"Scan complete: {items_scanned} items, "
            f"{opportunities_found} opportunities, {scan_time_ms:.0f}ms"
        )

        if self.config.silent_mode:
            logger.info(msg)  # Только в файл
        else:
            # В не-silent режиме можно отправить в TG
            self._pending_events.append({
                "type": "scan",
                "message": msg,
                "timestamp": datetime.now(UTC),
            })

    async def log_purchase(
        self,
        item_name: str,
        buy_price: float,
        expected_profit: float,
        profit_percent: float,
    ) -> None:
        """Логирует покупку (всегда отправляется в Telegram).

        Args:
            item_name: Название предмета
            buy_price: Цена покупки
            expected_profit: Ожидаемая прибыль
            profit_percent: Процент прибыли
        """
        msg = (
            f"✅ BOUGHT: {item_name}\n"
            f"Price: ${buy_price:.2f}\n"
            f"Expected profit: ${expected_profit:.2f} ({profit_percent:.1f}%)"
        )

        logger.info(msg)

        # В Telegram отправляем всегда
        if self.notifier and self.config.telegram_notify_on_buy:
            await self.notifier.send_message(msg, priority="high")

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        critical: bool = False,
    ) -> None:
        """Логирует ошибку.

        Args:
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            critical: Критическая ошибка
        """
        msg = f"❌ ERROR [{error_type}]: {error_message}"

        if critical:
            logger.error(msg)
        else:
            logger.warning(msg)

        # Критические ошибки всегда в Telegram
        if self.notifier and self.config.telegram_notify_on_error and critical:
            await self.notifier.send_message(msg, priority="critical")

    async def send_summary_if_needed(self) -> None:
        """Отправляет сводку, если прошло достаточно времени."""
        if not self.notifier or not self._pending_events:
            return

        now = datetime.now(UTC)
        interval = self.config.telegram_notify_interval_minutes

        # Проверяем, прошло ли достаточно времени
        if self._last_summary_time:
            minutes_passed = (now - self._last_summary_time).total_seconds() / 60
            if minutes_passed < interval:
                return

        # Формируем сводку
        summary = self._format_summary()
        await self.notifier.send_message(summary, priority="low")

        self._last_summary_time = now
        self._pending_events.clear()

    def _format_summary(self) -> str:
        """Форматирует сводку событий."""
        scans = [e for e in self._pending_events if e["type"] == "scan"]

        if not scans:
            return "📊 Нет новых событий"

        total_items = sum(e.get("items_scanned", 0) for e in scans)
        total_opportunities = sum(e.get("opportunities_found", 0) for e in scans)

        return (
            f"📊 Сводка за последние {self.config.telegram_notify_interval_minutes} мин:\n"
            f"• Сканирований: {len(scans)}\n"
            f"• Предметов: {total_items}\n"
            f"• Возможностей: {total_opportunities}"
        )


# =============================================================================
# LOCAL DELTA - Пропуск дубликатов
# =============================================================================

class LocalDeltaTracker:
    """Отслеживание изменений для пропуска дубликатов.

    Экономит CPU и API запросы, обрабатывая только изменившиеся предметы.
    """

    def __init__(self, config: ProfessionalBotConfig):
        """Инициализация трекера дельты.

        Args:
            config: Конфигурация бота
        """
        self.config = config
        self._cache: dict[str, tuple[str, float]] = {}  # item_id -> (hash, timestamp)
        self._stats = {
            "total_items": 0,
            "skipped_duplicates": 0,
            "processed_changes": 0,
        }

    def _compute_hash(self, item_data: dict[str, Any]) -> str:
        """Вычисляет хэш предмета.

        Args:
            item_data: Данные предмета

        Returns:
            Хэш строка
        """
        # Ключевые поля для сравнения
        key_fields = [
            str(item_data.get("price", {}).get("USD", 0)),
            str(item_data.get("suggestedPrice", {}).get("USD", 0)),
            str(item_data.get("lockStatus", 0)),
            str(item_data.get("discount", 0)),
        ]

        data_str = "|".join(key_fields)

        if self.config.delta_hash_algorithm == "md5":
            return hashlib.md5(data_str.encode(), usedforsecurity=False).hexdigest()[:16]  # noqa: S324
        return hashlib.sha256(data_str.encode(), usedforsecurity=False).hexdigest()[:16]

    def is_changed(self, item_id: str, item_data: dict[str, Any]) -> bool:
        """Проверяет, изменился ли предмет с последнего раза.

        Args:
            item_id: ID предмета
            item_data: Данные предмета

        Returns:
            True если предмет изменился или новый
        """
        if not self.config.enable_local_delta:
            return True  # Если отключено, всегда обрабатываем

        self._stats["total_items"] += 1

        new_hash = self._compute_hash(item_data)
        current_time = time.time()

        # Проверяем кэш
        if item_id in self._cache:
            old_hash, timestamp = self._cache[item_id]

            # Проверяем TTL
            if current_time - timestamp > self.config.delta_cache_ttl_seconds:
                # TTL истёк, считаем изменённым
                self._cache[item_id] = (new_hash, current_time)
                self._stats["processed_changes"] += 1
                return True

            # Сравниваем хэши
            if old_hash == new_hash:
                self._stats["skipped_duplicates"] += 1
                return False

        # Новый предмет или изменился
        self._cache[item_id] = (new_hash, current_time)
        self._stats["processed_changes"] += 1
        return True

    def cleanup_expired(self) -> int:
        """Очищает устаревшие записи из кэша.

        Returns:
            Количество удалённых записей
        """
        current_time = time.time()
        ttl = self.config.delta_cache_ttl_seconds

        expired = [
            item_id for item_id, (_, ts) in self._cache.items()
            if current_time - ts > ttl
        ]

        for item_id in expired:
            del self._cache[item_id]

        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику.

        Returns:
            Словарь со статистикой
        """
        total = self._stats["total_items"]
        skipped = self._stats["skipped_duplicates"]

        skip_rate = (skipped / total * 100) if total > 0 else 0.0

        return {
            **self._stats,
            "cache_size": len(self._cache),
            "skip_rate_percent": round(skip_rate, 1),
        }

    def reset_stats(self) -> None:
        """Сброс статистики."""
        self._stats = {
            "total_items": 0,
            "skipped_duplicates": 0,
            "processed_changes": 0,
        }


# =============================================================================
# ADAPTIVE RATE LIMITER - Защита от 429
# =============================================================================

class AdaptiveRateLimiter:
    """Адаптивный rate limiter с защитой от 429 ошибок.

    Автоматически увеличивает задержку при получении 429 и
    постепенно уменьшает при успешных запросах.
    """

    def __init__(self, config: ProfessionalBotConfig):
        """Инициализация rate limiter.

        Args:
            config: Конфигурация бота
        """
        self.config = config
        self._current_delay = config.base_request_delay
        self._consecutive_429s = 0
        self._consecutive_successes = 0
        self._last_request_time = 0.0
        self._total_requests = 0
        self._total_429s = 0

    async def wait_before_request(self) -> None:
        """Ожидание перед следующим запросом."""
        if not self.config.enable_adaptive_limiter:
            return

        current_time = time.time()
        elapsed = current_time - self._last_request_time

        # Если с последнего запроса прошло меньше текущей задержки
        if elapsed < self._current_delay:
            wait_time = self._current_delay - elapsed
            await self._async_sleep(wait_time)

        self._last_request_time = time.time()
        self._total_requests += 1

    async def _async_sleep(self, seconds: float) -> None:
        """Асинхронное ожидание.

        Args:
            seconds: Количество секунд
        """
        import asyncio
        await asyncio.sleep(seconds)

    def record_success(self) -> None:
        """Фиксирует успешный запрос."""
        self._consecutive_429s = 0
        self._consecutive_successes += 1

        # После 10 успешных запросов уменьшаем задержку
        if self._consecutive_successes >= 10:
            self._decrease_delay()
            self._consecutive_successes = 0

    def record_429_error(self, retry_after: int | None = None) -> float:
        """Фиксирует ошибку 429 и возвращает время ожидания.

        Args:
            retry_after: Значение из заголовка Retry-After

        Returns:
            Время ожидания в секундах
        """
        self._consecutive_successes = 0
        self._consecutive_429s += 1
        self._total_429s += 1

        # Экспоненциальное увеличение задержки
        self._increase_delay()

        # Если есть Retry-After, используем его
        if retry_after and retry_after > 0:
            return float(retry_after)

        return self._current_delay

    def _increase_delay(self) -> None:
        """Увеличивает задержку (exponential backoff)."""
        self._current_delay = min(
            self._current_delay * self.config.backoff_multiplier,
            self.config.max_backoff_seconds,
        )
        logger.warning(
            f"Rate limit: задержка увеличена до {self._current_delay:.1f}s "
            f"(429 ошибок подряд: {self._consecutive_429s})"
        )

    def _decrease_delay(self) -> None:
        """Уменьшает задержку после успешных запросов."""
        if self._current_delay > self.config.base_request_delay:
            self._current_delay = max(
                self._current_delay / self.config.backoff_multiplier,
                self.config.base_request_delay,
            )
            logger.info(
                f"Rate limit: задержка уменьшена до {self._current_delay:.1f}s"
            )

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику.

        Returns:
            Словарь со статистикой
        """
        return {
            "current_delay": round(self._current_delay, 2),
            "consecutive_429s": self._consecutive_429s,
            "consecutive_successes": self._consecutive_successes,
            "total_requests": self._total_requests,
            "total_429_errors": self._total_429s,
            "error_rate_percent": round(
                self._total_429s / max(self._total_requests, 1) * 100, 2
            ),
        }


# =============================================================================
# AI PREDICTOR SETTINGS - Защита от галлюцинаций
# =============================================================================

@dataclass
class AIProtectionSettings:
    """Настройки защиты AI от галлюцинаций и переобучения.

    min_samples_leaf=5 предотвращает модель от принятия решений
    на основе слишком малого количества примеров.
    """

    # === RandomForest/GradientBoosting настройки ===
    min_samples_leaf: int = 5  # Минимум примеров в листе
    min_samples_split: int = 10  # Минимум примеров для разделения
    max_depth: int = 10  # Максимальная глубина дерева (защита от переобучения)

    # === Валидация предсказаний ===
    min_samples_for_prediction: int = 10  # Минимум данных для прогноза
    max_prediction_confidence: float = 0.95  # Защита от overconfidence
    min_prediction_confidence: float = 0.3  # Минимальная уверенность

    # === Outlier detection ===
    outlier_std_threshold: float = 3.0  # Порог для выбросов (3 стандартных отклонения)
    max_price_change_percent: float = 50.0  # Максимальное изменение цены за раз

    # === Feature validation ===
    min_feature_importance: float = 0.01  # Минимальная важность признака
    max_feature_correlation: float = 0.95  # Максимальная корреляция между признаками

    def get_random_forest_params(self) -> dict[str, Any]:
        """Получить параметры для RandomForest.

        Returns:
            Словарь параметров
        """
        return {
            "min_samples_leaf": self.min_samples_leaf,
            "min_samples_split": self.min_samples_split,
            "max_depth": self.max_depth,
            "n_estimators": 100,
            "random_state": 42,
            "n_jobs": -1,
        }

    def get_gradient_boosting_params(self) -> dict[str, Any]:
        """Получить параметры для GradientBoosting.

        Returns:
            Словарь параметров
        """
        return {
            "min_samples_leaf": self.min_samples_leaf,
            "min_samples_split": self.min_samples_split,
            "max_depth": min(self.max_depth, 5),  # GB требует меньшую глубину
            "n_estimators": 100,
            "learning_rate": 0.1,
            "random_state": 42,
        }

    def validate_prediction(
        self,
        predicted_price: float,
        current_price: float,
        confidence: float,
    ) -> tuple[bool, str]:
        """Валидирует предсказание AI.

        Args:
            predicted_price: Предсказанная цена
            current_price: Текущая цена
            confidence: Уверенность модели

        Returns:
            (is_valid, reason)
        """
        # Проверка уверенности
        if confidence < self.min_prediction_confidence:
            return False, f"Confidence too low: {confidence:.2f}"

        if confidence > self.max_prediction_confidence:
            # Подозрительно высокая уверенность - может быть переобучение
            logger.warning(
                f"Suspiciously high confidence: {confidence:.2f}. "
                "Possible overfitting."
            )

        # Проверка изменения цены
        if current_price > 0:
            price_change_pct = abs(predicted_price - current_price) / current_price * 100

            if price_change_pct > self.max_price_change_percent:
                return False, f"Price change too large: {price_change_pct:.1f}%"

        return True, "OK"


# =============================================================================
# SMART SCANNER CONFIG - Умный сканер
# =============================================================================

@dataclass
class SmartScannerConfig:
    """Конфигурация умного сканера.

    Объединяет cursor навигацию, lockStatus фильтр и delta tracking.
    """

    # Navigation
    use_cursor: bool = True
    items_per_request: int = 100
    max_requests_per_scan: int = 50

    # Lock Status Filter
    max_lock_days: int = 0  # 0 = только без блокировки
    lock_discount_per_day: float = 0.5  # % дисконта за день

    # Delta Tracking
    enable_delta: bool = True
    delta_ttl_seconds: int = 300

    # Parallel Scanning
    enable_parallel: bool = True
    max_concurrent_requests: int = 3

    # Smart Filters
    min_profit_percent: float = 5.0
    min_liquidity_score: int = 50
    max_competition_level: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """Конвертирует в словарь.

        Returns:
            Словарь с настройками
        """
        return {
            "navigation": {
                "use_cursor": self.use_cursor,
                "items_per_request": self.items_per_request,
                "max_requests_per_scan": self.max_requests_per_scan,
            },
            "lock_filter": {
                "max_lock_days": self.max_lock_days,
                "discount_per_day": self.lock_discount_per_day,
            },
            "delta": {
                "enabled": self.enable_delta,
                "ttl_seconds": self.delta_ttl_seconds,
            },
            "parallel": {
                "enabled": self.enable_parallel,
                "max_concurrent": self.max_concurrent_requests,
            },
            "filters": {
                "min_profit_percent": self.min_profit_percent,
                "min_liquidity_score": self.min_liquidity_score,
                "max_competition_level": self.max_competition_level,
            },
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_professional_config(
    balance: float,
    risk_profile: str = "moderate",
) -> ProfessionalBotConfig:
    """Создает профессиональную конфигурацию на основе баланса.

    Args:
        balance: Текущий баланс в USD
        risk_profile: Профиль риска (conservative, moderate, aggressive)

    Returns:
        Настроенная конфигурация
    """
    config = ProfessionalBotConfig()

    # Адаптация к балансу
    if balance < 50:
        # Маленький баланс - консервативные настройки
        config.min_profit_pct = 0.10  # 10% минимальный профит
        config.max_item_price = balance * 0.5  # Макс 50% баланса на предмет
        config.max_item_lock_days = 0  # Только без блокировки
        config.max_balance_percent_per_item = 0.5
    elif balance < 200:
        # Средний баланс
        config.min_profit_pct = 0.07  # 7%
        config.max_item_price = balance * 0.3
        config.max_item_lock_days = 0
        config.max_balance_percent_per_item = 0.3
    elif balance < 1000:
        # Большой баланс
        config.min_profit_pct = 0.05  # 5%
        config.max_item_price = balance * 0.2
        config.max_item_lock_days = 3  # Можем позволить немного locked
        config.max_balance_percent_per_item = 0.2
    else:
        # Очень большой баланс
        config.min_profit_pct = 0.03  # 3%
        config.max_item_price = 200.0  # Абсолютный лимит
        config.max_item_lock_days = 7
        config.max_balance_percent_per_item = 0.1

    # Адаптация к профилю риска
    if risk_profile == "conservative":
        config.min_profit_pct *= 1.5
        config.max_item_lock_days = 0
        config.silent_mode = False  # Больше уведомлений
    elif risk_profile == "aggressive":
        config.min_profit_pct *= 0.7
        config.max_item_lock_days += 3
        config.max_balance_percent_per_item *= 1.2

    return config


def create_ai_protection_settings(strict: bool = True) -> AIProtectionSettings:
    """Создает настройки защиты AI.

    Args:
        strict: Использовать строгие настройки

    Returns:
        Настройки защиты
    """
    settings = AIProtectionSettings()

    if strict:
        settings.min_samples_leaf = 5
        settings.min_samples_split = 10
        settings.max_depth = 8
        settings.max_prediction_confidence = 0.9
        settings.max_price_change_percent = 30.0
    else:
        settings.min_samples_leaf = 3
        settings.min_samples_split = 5
        settings.max_depth = 12
        settings.max_prediction_confidence = 0.98
        settings.max_price_change_percent = 50.0

    return settings


def create_smart_scanner_config(
    for_small_balance: bool = True,
) -> SmartScannerConfig:
    """Создает конфигурацию умного сканера.

    Args:
        for_small_balance: Оптимизировать для маленького баланса

    Returns:
        Конфигурация сканера
    """
    config = SmartScannerConfig()

    if for_small_balance:
        config.max_lock_days = 0  # Только без блокировки
        config.min_profit_percent = 7.0  # Выше порог
        config.min_liquidity_score = 70  # Только ликвидные
        config.max_concurrent_requests = 2  # Меньше параллельных
    else:
        config.max_lock_days = 3  # Можем позволить locked
        config.min_profit_percent = 4.0
        config.min_liquidity_score = 40
        config.max_concurrent_requests = 5

    return config


# =============================================================================
# GLOBAL DEFAULT INSTANCES
# =============================================================================

# Дефолтная конфигурация (можно переопределить)
DEFAULT_BOT_CONFIG = ProfessionalBotConfig()
DEFAULT_AI_PROTECTION = AIProtectionSettings()
DEFAULT_SCANNER_CONFIG = SmartScannerConfig()
