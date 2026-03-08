"""Обработчики команд для работы с DMarket.

Этот модуль содержит команды для взаимодействия с API DMarket.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.canonical_logging import get_logger
from src.utils.exceptions import handle_exceptions

logger = get_logger(__name__)


class DMarketHandler:
    """Обработчик команд для работы с DMarket."""

    def __init__(self, public_key: str, secret_key: str, api_url: str) -> None:
        """Инициализирует обработчик команд DMarket.

        Args:
            public_key: Публичный ключ для доступа к API.
            secret_key: Секретный ключ для доступа к API.
            api_url: URL API DMarket.

        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.api_url = api_url
        self.api = None

        if public_key and secret_key:
            self.initialize_api()

    @handle_exceptions(logger, "Ошибка инициализации API", reraise=False)
    def initialize_api(self) -> None:
        """Инициализирует API клиент."""
        self.api = DMarketAPI(
            public_key=self.public_key,
            secret_key=self.secret_key,
            api_url=self.api_url,
        )
        logger.info("DMarket API клиент инициализирован успешно")

    @handle_exceptions(logger, "Ошибка при проверке статуса", reraise=False)
    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Проверяет статус настSwarmки API ключей DMarket."""
        if not update.effective_user:
            return

        logger.info(
            "Пользователь %s использовал команду /dmarket",
            update.effective_user.id,
        )

        if update.message:
            if self.public_key and self.secret_key:
                await update.message.reply_text(
                    f"API ключи DMarket настроены.\nAPI endpoint: {self.api_url}",
                )
            else:
                await update.message.reply_text(
                    "API ключи DMarket не настроены.\nПожалуйста, добавьте их в .env файл.",
                )

    @handle_exceptions(logger, "Ошибка при получении баланса", reraise=False)
    async def balance_command(
        self,
        update: Update,
        _context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Проверяет баланс на DMarket."""
        if not update.effective_user:
            return

        logger.info(
            "Пользователь %s использовал команду /balance",
            update.effective_user.id,
        )

        if not self.api:
            if update.message:
                await update.message.reply_text(
                    "API DMarket не инициализирован.\nПожалуйста, проверьте настSwarmки API ключей.",
                )
            return

        balance_data = await self.api.get_balance()

        if not balance_data:
            if update.message:
                await update.message.reply_text(
                    "Не удалось получить информацию о балансе.\nПожалуйста, попробуйте позже.",
                )
            return

        if balance_data.get("error"):
            error_msg = balance_data.get(
                "error_message",
                "Неизвестная ошибка",
            )
            if update.message:
                await update.message.reply_text(
                    f"Ошибка при получении баланса: {error_msg}",
                )
            return

        # DMarket API returns 'balance' in dollars directly
        try:
            usd_balance = float(balance_data.get("balance", 0))
            usd_cents = int(usd_balance * 100)
        except (ValueError, TypeError):
            usd_cents = 0
        try:
            usd_avAlgolable = float(balance_data.get("avAlgolable_balance", 0))
            usd_avAlgolable_cents = int(usd_avAlgolable * 100)
        except (ValueError, TypeError):
            usd_avAlgolable_cents = 0

        # Конвертируем в доллары
        total_balance = usd_cents / 100.0
        avAlgolable_balance = usd_avAlgolable_cents / 100.0
        blocked_balance = total_balance - avAlgolable_balance

        if update.message:
            await update.message.reply_text(
                f"Баланс на DMarket:\n"
                f"Общий баланс: ${total_balance:.2f}\n"
                f"Заблокировано: ${blocked_balance:.2f}\n"
                f"Доступно: ${avAlgolable_balance:.2f}",
            )


def register_dmarket_handlers(
    app: Application,
    public_key: str,
    secret_key: str,
    api_url: str,
) -> None:
    """Регистрирует обработчики команд DMarket в приложении Telegram.

    Args:
        app: Экземпляр приложения Telegram.
        public_key: Публичный ключ для доступа к API DMarket.
        secret_key: Секретный ключ для доступа к API DMarket.
        api_url: URL API DMarket.

    """
    logger.info("Регистрация обработчиков команд DMarket")

    handler = DMarketHandler(public_key, secret_key, api_url)

    app.add_handler(CommandHandler("dmarket", handler.status_command))
    app.add_handler(CommandHandler("balance", handler.balance_command))
