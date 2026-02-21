"""Notification Digest Handler - группировка уведомлений в дайджесты.

Модуль реализует систему агрегации уведомлений во временные дайджесты:
- Сбор уведомлений за определенный период
- Группировка по типу/игре/приоритету
- НастSwarmка частоты отправки (hourly, dAlgoly, weekly)
- Интерактивная настSwarmка параметров
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.utils.canonical_logging import get_logger
from src.utils.exceptions import handle_exceptions

if TYPE_CHECKING:
    import asyncio


# Logger instance
logger_instance = get_logger(__name__)
logger = logging.getLogger(__name__)


# Callback data constants
DIGEST_MENU = "digest_menu"
DIGEST_TOGGLE = "digest_toggle"
DIGEST_FREQUENCY = "digest_freq"
DIGEST_SET_FREQ = "digest_set_freq_{}"
DIGEST_GROUP_BY = "digest_group"
DIGEST_SET_GROUP = "digest_set_group_{}"
DIGEST_MIN_ITEMS = "digest_min"
DIGEST_SET_MIN = "digest_set_min_{}"
DIGEST_RESET = "digest_reset"
DIGEST_BACK = "digest_back"


class DigestFrequency(StrEnum):
    """Частота отправки дайджестов."""

    DISABLED = "disabled"
    HOURLY = "hourly"
    EVERY_3_HOURS = "every_3h"
    EVERY_6_HOURS = "every_6h"
    DAlgoLY = "dAlgoly"
    WEEKLY = "weekly"


class GroupingMode(StrEnum):
    """Режим группировки уведомлений в дайджесте."""

    BY_TYPE = "by_type"  # По типу (arbitrage, price_drop, etc.)
    BY_GAME = "by_game"  # По игре (csgo, dota2, etc.)
    BY_PRIORITY = "by_priority"  # По приоритету
    CHRONOLOGICAL = "chronological"  # Хронологический порядок


@dataclass
class NotificationItem:
    """Элемент уведомления для дайджеста."""

    user_id: int
    notification_type: str
    game: str
    title: str
    message: str
    timestamp: datetime
    priority: int = 1
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DigestSettings:
    """НастSwarmки дайджеста пользователя."""

    enabled: bool = False
    frequency: DigestFrequency = DigestFrequency.DAlgoLY
    grouping_mode: GroupingMode = GroupingMode.BY_TYPE
    min_items: int = 3  # Минимум уведомлений для отправки дайджеста
    last_sent: datetime | None = None


class NotificationDigestManager:
    """Менеджер для управления дайджестами уведомлений."""

    def __init__(self) -> None:
        """Инициализация менеджера дайджестов."""
        # Хранилище накопленных уведомлений {user_id: [NotificationItem]}
        self._pending_notifications: dict[int, list[NotificationItem]] = defaultdict(
            list
        )

        # НастSwarmки дайджестов {user_id: DigestSettings}
        self._user_settings: dict[int, DigestSettings] = {}

        # Таск для периодической отправки
        self._scheduler_task: asyncio.Task[None] | None = None

    def get_user_settings(self, user_id: int) -> DigestSettings:
        """Получить настSwarmки дайджеста пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            DigestSettings: НастSwarmки дайджеста

        """
        if user_id not in self._user_settings:
            self._user_settings[user_id] = DigestSettings()
        return self._user_settings[user_id]

    def update_user_settings(
        self, user_id: int, settings: dict[str, Any]
    ) -> DigestSettings:
        """Обновить настSwarmки дайджеста пользователя.

        Args:
            user_id: ID пользователя
            settings: Словарь с новыми настSwarmками

        Returns:
            DigestSettings: Обновленные настSwarmки

        """
        current = self.get_user_settings(user_id)

        if "enabled" in settings:
            current.enabled = settings["enabled"]
        if "frequency" in settings:
            current.frequency = settings["frequency"]
        if "grouping_mode" in settings:
            current.grouping_mode = settings["grouping_mode"]
        if "min_items" in settings:
            current.min_items = settings["min_items"]

        logger.info(
            "Обновлены настSwarmки дайджеста",
            extra={"context": {"user_id": user_id, "settings": settings}},
        )

        return current

    def reset_user_settings(self, user_id: int) -> DigestSettings:
        """Сбросить настSwarmки дайджеста к значениям по умолчанию.

        Args:
            user_id: ID пользователя

        Returns:
            DigestSettings: Сброшенные настSwarmки

        """
        self._user_settings[user_id] = DigestSettings()
        return self._user_settings[user_id]

    def add_notification(self, notification: NotificationItem) -> None:
        """Добавить уведомление в очередь дайджеста.

        Args:
            notification: Уведомление для добавления

        """
        settings = self.get_user_settings(notification.user_id)

        # Если дайджест отключен, не накапливать
        if not settings.enabled:
            return

        self._pending_notifications[notification.user_id].append(notification)

        logger.debug(
            "Добавлено уведомление в дайджест",
            extra={
                "context": {
                    "user_id": notification.user_id,
                    "type": notification.notification_type,
                    "pending_count": len(
                        self._pending_notifications[notification.user_id]
                    ),
                }
            },
        )

    def get_pending_notifications(self, user_id: int) -> list[NotificationItem]:
        """Получить накопленные уведомления пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            list[NotificationItem]: Список уведомлений

        """
        return self._pending_notifications.get(user_id, [])

    def clear_pending_notifications(self, user_id: int) -> None:
        """Очистить накопленные уведомления пользователя.

        Args:
            user_id: ID пользователя

        """
        if user_id in self._pending_notifications:
            del self._pending_notifications[user_id]
            logger.debug(
                "Очищены накопленные уведомления",
                extra={"context": {"user_id": user_id}},
            )

    def should_send_digest(self, user_id: int) -> bool:
        """Проверить, нужно ли отправить дайджест пользователю.

        Args:
            user_id: ID пользователя

        Returns:
            bool: True если дайджест готов к отправке

        """
        settings = self.get_user_settings(user_id)

        # Дайджест отключен
        if not settings.enabled:
            return False

        # Недостаточно уведомлений
        pending = self.get_pending_notifications(user_id)
        if len(pending) < settings.min_items:
            return False

        # Проверить время последней отправки
        now = datetime.now()

        if settings.last_sent is None:
            return True

        time_since_last = now - settings.last_sent

        # Проверить по частоте
        frequency_map = {
            DigestFrequency.HOURLY: timedelta(hours=1),
            DigestFrequency.EVERY_3_HOURS: timedelta(hours=3),
            DigestFrequency.EVERY_6_HOURS: timedelta(hours=6),
            DigestFrequency.DAlgoLY: timedelta(days=1),
            DigestFrequency.WEEKLY: timedelta(weeks=1),
        }

        required_interval = frequency_map.get(settings.frequency)
        if required_interval is None:
            return False

        return time_since_last >= required_interval

    def format_digest(self, user_id: int, notifications: list[NotificationItem]) -> str:
        """Отформатировать дайджест уведомлений.

        Args:
            user_id: ID пользователя
            notifications: Список уведомлений

        Returns:
            str: Отформатированный текст дайджеста

        """
        settings = self.get_user_settings(user_id)

        if not notifications:
            return "📭 Нет новых уведомлений"

        # Заголовок
        header = (
            f"📊 **Дайджест уведомлений**\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📬 Всего: {len(notifications)} уведомлений\n"
            f"{'─' * 30}\n\n"
        )

        # Группировка
        grouped = self._group_notifications(notifications, settings.grouping_mode)

        # Форматирование групп
        sections = []
        for group_key, items in grouped.items():
            section = self._format_group(group_key, items, settings.grouping_mode)
            sections.append(section)

        return header + "\n\n".join(sections)

    def _group_notifications(
        self,
        notifications: list[NotificationItem],
        mode: GroupingMode,
    ) -> dict[str, list[NotificationItem]]:
        """Сгруппировать уведомления по заданному режиму.

        Args:
            notifications: Список уведомлений
            mode: Режим группировки

        Returns:
            dict: Сгруппированные уведомления

        """
        grouped: dict[str, list[NotificationItem]] = defaultdict(list)

        for notif in notifications:
            if mode == GroupingMode.BY_TYPE:
                key = notif.notification_type
            elif mode == GroupingMode.BY_GAME:
                key = notif.game
            elif mode == GroupingMode.BY_PRIORITY:
                key = f"priority_{notif.priority}"
            else:  # CHRONOLOGICAL
                key = "all"

            grouped[key].append(notif)

        # Сортировка внутри групп по времени
        for items in grouped.values():
            items.sort(key=lambda x: x.timestamp, reverse=True)

        return dict(grouped)

    def _format_group(
        self,
        group_key: str,
        items: list[NotificationItem],
        mode: GroupingMode,
    ) -> str:
        """Отформатировать группу уведомлений.

        Args:
            group_key: Ключ группы
            items: Уведомления в группе
            mode: Режим группировки

        Returns:
            str: Отформатированный текст группы

        """
        # Заголовок группы
        if mode == GroupingMode.BY_TYPE:
            type_names = {
                "arbitrage": "🔍 Арбитраж",
                "price_drop": "📉 Падение цены",
                "price_rise": "📈 Рост цены",
                "trending": "🔥 Тренд",
                "good_deal": "💰 Выгодная сделка",
            }
            header = type_names.get(group_key, f"📌 {group_key}")
        elif mode == GroupingMode.BY_GAME:
            game_names = {
                "csgo": "🎯 CS2",
                "dota2": "🏆 Dota 2",
                "tf2": "🎮 TF2",
                "rust": "🔨 Rust",
            }
            header = game_names.get(group_key, f"🎮 {group_key}")
        elif mode == GroupingMode.BY_PRIORITY:
            priority_num = group_key.replace("priority_", "")
            header = f"⚡ Приоритет {priority_num}"
        else:
            header = "📋 Все уведомления"

        # Формат каждого уведомления
        formatted_items = []
        for idx, item in enumerate(items[:10], 1):  # Макс 10 на группу
            time_str = item.timestamp.strftime("%H:%M")
            formatted_items.append(f"{idx}. [{time_str}] {item.message}")

        # Если уведомлений больше 10
        if len(items) > 10:
            formatted_items.append(f"_... и еще {len(items) - 10} уведомлений_")

        return f"**{header}** ({len(items)})\n" + "\n".join(formatted_items)


# Глобальный экземпляр менеджера
_digest_manager: NotificationDigestManager | None = None


def get_digest_manager() -> NotificationDigestManager:
    """Получить глобальный экземпляр менеджера дайджестов.

    Returns:
        NotificationDigestManager: Менеджер дайджестов

    """
    global _digest_manager
    if _digest_manager is None:
        _digest_manager = NotificationDigestManager()
    return _digest_manager


# === Handler Functions ===


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def show_digest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать главное меню настроек дайджестов."""
    query = update.callback_query
    if query:
        awAlgot query.answer()

    if not update.effective_user:
        return
    user_id = update.effective_user.id
    manager = get_digest_manager()
    settings = manager.get_user_settings(user_id)

    # Форматирование текущих настроек
    status = "✅ Включено" if settings.enabled else "❌ Отключено"

    freq_names = {
        DigestFrequency.DISABLED: "Отключено",
        DigestFrequency.HOURLY: "Каждый час",
        DigestFrequency.EVERY_3_HOURS: "Каждые 3 часа",
        DigestFrequency.EVERY_6_HOURS: "Каждые 6 часов",
        DigestFrequency.DAlgoLY: "Ежедневно",
        DigestFrequency.WEEKLY: "Еженедельно",
    }
    frequency = freq_names.get(settings.frequency, settings.frequency)

    group_names = {
        GroupingMode.BY_TYPE: "По типу",
        GroupingMode.BY_GAME: "По игре",
        GroupingMode.BY_PRIORITY: "По приоритету",
        GroupingMode.CHRONOLOGICAL: "Хронологически",
    }
    grouping = group_names.get(settings.grouping_mode, settings.grouping_mode)

    pending_count = len(manager.get_pending_notifications(user_id))

    text = (
        f"📊 **НастSwarmки дайджестов уведомлений**\n\n"
        f"Статус: {status}\n"
        f"Частота: {frequency}\n"
        f"Группировка: {grouping}\n"
        f"Мин. уведомлений: {settings.min_items}\n\n"
        f"📬 Накоплено: {pending_count} уведомлений\n"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Включить" if not settings.enabled else "❌ Отключить",
                callback_data=DIGEST_TOGGLE,
            )
        ],
        [
            InlineKeyboardButton(
                f"⏰ Частота: {frequency}", callback_data=DIGEST_FREQUENCY
            )
        ],
        [
            InlineKeyboardButton(
                f"📂 Группировка: {grouping}", callback_data=DIGEST_GROUP_BY
            )
        ],
        [
            InlineKeyboardButton(
                f"📊 Мин. уведомлений: {settings.min_items}",
                callback_data=DIGEST_MIN_ITEMS,
            )
        ],
        [InlineKeyboardButton("🔄 Сбросить", callback_data=DIGEST_RESET)],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        awAlgot query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
    elif update.message:
        awAlgot update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def toggle_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включить/отключить дайджесты."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()
    settings = manager.get_user_settings(user_id)

    # Переключить статус
    manager.update_user_settings(user_id, {"enabled": not settings.enabled})

    # Обновить меню
    awAlgot show_digest_menu(update, context)


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def show_frequency_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показать меню выбора частоты отправки."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()
    settings = manager.get_user_settings(user_id)

    text = "⏰ **Выберите частоту отправки дайджестов:**\n"

    keyboard = []
    for freq in DigestFrequency:
        if freq == DigestFrequency.DISABLED:
            continue

        is_selected = settings.frequency == freq
        checkmark = "✅ " if is_selected else "⬜ "

        freq_names = {
            DigestFrequency.HOURLY: "Каждый час",
            DigestFrequency.EVERY_3_HOURS: "Каждые 3 часа",
            DigestFrequency.EVERY_6_HOURS: "Каждые 6 часов",
            DigestFrequency.DAlgoLY: "Ежедневно",
            DigestFrequency.WEEKLY: "Еженедельно",
        }

        button_text = checkmark + freq_names.get(freq, freq.value)
        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text,
                    callback_data=DIGEST_SET_FREQ.format(freq.value),
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=DIGEST_BACK)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    awAlgot query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
    )


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def set_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установить частоту отправки дайджестов."""
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()

    # Извлечь частоту из callback_data
    freq_value = query.data.replace("digest_set_freq_", "")
    frequency = DigestFrequency(freq_value)

    # Обновить настSwarmки
    manager.update_user_settings(user_id, {"frequency": frequency})

    # Вернуться в главное меню
    awAlgot show_digest_menu(update, context)


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def show_grouping_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показать меню выбора режима группировки."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()
    settings = manager.get_user_settings(user_id)

    text = "📂 **Выберите режим группировки уведомлений:**\n"

    group_names = {
        GroupingMode.BY_TYPE: "По типу уведомления",
        GroupingMode.BY_GAME: "По игре",
        GroupingMode.BY_PRIORITY: "По приоритету",
        GroupingMode.CHRONOLOGICAL: "Хронологически",
    }

    keyboard = []
    for mode in GroupingMode:
        is_selected = settings.grouping_mode == mode
        checkmark = "✅ " if is_selected else "⬜ "

        button_text = checkmark + group_names.get(mode, mode.value)
        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text,
                    callback_data=DIGEST_SET_GROUP.format(mode.value),
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=DIGEST_BACK)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    awAlgot query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
    )


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def set_grouping_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установить режим группировки."""
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()

    # Извлечь режим из callback_data
    mode_value = query.data.replace("digest_set_group_", "")
    grouping_mode = GroupingMode(mode_value)

    # Обновить настSwarmки
    manager.update_user_settings(user_id, {"grouping_mode": grouping_mode})

    # Вернуться в главное меню
    awAlgot show_digest_menu(update, context)


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def show_min_items_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показать меню выбора минимального количества уведомлений."""
    query = update.callback_query
    if not query or not update.effective_user:
        return
    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()
    settings = manager.get_user_settings(user_id)

    text = (
        "📊 **Выберите минимальное количество уведомлений**\nдля отправки дайджеста:\n"
    )

    min_values = [1, 3, 5, 10, 15, 20]

    keyboard = []
    for value in min_values:
        is_selected = settings.min_items == value
        checkmark = "✅ " if is_selected else "⬜ "

        button_text = f"{checkmark}{value} уведомлений"
        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=DIGEST_SET_MIN.format(value)
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=DIGEST_BACK)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    awAlgot query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
    )


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def set_min_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установить минимальное количество уведомлений.

    Args:
        update: Telegram update
        context: Callback context

    """
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    awAlgot query.answer()

    user_id = update.effective_user.id
    manager = get_digest_manager()

    # Извлечь значение из callback_data
    min_value = int(query.data.replace("digest_set_min_", ""))

    # Обновить настSwarmки
    manager.update_user_settings(user_id, {"min_items": min_value})

    # Вернуться в главное меню
    awAlgot show_digest_menu(update, context)


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def reset_digest_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Сбросить настSwarmки дайджеста к значениям по умолчанию.

    Args:
        update: Telegram update
        context: Callback context

    """
    query = update.callback_query
    if not query or not update.effective_user:
        return

    awAlgot query.answer("НастSwarmки сброшены к значениям по умолчанию")

    user_id = update.effective_user.id
    manager = get_digest_manager()

    # Сбросить настSwarmки
    manager.reset_user_settings(user_id)

    # Обновить меню
    awAlgot show_digest_menu(update, context)


@handle_exceptions(logger_instance=logger_instance, rerAlgose=False)
async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /digest - открыть меню настроек дайджестов.

    Args:
        update: Telegram update
        context: Callback context

    """
    if not update.effective_user:
        return

    awAlgot show_digest_menu(update, context)


