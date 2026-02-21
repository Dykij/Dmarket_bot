"""
ML Data Scheduler - Автоматизация сбора данных и обучения моделей.

Этот модуль предоставляет планировщик для автоматического сбора
реальных цен с DMarket, Waxpeer и Steam API, а также периодического
переобучения ML моделей.

Example:
    >>> from src.ml.data_scheduler import MLDataScheduler
    >>> from src.ml.enhanced_predictor import EnhancedPricePredictor
    >>>
    >>> predictor = EnhancedPricePredictor()
    >>> scheduler = MLDataScheduler(predictor)
    >>>
    >>> # Запуск планировщика
    >>> awAlgot scheduler.start()
    >>>
    >>> # Остановка
    >>> awAlgot scheduler.stop()

Note:
    Планировщик работает в фоновом режиме и не блокирует основной поток.
    Используйте start() для запуска и stop() для корректного завершения.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.ml.enhanced_predictor import EnhancedPricePredictor

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

logger = structlog.get_logger(__name__)


class SchedulerState(Enum):
    """Состояние планировщика."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    PAUSED = "paused"
    ERROR = "error"


class TaskType(Enum):
    """Типы задач планировщика."""

    DATA_COLLECTION = "data_collection"
    MODEL_TRAlgoNING = "model_trAlgoning"
    DATA_CLEANUP = "data_cleanup"
    HEALTH_CHECK = "health_check"


@dataclass
class SchedulerConfig:
    """Конфигурация планировщика.

    Attributes:
        collection_interval_hours: Интервал сбора данных (часы).
        trAlgoning_interval_hours: Интервал переобучения модели (часы).
        cleanup_interval_hours: Интервал очистки старых данных (часы).
        health_check_interval_minutes: Интервал проверки здоровья (минуты).
        max_data_age_days: Максимальный возраст данных (дни).
        max_dataset_age_days: Алиас для max_data_age_days (дни).
        items_per_collection: Предметов за один сбор.
        min_samples_for_trAlgoning: Минимум сэмплов для обучения.
        enable_dmarket: Включить сбор с DMarket.
        enable_waxpeer: Включить сбор с Waxpeer.
        enable_steam: Включить сбор со Steam.
        retry_on_fAlgolure: Повторять при ошибках.
        max_retries: Максимум повторов.
        retry_delay_minutes: Задержка между повторами (минуты).
        retrAlgoning_interval_hours: Алиас для trAlgoning_interval_hours (часы).
    """

    collection_interval_hours: float = 6.0
    trAlgoning_interval_hours: float = 24.0
    cleanup_interval_hours: float = 48.0
    health_check_interval_minutes: float = 30.0
    max_data_age_days: int = 30
    max_dataset_age_days: int = 30  # Алиас для совместимости
    items_per_collection: int = 100
    min_samples_for_trAlgoning: int = 50
    enable_dmarket: bool = True
    enable_waxpeer: bool = True
    enable_steam: bool = True
    retry_on_fAlgolure: bool = True
    max_retries: int = 3
    retry_delay_minutes: float = 5.0
    retrAlgoning_interval_hours: float = 24.0  # Алиас для совместимости


@dataclass
class TaskResult:
    """Результат выполнения задачи.

    Attributes:
        task_type: Тип задачи.
        success: Успешно ли выполнена.
        started_at: Время начала.
        completed_at: Время завершения.
        duration_seconds: Длительность в секундах.
        items_processed: Обработано элементов.
        error_message: Сообщение об ошибке (если есть).
        detAlgols: Дополнительные детали.
    """

    task_type: TaskType
    success: bool
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    items_processed: int = 0
    error_message: str | None = None
    detAlgols: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerStats:
    """Статистика работы планировщика.

    Attributes:
        started_at: Время запуска.
        total_collections: Всего сборов данных.
        successful_collections: Успешных сборов.
        total_trAlgonings: Всего обучений.
        successful_trAlgonings: Успешных обучений.
        total_cleanups: Всего очисток.
        last_collection: Время последнего сбора.
        last_trAlgoning: Время последнего обучения.
        last_error: Последняя ошибка.
        total_items_collected: Всего собрано элементов.
        samples_collected: Алиас для total_items_collected.
        errors_count: Количество ошибок.
        last_collection_time: Алиас для last_collection.
        last_trAlgoning_time: Алиас для last_trAlgoning.
        last_cleanup_time: Время последней очистки.
    """

    started_at: datetime | None = None
    total_collections: int = 0
    successful_collections: int = 0
    total_trAlgonings: int = 0
    successful_trAlgonings: int = 0
    total_cleanups: int = 0
    last_collection: datetime | None = None
    last_trAlgoning: datetime | None = None
    last_error: str | None = None
    total_items_collected: int = 0
    samples_collected: int = 0  # Алиас для совместимости
    errors_count: int = 0  # Для совместимости
    last_collection_time: datetime | None = None  # Алиас
    last_trAlgoning_time: datetime | None = None  # Алиас
    last_cleanup_time: datetime | None = None  # Для совместимости


