"""Команда для отправки ежедневного отчета вручную.

Этот модуль предоставляет команду /dailyreport для администраторов,
которая позволяет отправить ежедневный отчет немедленно, не дожидаясь
автоматической генерации по расписанию.
"""

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from src.utils.daily_report_scheduler import DailyReportScheduler


logger = logging.getLogger(__name__)


async def daily_report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик команды /dailyreport для отправки ежедневного отчета.

    Проверяет права администратора и отправляет ежедневный отчет
    за последние N дней (по умолчанию 1 день).

    Args:
        update: Объект Update от Telegram
        context: Контекст выполнения команды

    """
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    # Получить конфигурацию и планировщик
    config = context.bot_data.get("config")
    scheduler: DailyReportScheduler | None = context.application.bot_data.get(
        "daily_report_scheduler",
    )

    # Проверка прав администратора
    admin_users = []
    if config and hasattr(config.security, "admin_users"):
        admin_users = config.security.admin_users

    if not admin_users and config and hasattr(config.security, "allowed_users"):
        admin_users = config.security.allowed_users

    if user_id not in admin_users:
        await update.message.reply_text(
            "❌ Эта команда доступна только администраторам",
        )
        logger.warning(
            "User %s attempted to access /dailyreport without admin rights",
            user_id,
        )
        return

    # Проверка наличия планировщика
    if not scheduler:
        await update.message.reply_text(
            "❌ Планировщик ежедневных отчетов не инициализирован",
        )
        logger.error("Daily report scheduler not initialized")
        return

    # Определить количество дней для отчета (из аргументов команды)
    days = 1
    if context.args and len(context.args) > 0:
        try:
            days = int(context.args[0])
            if days < 1 or days > 30:
                await update.message.reply_text(
                    "❌ Количество дней должно быть от 1 до 30",
                )
                return
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Используйте: /dailyreport [дни]",
            )
            return

    # Отправить статус генерации
    status_message = await update.message.reply_text(
        f"📊 Генерация отчета за последние {days} дн..\nПожалуйста, подождите...",
    )

    try:
        # Отправить ежедневный отчет
        await scheduler.send_manual_report(days=days)

        # Обновить статус
        await status_message.edit_text(
            f"✅ Ежедневный отчет за {days} дн. успешно отправлен!",
        )

        logger.info(
            "Manual daily report for %s days sent by user %s",
            days,
            user_id,
        )

    except Exception as e:
        logger.exception("Failed to send manual daily report: %s", e)

        await status_message.edit_text(
            f"❌ Ошибка при генерации отчета:\n{e!s}",
        )


__all__ = ["daily_report_command"]