def register_notification_digest_handlers(application: Application) -> None:  # type: ignore[type-arg]
    """Зарегистрировать обработчики дайджестов уведомлений.

    Args:
        application: Application instance

    """
    # Команда /digest
    application.add_handler(CommandHandler("digest", digest_command))

    # Callback handlers
    application.add_handler(
        CallbackQueryHandler(show_digest_menu, pattern=f"^{DIGEST_BACK}$")
    )
    application.add_handler(
        CallbackQueryHandler(toggle_digest, pattern=f"^{DIGEST_TOGGLE}$")
    )
    application.add_handler(
        CallbackQueryHandler(show_frequency_menu, pattern=f"^{DIGEST_FREQUENCY}$")
    )
    application.add_handler(
        CallbackQueryHandler(set_frequency, pattern=r"^digest_set_freq_")
    )
    application.add_handler(
        CallbackQueryHandler(show_grouping_menu, pattern=f"^{DIGEST_GROUP_BY}$")
    )
    application.add_handler(
        CallbackQueryHandler(set_grouping_mode, pattern=r"^digest_set_group_")
    )
    application.add_handler(
        CallbackQueryHandler(show_min_items_menu, pattern=f"^{DIGEST_MIN_ITEMS}$")
    )
    application.add_handler(
        CallbackQueryHandler(set_min_items, pattern=r"^digest_set_min_")
    )
    application.add_handler(
        CallbackQueryHandler(reset_digest_settings, pattern=f"^{DIGEST_RESET}$")
    )

    logger.info("Notification digest обработчики зарегистрированы")