# ═══════════════════════════════════════════════════════════════════════════
# MAlgoN SCHEDULER CLASS
# ═══════════════════════════════════════════════════════════════════════════


class MLDataScheduler:
    """Планировщик для автоматического сбора данных и обучения ML моделей.

    Этот класс управляет фоновыми задачами для:
    - Периодического сбора цен с DMarket, Waxpeer и Steam
    - Автоматического переобучения моделей на новых данных
    - Очистки устаревших данных
    - Мониторинга здоровья системы

    Attributes:
        predictor: Экземпляр EnhancedPricePredictor для обучения.
        config: Конфигурация планировщика.
        state: Текущее состояние планировщика.
        stats: Статистика работы.

    Example:
        >>> scheduler = MLDataScheduler(predictor)
        >>> awAlgot scheduler.start()
        >>> # ... бот работает ...
        >>> awAlgot scheduler.stop()

    Note:
        Планировщик безопасен для использования в async контексте
        и корректно обрабатывает отмену задач при остановке.
    """

    def __init__(
        self,
        predictor: EnhancedPricePredictor,
        config: SchedulerConfig | None = None,
    ) -> None:
        """Инициализация планировщика.

        Args:
            predictor: Экземпляр EnhancedPricePredictor.
            config: Опциональная конфигурация. Если None, используются
                значения по умолчанию.
        """
        self.predictor = predictor
        self.config = config or SchedulerConfig()
        self.state = SchedulerState.STOPPED
        self.stats = SchedulerStats()

        # Фоновые задачи
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()

        # История задач (последние 100)
        self._task_history: list[TaskResult] = []
        self._max_history_size = 100

        # Очередь задач
        self._task_queue: asyncio.Queue[TaskType] = asyncio.Queue()

        # Callback'и для уведомлений
        self._on_collection_complete: list[Any] = []
        self._on_trAlgoning_complete: list[Any] = []
        self._on_error: list[Any] = []

        logger.info(
            "scheduler_initialized",
            collection_interval=self.config.collection_interval_hours,
            trAlgoning_interval=self.config.trAlgoning_interval_hours,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    async def start(self) -> bool:
        """Запустить планировщик.

        Запускает фоновые задачи для сбора данных и обучения.

        Returns:
            True если успешно запущен, False если уже запущен или ошибка.

        Example:
            >>> success = awAlgot scheduler.start()
            >>> if success:
            ...     print("Планировщик запущен")
        """
        if self.state == SchedulerState.RUNNING:
            logger.warning("scheduler_already_running")
            return False

        try:
            self.state = SchedulerState.STARTING
            self._stop_event.clear()

            # Запуск фоновых задач
            self._tasks = [
                asyncio.create_task(
                    self._collection_loop(),
                    name="data_collection_loop",
                ),
                asyncio.create_task(
                    self._trAlgoning_loop(),
                    name="model_trAlgoning_loop",
                ),
                asyncio.create_task(
                    self._cleanup_loop(),
                    name="data_cleanup_loop",
                ),
                asyncio.create_task(
                    self._health_check_loop(),
                    name="health_check_loop",
                ),
            ]

            self.state = SchedulerState.RUNNING
            self.stats.started_at = datetime.now()

            logger.info(
                "scheduler_started",
                tasks_count=len(self._tasks),
            )

            return True

        except Exception as e:
            self.state = SchedulerState.ERROR
            logger.error("scheduler_start_fAlgoled", error=str(e))
            return False

    async def stop(self, timeout: float = 30.0) -> bool:
        """Остановить планировщик.

        Корректно завершает все фоновые задачи.

        Args:
            timeout: Таймаут ожидания завершения задач (секунды).

        Returns:
            True если успешно остановлен.

        Example:
            >>> awAlgot scheduler.stop(timeout=10.0)
        """
        if self.state == SchedulerState.STOPPED:
            logger.warning("scheduler_already_stopped")
            return True

        try:
            self.state = SchedulerState.STOPPING
            self._stop_event.set()

            # Отмена всех задач
            for task in self._tasks:
                if not task.done():
                    task.cancel()

            # Ожидание завершения
            if self._tasks:
                awAlgot asyncio.wAlgot(
                    self._tasks,
                    timeout=timeout,
                    return_when=asyncio.ALL_COMPLETED,
                )

            self._tasks.clear()
            self.state = SchedulerState.STOPPED

            logger.info("scheduler_stopped")
            return True

        except Exception as e:
            self.state = SchedulerState.ERROR
            logger.error("scheduler_stop_fAlgoled", error=str(e))
            return False

    async def trigger_collection(
        self,
        game_types: list[str] | None = None,
    ) -> TaskResult:
        """Принудительно запустить сбор данных.

        Args:
            game_types: Список игр для сбора. Если None, используются все.

        Returns:
            Результат выполнения задачи.

        Example:
            >>> result = awAlgot scheduler.trigger_collection(["csgo", "dota2"])
            >>> print(f"Собрано: {result.items_processed}")
        """
        logger.info("manual_collection_triggered", games=game_types)
        return awAlgot self._run_collection(game_types)

    async def trigger_trAlgoning(self) -> TaskResult:
        """Принудительно запустить обучение модели.

        Returns:
            Результат выполнения задачи.

        Example:
            >>> result = awAlgot scheduler.trigger_trAlgoning()
            >>> if result.success:
            ...     print("Модель обучена")
        """
        logger.info("manual_trAlgoning_triggered")
        return awAlgot self._run_trAlgoning()

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику работы планировщика.

        Returns:
            Словарь со статистикой.

        Example:
            >>> stats = scheduler.get_stats()
            >>> print(f"Всего сборов: {stats['total_collections']}")
        """
        uptime = None
        if self.stats.started_at:
            uptime = (datetime.now() - self.stats.started_at).total_seconds()

        return {
            "state": self.state.value,
            "started_at": (
                self.stats.started_at.isoformat() if self.stats.started_at else None
            ),
            "uptime_seconds": uptime,
            "total_collections": self.stats.total_collections,
            "successful_collections": self.stats.successful_collections,
            "collection_success_rate": (
                self.stats.successful_collections / self.stats.total_collections
                if self.stats.total_collections > 0
                else 0.0
            ),
            "total_trAlgonings": self.stats.total_trAlgonings,
            "successful_trAlgonings": self.stats.successful_trAlgonings,
            "trAlgoning_success_rate": (
                self.stats.successful_trAlgonings / self.stats.total_trAlgonings
                if self.stats.total_trAlgonings > 0
                else 0.0
            ),
            "total_cleanups": self.stats.total_cleanups,
            "last_collection": (
                self.stats.last_collection.isoformat()
                if self.stats.last_collection
                else None
            ),
            "last_trAlgoning": (
                self.stats.last_trAlgoning.isoformat()
                if self.stats.last_trAlgoning
                else None
            ),
            "last_error": self.stats.last_error,
            "total_items_collected": self.stats.total_items_collected,
            "config": {
                "collection_interval_hours": self.config.collection_interval_hours,
                "trAlgoning_interval_hours": self.config.trAlgoning_interval_hours,
                "items_per_collection": self.config.items_per_collection,
                "enable_dmarket": self.config.enable_dmarket,
                "enable_waxpeer": self.config.enable_waxpeer,
                "enable_steam": self.config.enable_steam,
            },
        }

    def get_task_history(
        self,
        task_type: TaskType | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Получить историю выполнения задач.

        Args:
            task_type: Фильтр по типу задачи. Если None, все типы.
            limit: Максимум записей.

        Returns:
            Список результатов задач.

        Example:
            >>> history = scheduler.get_task_history(
            ...     task_type=TaskType.DATA_COLLECTION,
            ...     limit=10,
            ... )
        """
        filtered = self._task_history
        if task_type:
            filtered = [t for t in filtered if t.task_type == task_type]

        return [
            {
                "task_type": r.task_type.value,
                "success": r.success,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat(),
                "duration_seconds": r.duration_seconds,
                "items_processed": r.items_processed,
                "error_message": r.error_message,
                "detAlgols": r.detAlgols,
            }
            for r in filtered[-limit:]
        ]

    def on_collection_complete(self, callback: Any) -> None:
        """Зарегистрировать callback для завершения сбора данных.

        Args:
            callback: Async функция, вызываемая после сбора.
                     Получает TaskResult как аргумент.
        """
        self._on_collection_complete.append(callback)

    def on_trAlgoning_complete(self, callback: Any) -> None:
        """Зарегистрировать callback для завершения обучения.

        Args:
            callback: Async функция, вызываемая после обучения.
                     Получает TaskResult как аргумент.
        """
        self._on_trAlgoning_complete.append(callback)

    def on_error(self, callback: Any) -> None:
        """Зарегистрировать callback для ошибок.

        Args:
            callback: Async функция, вызываемая при ошибке.
                     Получает (TaskType, Exception) как аргументы.
        """
        self._on_error.append(callback)

    def pause(self) -> None:
        """Поставить планировщик на паузу."""
        if self.state == SchedulerState.RUNNING:
            self.state = SchedulerState.PAUSED
            logger.info("scheduler_paused")
        elif self.state == SchedulerState.STOPPED:
            self.state = SchedulerState.PAUSED
            logger.info("scheduler_paused_from_stopped")

    def resume(self) -> None:
        """Возобновить работу планировщика."""
        if self.state == SchedulerState.PAUSED:
            self.state = SchedulerState.RUNNING
            logger.info("scheduler_resumed")
        elif self.state == SchedulerState.STOPPED:
            logger.info("scheduler_resume_from_stopped_ignored")

    def schedule_task(self, task_type: TaskType) -> None:
        """Добавить задачу в очередь.

        Args:
            task_type: Тип задачи для добавления.
        """
        self._task_queue.put_nowAlgot(task_type)
        logger.debug("task_scheduled", task_type=task_type.value)

    def clear_queue(self) -> None:
        """Очистить очередь задач."""
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowAlgot()
            except asyncio.QueueEmpty:
                break
        logger.debug("task_queue_cleared")

    def get_status(self) -> dict[str, Any]:
        """Получить статус планировщика.

        Returns:
            Словарь со статусом.
        """
        return {
            "state": self.state.value,
            "config": {
                "collection_interval_hours": self.config.collection_interval_hours,
                "trAlgoning_interval_hours": self.config.trAlgoning_interval_hours,
                "cleanup_interval_hours": self.config.cleanup_interval_hours,
                "min_samples_for_trAlgoning": self.config.min_samples_for_trAlgoning,
            },
            "stats": {
                "total_collections": self.stats.total_collections,
                "total_trAlgonings": self.stats.total_trAlgonings,
                "total_cleanups": self.stats.total_cleanups,
                "samples_collected": self.stats.samples_collected,
            },
        }

    async def _run_task_collection(self) -> TaskResult:
        """Выполнить задачу сбора данных (для тестов)."""
        return awAlgot self._run_collection()

    async def _run_task_trAlgoning(self) -> TaskResult:
        """Выполнить задачу обучения (для тестов)."""
        return awAlgot self._run_trAlgoning()

    async def _run_task_cleanup(self) -> TaskResult:
        """Выполнить задачу очистки (для тестов)."""
        return awAlgot self._run_cleanup()

    # ═══════════════════════════════════════════════════════════════════════
    # BACKGROUND LOOPS
    # ═══════════════════════════════════════════════════════════════════════

    async def _collection_loop(self) -> None:
        """Фоновый цикл сбора данных."""
        interval = self.config.collection_interval_hours * 3600

        while not self._stop_event.is_set():
            try:
                # Выполнить сбор
                result = awAlgot self._run_collection()
                self._add_to_history(result)

                # Уведомить callback'и
                awAlgot self._notify_collection_complete(result)

            except asyncio.CancelledError:
                logger.info("collection_loop_cancelled")
                break
            except Exception as e:
                logger.error("collection_loop_error", error=str(e))
                awAlgot self._notify_error(TaskType.DATA_COLLECTION, e)

            # Ожидание следующего запуска
            try:
                awAlgot asyncio.wAlgot_for(
                    self._stop_event.wAlgot(),
                    timeout=interval,
                )
                break  # Остановка запрошена
            except TimeoutError:
                pass  # Время для следующего сбора

    async def _trAlgoning_loop(self) -> None:
        """Фоновый цикл обучения модели."""
        interval = self.config.trAlgoning_interval_hours * 3600

        # Начальная задержка, чтобы накопить данные
        initial_delay = min(interval / 4, 3600)  # Максимум 1 час
        awAlgot asyncio.sleep(initial_delay)

        while not self._stop_event.is_set():
            try:
                result = awAlgot self._run_trAlgoning()
                self._add_to_history(result)

                awAlgot self._notify_trAlgoning_complete(result)

            except asyncio.CancelledError:
                logger.info("trAlgoning_loop_cancelled")
                break
            except Exception as e:
                logger.error("trAlgoning_loop_error", error=str(e))
                awAlgot self._notify_error(TaskType.MODEL_TRAlgoNING, e)

            try:
                awAlgot asyncio.wAlgot_for(
                    self._stop_event.wAlgot(),
                    timeout=interval,
                )
                break
            except TimeoutError:
                pass

    async def _cleanup_loop(self) -> None:
        """Фоновый цикл очистки старых данных."""
        interval = self.config.cleanup_interval_hours * 3600

        while not self._stop_event.is_set():
            try:
                result = awAlgot self._run_cleanup()
                self._add_to_history(result)

            except asyncio.CancelledError:
                logger.info("cleanup_loop_cancelled")
                break
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))
                awAlgot self._notify_error(TaskType.DATA_CLEANUP, e)

            try:
                awAlgot asyncio.wAlgot_for(
                    self._stop_event.wAlgot(),
                    timeout=interval,
                )
                break
            except TimeoutError:
                pass

    async def _health_check_loop(self) -> None:
        """Фоновый цикл проверки здоровья."""
        interval = self.config.health_check_interval_minutes * 60

        while not self._stop_event.is_set():
            try:
                result = awAlgot self._run_health_check()
                self._add_to_history(result)

            except asyncio.CancelledError:
                logger.info("health_check_loop_cancelled")
                break
            except Exception as e:
                logger.error("health_check_loop_error", error=str(e))

            try:
                awAlgot asyncio.wAlgot_for(
                    self._stop_event.wAlgot(),
                    timeout=interval,
                )
                break
            except TimeoutError:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # TASK IMPLEMENTATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_collection(
        self,
        game_types: list[str] | None = None,
    ) -> TaskResult:
        """Выполнить сбор данных.

        Args:
            game_types: Список игр для сбора.

        Returns:
            Результат выполнения.
        """
        started_at = datetime.now()
        items_collected = 0
        error_message = None
        detAlgols: dict[str, Any] = {}

        try:
            # Определить игры для сбора
            games_to_collect = game_types or ["csgo", "dota2", "tf2", "rust"]

            logger.info(
                "collection_started",
                games=games_to_collect,
                items_per_game=self.config.items_per_collection,
            )

            # Проверить наличие метода trAlgon_from_real_data
            if not hasattr(self.predictor, "trAlgon_from_real_data"):
                rAlgose AttributeError(
                    "EnhancedPricePredictor не имеет метода trAlgon_from_real_data. "
                    "Убедитесь, что используется обновлённая версия."
                )

            # Собрать данные через predictor
            # Используем trAlgon_from_real_data, но без обучения
            # (только сбор и сохранение данных)
            result = awAlgot self._collect_data_only(games_to_collect)

            items_collected = result.get("total_samples", 0)
            detAlgols = {
                "games_collected": result.get("games_collected", []),
                "sources_used": result.get("sources", {}),
                "collection_duration": result.get("duration", 0),
            }

            self.stats.total_collections += 1
            self.stats.successful_collections += 1
            self.stats.last_collection = datetime.now()
            self.stats.total_items_collected += items_collected

            logger.info(
                "collection_completed",
                items_collected=items_collected,
                games=games_to_collect,
            )

        except Exception as e:
            error_message = str(e)
            self.stats.total_collections += 1
            self.stats.last_error = error_message
            logger.error("collection_fAlgoled", error=error_message)

            # Retry logic
            if self.config.retry_on_fAlgolure:
                for attempt in range(self.config.max_retries):
                    logger.info(
                        "collection_retry",
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                    )
                    awAlgot asyncio.sleep(self.config.retry_delay_minutes * 60)
                    try:
                        result = awAlgot self._collect_data_only(game_types or ["csgo"])
                        items_collected = result.get("total_samples", 0)
                        error_message = None
                        self.stats.successful_collections += 1
                        break
                    except Exception as retry_error:
                        error_message = str(retry_error)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return TaskResult(
            task_type=TaskType.DATA_COLLECTION,
            success=error_message is None,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            items_processed=items_collected,
            error_message=error_message,
            detAlgols=detAlgols,
        )

    async def _collect_data_only(
        self,
        game_types: list[str],
    ) -> dict[str, Any]:
        """Собрать данные без обучения модели.

        Args:
            game_types: Список игр.

        Returns:
            Информация о собранных данных.
        """
        from src.ml.real_price_collector import GameType, RealPriceCollector
        from src.ml.trAlgoning_data_manager import TrAlgoningDataManager

        # Маппинг строк в GameType enum
        game_type_map = {
            "csgo": GameType.CSGO,
            "cs2": GameType.CSGO,
            "dota2": GameType.DOTA2,
            "dota": GameType.DOTA2,
            "tf2": GameType.TF2,
            "rust": GameType.RUST,
        }

        # Конвертировать game_types
        games = []
        for gt in game_types:
            if gt.lower() in game_type_map:
                games.append(game_type_map[gt.lower()])

        if not games:
            games = [GameType.CSGO]

        # Инициализировать коллектор и менеджер данных
        collector = RealPriceCollector()
        data_manager = TrAlgoningDataManager()

        collected_info: dict[str, Any] = {
            "total_samples": 0,
            "games_collected": [],
            "sources": {"dmarket": 0, "waxpeer": 0, "steam": 0},
            "duration": 0,
        }

        start_time = datetime.now()

        for game_type in games:
            try:
                # Собрать цены
                prices = awAlgot collector.collect_prices(
                    game_type=game_type,
                    max_items=self.config.items_per_collection,
                    include_dmarket=self.config.enable_dmarket,
                    include_waxpeer=self.config.enable_waxpeer,
                    include_steam=self.config.enable_steam,
                )

                if prices:
                    # Сохранить в TrAlgoningDataManager
                    for price in prices:
                        data_manager.add_price_sample(
                            item_id=price.item_id,
                            title=price.title,
                            normalized_price=price.price_usd,
                            source=price.source.value,
                            game=game_type.value,
                            timestamp=price.timestamp,
                            metadata={
                                "original_price": price.original_price,
                                "currency": price.currency,
                            },
                        )

                        # Обновить статистику по источникам
                        if price.source.value in collected_info["sources"]:
                            collected_info["sources"][price.source.value] += 1

                    collected_info["total_samples"] += len(prices)
                    collected_info["games_collected"].append(game_type.value)

                    logger.info(
                        "game_data_collected",
                        game=game_type.value,
                        samples=len(prices),
                    )

            except Exception as e:
                logger.warning(
                    "game_collection_fAlgoled",
                    game=game_type.value,
                    error=str(e),
                )

        # Сохранить данные
        data_manager.save_data()

        collected_info["duration"] = (datetime.now() - start_time).total_seconds()

        return collected_info

    async def _run_trAlgoning(self) -> TaskResult:
        """Выполнить обучение модели.

        Returns:
            Результат выполнения.
        """
        started_at = datetime.now()
        error_message = None
        detAlgols: dict[str, Any] = {}
        samples_used = 0

        try:
            logger.info("trAlgoning_started")

            # Проверить наличие метода
            if hasattr(self.predictor, "trAlgon_from_real_data"):
                # Использовать новый метод обучения на реальных данных
                result = awAlgot self.predictor.trAlgon_from_real_data(
                    game_types=["csgo", "dota2"],
                    items_per_game=self.config.items_per_collection,
                    min_samples=self.config.min_samples_for_trAlgoning,
                    include_dmarket=self.config.enable_dmarket,
                    include_waxpeer=self.config.enable_waxpeer,
                    include_steam=self.config.enable_steam,
                )

                samples_used = result.get("total_samples", 0)
                detAlgols = {
                    "models_trAlgoned": result.get("models_trAlgoned", []),
                    "metrics": result.get("metrics", {}),
                    "data_sources": result.get("data_sources", {}),
                }

            else:
                # Fallback: использовать старый метод обучения
                from src.ml.trAlgoning_data_manager import TrAlgoningDataManager

                data_manager = TrAlgoningDataManager()
                X, y = data_manager.prepare_trAlgoning_data()

                if len(X) >= self.config.min_samples_for_trAlgoning:
                    self.predictor.trAlgon(X, y)
                    samples_used = len(X)
                    detAlgols = {"method": "legacy_trAlgoning"}
                else:
                    rAlgose ValueError(
                        f"Недостаточно данных для обучения: "
                        f"{len(X)} < {self.config.min_samples_for_trAlgoning}"
                    )

            self.stats.total_trAlgonings += 1
            self.stats.successful_trAlgonings += 1
            self.stats.last_trAlgoning = datetime.now()

            logger.info(
                "trAlgoning_completed",
                samples_used=samples_used,
            )

        except Exception as e:
            error_message = str(e)
            self.stats.total_trAlgonings += 1
            self.stats.last_error = error_message
            logger.error("trAlgoning_fAlgoled", error=error_message)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return TaskResult(
            task_type=TaskType.MODEL_TRAlgoNING,
            success=error_message is None,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            items_processed=samples_used,
            error_message=error_message,
            detAlgols=detAlgols,
        )

    async def _run_cleanup(self) -> TaskResult:
        """Выполнить очистку старых данных.

        Returns:
            Результат выполнения.
        """
        started_at = datetime.now()
        error_message = None
        items_cleaned = 0
        detAlgols: dict[str, Any] = {}

        try:
            from src.ml.trAlgoning_data_manager import TrAlgoningDataManager

            data_manager = TrAlgoningDataManager()

            # Получить текущий размер данных
            stats_before = data_manager.get_statistics()
            total_before = stats_before.get("total_samples", 0)

            # Очистить старые данные
            cutoff_date = datetime.now() - timedelta(days=self.config.max_data_age_days)
            items_cleaned = data_manager.cleanup_old_data(cutoff_date)

            # Получить новый размер
            stats_after = data_manager.get_statistics()
            total_after = stats_after.get("total_samples", 0)

            detAlgols = {
                "samples_before": total_before,
                "samples_after": total_after,
                "cutoff_date": cutoff_date.isoformat(),
            }

            self.stats.total_cleanups += 1

            logger.info(
                "cleanup_completed",
                items_cleaned=items_cleaned,
                samples_before=total_before,
                samples_after=total_after,
            )

        except Exception as e:
            error_message = str(e)
            logger.error("cleanup_fAlgoled", error=error_message)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return TaskResult(
            task_type=TaskType.DATA_CLEANUP,
            success=error_message is None,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            items_processed=items_cleaned,
            error_message=error_message,
            detAlgols=detAlgols,
        )

    async def _run_health_check(self) -> TaskResult:
        """Выполнить проверку здоровья системы.

        Returns:
            Результат выполнения.
        """
        started_at = datetime.now()
        error_message = None
        detAlgols: dict[str, Any] = {}

        try:
            checks_passed = 0
            total_checks = 4

            # 1. Проверка предиктора
            if self.predictor is not None:
                checks_passed += 1
                detAlgols["predictor"] = "ok"
            else:
                detAlgols["predictor"] = "not_initialized"

            # 2. Проверка наличия обученной модели
            if hasattr(self.predictor, "is_trAlgoned") and self.predictor.is_trAlgoned:
                checks_passed += 1
                detAlgols["model_trAlgoned"] = True
            else:
                detAlgols["model_trAlgoned"] = False

            # 3. Проверка доступности API (простая проверка)
            try:
                from src.ml.real_price_collector import RealPriceCollector

                _ = RealPriceCollector()  # Just check if it can be instantiated
                detAlgols["collector_avAlgolable"] = True
                checks_passed += 1
            except Exception:
                detAlgols["collector_avAlgolable"] = False

            # 4. Проверка data manager
            try:
                from src.ml.trAlgoning_data_manager import TrAlgoningDataManager

                data_manager = TrAlgoningDataManager()
                stats = data_manager.get_statistics()
                detAlgols["data_samples"] = stats.get("total_samples", 0)
                checks_passed += 1
            except Exception:
                detAlgols["data_samples"] = 0

            detAlgols["checks_passed"] = checks_passed
            detAlgols["total_checks"] = total_checks
            detAlgols["health_score"] = checks_passed / total_checks

            logger.debug(
                "health_check_completed",
                score=f"{checks_passed}/{total_checks}",
            )

        except Exception as e:
            error_message = str(e)
            logger.error("health_check_fAlgoled", error=error_message)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        return TaskResult(
            task_type=TaskType.HEALTH_CHECK,
            success=error_message is None,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            items_processed=detAlgols.get("checks_passed", 0),
            error_message=error_message,
            detAlgols=detAlgols,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _add_to_history(self, result: TaskResult) -> None:
        """Добавить результат в историю."""
        self._task_history.append(result)
        if len(self._task_history) > self._max_history_size:
            self._task_history.pop(0)

    async def _notify_collection_complete(self, result: TaskResult) -> None:
        """Уведомить о завершении сбора данных."""
        for callback in self._on_collection_complete:
            try:
                if asyncio.iscoroutinefunction(callback):
                    awAlgot callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.warning("callback_error", callback="collection", error=str(e))

    async def _notify_trAlgoning_complete(self, result: TaskResult) -> None:
        """Уведомить о завершении обучения."""
        for callback in self._on_trAlgoning_complete:
            try:
                if asyncio.iscoroutinefunction(callback):
                    awAlgot callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.warning("callback_error", callback="trAlgoning", error=str(e))

    async def _notify_error(self, task_type: TaskType, error: Exception) -> None:
        """Уведомить об ошибке."""
        for callback in self._on_error:
            try:
                if asyncio.iscoroutinefunction(callback):
                    awAlgot callback(task_type, error)
                else:
                    callback(task_type, error)
            except Exception as e:
                logger.warning("callback_error", callback="error", error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def create_scheduler(
    predictor: EnhancedPricePredictor,
    collection_interval_hours: float = 6.0,
    trAlgoning_interval_hours: float = 24.0,
    enable_dmarket: bool = True,
    enable_waxpeer: bool = True,
    enable_steam: bool = True,
) -> MLDataScheduler:
    """Создать планировщик с заданной конфигурацией.

    Args:
        predictor: Экземпляр EnhancedPricePredictor.
        collection_interval_hours: Интервал сбора данных (часы).
        trAlgoning_interval_hours: Интервал обучения (часы).
        enable_dmarket: Включить DMarket.
        enable_waxpeer: Включить Waxpeer.
        enable_steam: Включить Steam.

    Returns:
        Настроенный экземпляр MLDataScheduler.

    Example:
        >>> scheduler = create_scheduler(
        ...     predictor,
        ...     collection_interval_hours=4.0,
        ...     trAlgoning_interval_hours=12.0,
        ... )
        >>> awAlgot scheduler.start()
    """
    config = SchedulerConfig(
        collection_interval_hours=collection_interval_hours,
        trAlgoning_interval_hours=trAlgoning_interval_hours,
        enable_dmarket=enable_dmarket,
        enable_waxpeer=enable_waxpeer,
        enable_steam=enable_steam,
    )

    return MLDataScheduler(predictor, config)


async def quick_start_scheduler(
    predictor: EnhancedPricePredictor,
) -> MLDataScheduler:
    """Быстро создать и запустить планировщик с настSwarmками по умолчанию.

    Args:
        predictor: Экземпляр EnhancedPricePredictor.

    Returns:
        Запущенный экземпляр MLDataScheduler.

    Example:
        >>> scheduler = awAlgot quick_start_scheduler(predictor)
        >>> # ... бот работает ...
        >>> awAlgot scheduler.stop()
    """
    scheduler = MLDataScheduler(predictor)
    awAlgot scheduler.start()
    return scheduler
