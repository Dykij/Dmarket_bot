"""AI Training Handler for Telegram Bot.

This module provides Telegram commands for:
- /ai_train - Train the AI price prediction model
- /ai_status - Check AI model status and data collection progress
- /ai_scan - Run AI-powered smart scan

Usage:
    Register handlers in your bot initialization:
    ```python
    from src.telegram_bot.handlers.ai_handler import register_ai_handlers
    register_ai_handlers(application)
    ```
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)


def _get_data_status(output_path: str) -> dict[str, Any]:
    """Get status of collected training data.

    Args:
        output_path: Path to the CSV data file

    Returns:
        Dictionary with data collection status
    """
    path = Path(output_path)

    status: dict[str, Any] = {
        "exists": path.exists(),
        "rows": 0,
        "ready_for_training": False,
        "path": str(path),
    }

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                # Count rows (excluding header)
                row_count = sum(1 for _ in f) - 1
                status["rows"] = max(0, row_count)
                status["ready_for_training"] = row_count >= 100
        except Exception as e:
            logger.warning("data_status_check_failed", error=str(e))

    return status


async def ai_train_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_train command - Train the AI price prediction model.

    This command triggers training of the RandomForest model on collected
    market data. Requires at least 100 data points in market_history.csv.

    Usage: /ai_train
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_train_command", user_id=user_id)

    await update.message.reply_text(
        "🤖 <b>Запуск обучения AI модели...</b>\n\n"
        "Это может занять несколько минут.",
        parse_mode="HTML",
    )

    try:
        from src.ai.price_predictor import PricePredictor

        predictor = PricePredictor()
        result = predictor.train_model()

        await update.message.reply_text(
            f"🤖 <b>Результат обучения AI:</b>\n\n{result}",
            parse_mode="HTML",
        )

        # Log training result
        logger.info(
            "ai_model_trained",
            user_id=user_id,
            result=result,
        )

    except ImportError as e:
        error_msg = (
            "❌ <b>Ошибка:</b> Отсутствуют зависимости для AI.\n\n"
            f"Установите: <code>pip install scikit-learn pandas numpy scipy joblib</code>\n\n"
            f"Детали: {e}"
        )
        await update.message.reply_text(error_msg, parse_mode="HTML")

    except Exception as e:
        error_msg = f"❌ <b>Ошибка обучения:</b>\n\n{e}"
        await update.message.reply_text(error_msg, parse_mode="HTML")
        logger.exception("ai_train_failed", error=str(e))


async def ai_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_status command - Check AI model and data status.

    Shows:
    - Model training status
    - Number of known items
    - Data collection progress
    - Recommendation on next steps

    Usage: /ai_status
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_status_command", user_id=user_id)

    try:
        from src.ai.price_predictor import PricePredictor
        from src.dmarket.market_data_logger import MarketDataLoggerConfig

        predictor = PricePredictor()
        model_info = predictor.get_model_info()

        # Get data status (just check file existence, don't need API)
        config = MarketDataLoggerConfig()
        data_status = _get_data_status(config.output_path)

        # Build status message
        status_parts = ["🤖 <b>AI Status</b>\n"]

        # Model status
        if model_info["is_trained"]:
            status_parts.append(
                f"✅ Модель обучена\n"
                f"📦 Известных предметов: {model_info.get('known_items_count', 'N/A')}\n"
            )
        else:
            status_parts.append("❌ Модель не обучена\n")

        status_parts.extend([
            "",  # Empty line
            "<b>📊 Данные для обучения:</b>\n",
        ])

        if data_status["exists"]:
            status_parts.append(
                f"📄 Файл: {data_status['path']}\n"
                f"📈 Записей: {data_status['rows']}\n"
            )

            if data_status["ready_for_training"]:
                status_parts.append("✅ Достаточно данных для обучения\n")
            else:
                remaining = 100 - data_status["rows"]
                status_parts.append(
                    f"⏳ Нужно еще {remaining} записей\n"
                )
        else:
            status_parts.append(
                "❌ Файл данных не найден\n"
                "💡 Запустите бота в режиме логгера на 48 часов\n"
            )

        status_parts.extend([
            "",
            "<b>💡 Рекомендации:</b>\n",
        ])

        if not data_status["exists"] or data_status["rows"] < 100:
            status_parts.append(
                "1. Подождите 48 часов для сбора данных\n"
                "2. Затем выполните /ai_train\n"
            )
        elif not model_info["is_trained"]:
            status_parts.append(
                "1. Выполните /ai_train для обучения\n"
                "2. После обучения используйте /ai_scan\n"
            )
        else:
            status_parts.append(
                "✅ Система готова к работе\n"
                "Используйте /ai_scan для поиска\n"
            )

        await update.message.reply_text(
            "".join(status_parts),
            parse_mode="HTML",
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка получения статуса:</b>\n\n{e}",
            parse_mode="HTML",
        )
        logger.exception("ai_status_failed", error=str(e))


async def ai_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_scan command - Run AI-powered smart scan.

    Performs a single scan using the Smart Scanner with AI validation.
    Finds and reports items with potential profit opportunities.

    Usage: /ai_scan [include_locked]
        include_locked - Include items with trade ban (default: no)
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_scan_command", user_id=user_id)

    # Parse arguments
    args = context.args or []
    include_locked = "locked" in " ".join(args).lower()

    await update.message.reply_text(
        "🔍 <b>Запуск AI-сканирования...</b>\n\n"
        f"📦 Включить предметы с локом: {'Да' if include_locked else 'Нет'}",
        parse_mode="HTML",
    )

    try:
        from src.ai.price_predictor import PricePredictor
        from src.dmarket.dmarket_api import DMarketAPI
        from src.dmarket.smart_scanner import SmartScanner, SmartScannerConfig

        # Get API client from context
        api = getattr(context.application, "dmarket_api", None)
        if not api:
            # Create new API client
            import os

            api = DMarketAPI(
                public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
                secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
            )

        # Initialize predictor
        predictor = PricePredictor()

        if not predictor.is_trained:
            await update.message.reply_text(
                "⚠️ AI модель не обучена.\n\n"
                "Выполните /ai_train сначала.",
                parse_mode="HTML",
            )
            return

        # Configure scanner
        config = SmartScannerConfig(
            allow_trade_ban=include_locked,
            max_lock_days=8 if include_locked else 0,
            min_profit_percent=15.0 if include_locked else 5.0,
            enable_ai=True,
            dry_run=True,  # Always dry run from Telegram
        )

        # Create scanner
        scanner = SmartScanner(api=api, predictor=predictor, config=config)

        # Run single scan
        results = await scanner.scan_once()

        # Filter profitable results
        opportunities = [r for r in results if r.should_buy]

        if not opportunities:
            await update.message.reply_text(
                "📭 <b>Результат сканирования:</b>\n\n"
                "Арбитражных возможностей не найдено.\n\n"
                f"Проанализировано предметов: {len(results)}",
                parse_mode="HTML",
            )
            return

        # Format results
        message_parts = [
            f"🎯 <b>Найдено {len(opportunities)} возможностей!</b>\n\n"
        ]

        for i, opp in enumerate(opportunities[:5], 1):  # Show top 5
            lock_info = f"⏳ Лок: {opp.lock_days}д" if opp.lock_days > 0 else "✅ Без лока"

            message_parts.append(
                f"<b>{i}. {opp.title[:50]}...</b>\n"
                f"💰 Цена: ${float(opp.market_price):.2f}\n"
                f"📈 Профит: +{opp.profit_percent:.1f}% (${float(opp.profit_usd):.2f})\n"
                f"{lock_info}\n"
                f"💡 {opp.reason}\n\n"
            )

        if len(opportunities) > 5:
            message_parts.append(
                f"<i>...и еще {len(opportunities) - 5} возможностей</i>\n"
            )

        await update.message.reply_text(
            "".join(message_parts),
            parse_mode="HTML",
        )

        logger.info(
            "ai_scan_completed",
            user_id=user_id,
            opportunities=len(opportunities),
            include_locked=include_locked,
        )

    except ImportError as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка:</b> Отсутствуют зависимости.\n\n{e}",
            parse_mode="HTML",
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка сканирования:</b>\n\n{e}",
            parse_mode="HTML",
        )
        logger.exception("ai_scan_failed", error=str(e))


async def ai_analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_analyze command - Analyze specific item with trade ban.

    Provides detailed analysis of an item to determine if it's worth
    buying even with a trade lock.

    Usage: /ai_analyze <item_name>
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # Get item name from arguments
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "📝 <b>Использование:</b>\n\n"
            "/ai_analyze &lt;название предмета&gt;\n\n"
            "<b>Пример:</b>\n"
            "/ai_analyze AK-47 | Redline (Field-Tested)",
            parse_mode="HTML",
        )
        return

    item_name = " ".join(args)
    logger.info("ai_analyze_command", user_id=user_id, item=item_name)

    await update.message.reply_text(
        f"🔍 <b>Анализирую предмет:</b>\n\n"
        f"<code>{item_name}</code>",
        parse_mode="HTML",
    )

    try:
        from src.ai.price_predictor import PricePredictor

        predictor = PricePredictor()

        if not predictor.is_trained:
            await update.message.reply_text(
                "⚠️ AI модель не обучена.\n\n"
                "Выполните /ai_train сначала.",
                parse_mode="HTML",
            )
            return

        # Get raw prediction
        raw_price = predictor.get_raw_prediction(item_name)

        if raw_price is None:
            await update.message.reply_text(
                "❌ <b>Предмет не найден в базе AI</b>\n\n"
                "Этот предмет не встречался в данных обучения.\n"
                "Подождите пока бот соберет больше данных.",
                parse_mode="HTML",
            )
            return

        # Build analysis message
        message = (
            f"🤖 <b>AI Анализ предмета</b>\n\n"
            f"📦 <b>Предмет:</b>\n<code>{item_name}</code>\n\n"
            f"💵 <b>AI Справедливая цена:</b> ${raw_price:.2f}\n\n"
            f"<b>💡 Рекомендации:</b>\n"
            f"• Если рыночная цена ниже ${raw_price * 0.95:.2f} - покупка выгодна\n"
            f"• Если выше ${raw_price * 1.05:.2f} - переплата\n\n"
            f"⚠️ <i>AI предсказание не гарантирует прибыль</i>"
        )

        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка анализа:</b>\n\n{e}",
            parse_mode="HTML",
        )
        logger.exception("ai_analyze_failed", error=str(e))


async def ai_collect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_collect command - Collect real market data for AI training.

    Fetches real price data from DMarket API and saves it to CSV for training.
    This ensures the AI model is trained on real market prices, not demo data.

    Usage: /ai_collect [count]
        count - Number of items to collect (default: 500, max: 2000)
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_collect_command", user_id=user_id)

    # Parse arguments
    args = context.args or []
    try:
        item_count = min(int(args[0]), 2000) if args else 500
    except (ValueError, IndexError):
        item_count = 500

    await update.message.reply_text(
        f"📥 <b>Сбор реальных данных с DMarket...</b>\n\n"
        f"🎯 Цель: {item_count} предметов\n"
        f"⏳ Это может занять несколько минут.",
        parse_mode="HTML",
    )

    try:
        import os

        from src.dmarket.dmarket_api import DMarketAPI
        from src.dmarket.market_data_logger import MarketDataLogger, MarketDataLoggerConfig

        # Get or create API client
        api = getattr(context.application, "dmarket_api", None)
        if not api:
            api = DMarketAPI(
                public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
                secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
            )

        # Configure logger for real data collection
        config = MarketDataLoggerConfig(
            output_path="data/market_history.csv",
            max_items_per_scan=min(item_count, 100),  # API limit per request
            games=["a8db", "tf2", "dota2", "rust"],  # All supported games
            min_price_cents=50,  # $0.50 minimum
            max_price_cents=100000,  # $1000 maximum
        )

        data_logger = MarketDataLogger(api, config)

        # Collect data in batches
        total_collected = 0
        batches_needed = (item_count + 99) // 100  # Round up

        for batch in range(batches_needed):
            collected = await data_logger.log_market_data()
            total_collected += collected

            if batch % 5 == 0 and batch > 0:
                await update.message.reply_text(
                    f"📊 Прогресс: {total_collected}/{item_count} предметов",
                    parse_mode="HTML",
                )

        # Get final data status
        data_status = data_logger.get_data_status()

        result_msg = (
            f"✅ <b>Сбор данных завершен!</b>\n\n"
            f"📈 Собрано записей: {total_collected}\n"
            f"📄 Всего в базе: {data_status['rows']}\n\n"
        )

        if data_status["ready_for_training"]:
            result_msg += (
                "✅ <b>Данных достаточно для обучения!</b>\n\n"
                "Выполните /ai_train чтобы обучить модель на реальных ценах."
            )
        else:
            remaining = 100 - data_status["rows"]
            result_msg += (
                f"⏳ Нужно еще {remaining} записей.\n"
                f"Выполните /ai_collect еще раз."
            )

        await update.message.reply_text(result_msg, parse_mode="HTML")

        logger.info(
            "ai_collect_completed",
            user_id=user_id,
            collected=total_collected,
            total_rows=data_status["rows"],
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка сбора данных:</b>\n\n{e}",
            parse_mode="HTML",
        )
        logger.exception("ai_collect_failed", error=str(e))


async def ai_train_real_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_train_real command - Train AI on real market prices.

    This command:
    1. Collects fresh data from DMarket API
    2. Trains the model on real prices
    3. Saves the trained model

    Usage: /ai_train_real [samples]
        samples - Number of samples to collect before training (default: 500)
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_train_real_command", user_id=user_id)

    # Parse arguments
    args = context.args or []
    try:
        sample_count = min(int(args[0]), 2000) if args else 500
    except (ValueError, IndexError):
        sample_count = 500

    await update.message.reply_text(
        f"🤖 <b>Обучение AI на реальных ценах</b>\n\n"
        f"📥 Шаг 1/2: Сбор {sample_count} реальных цен...",
        parse_mode="HTML",
    )

    try:
        import os

        from src.ai.price_predictor import PricePredictor
        from src.dmarket.dmarket_api import DMarketAPI
        from src.dmarket.market_data_logger import MarketDataLogger, MarketDataLoggerConfig

        # Get or create API client
        api = getattr(context.application, "dmarket_api", None)
        if not api:
            api = DMarketAPI(
                public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
                secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
            )

        # Step 1: Collect real data
        config = MarketDataLoggerConfig(
            output_path="data/market_history.csv",
            max_items_per_scan=100,
            games=["a8db", "tf2", "dota2", "rust"],
            min_price_cents=50,
            max_price_cents=100000,
        )

        data_logger = MarketDataLogger(api, config)

        total_collected = 0
        batches_needed = (sample_count + 99) // 100

        for batch in range(batches_needed):
            collected = await data_logger.log_market_data()
            total_collected += collected

        data_status = data_logger.get_data_status()

        await update.message.reply_text(
            f"📊 Собрано {total_collected} записей (всего: {data_status['rows']})\n\n"
            f"🧠 Шаг 2/2: Обучение модели...",
            parse_mode="HTML",
        )

        # Step 2: Train model
        predictor = PricePredictor()
        result = predictor.train_model(force_retrain=True)

        await update.message.reply_text(
            f"🤖 <b>Обучение на реальных ценах завершено!</b>\n\n{result}",
            parse_mode="HTML",
        )

        logger.info(
            "ai_train_real_completed",
            user_id=user_id,
            collected=total_collected,
            result=result,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Ошибка:</b>\n\n{e}",
            parse_mode="HTML",
        )
        logger.exception("ai_train_real_failed", error=str(e))


# ============================================================================
# Helper functions for ai_train_liquid_command (Phase 2 refactoring)
# ============================================================================


async def _init_liquid_training_components(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """Initialize filters and API clients for liquid training.

    Returns:
        Tuple of (whitelist_checker, blacklist_filter, waxpeer_api, dmarket_api)
    """
    import os

    from src.dmarket.blacklist_filters import ItemBlacklistFilter
    from src.dmarket.dmarket_api import DMarketAPI
    from src.dmarket.whitelist_config import WhitelistChecker

    whitelist_checker = WhitelistChecker(enable_priority_boost=True, profit_boost_percent=2.0)
    blacklist_filter = ItemBlacklistFilter(
        enable_keyword_filter=True,
        enable_float_filter=True,
        enable_sticker_boost_filter=True,
        enable_pattern_filter=True,
        enable_scam_risk_filter=True,
    )

    # Try to import Waxpeer API (optional)
    waxpeer_api = None
    try:
        from src.waxpeer.waxpeer_api import WaxpeerAPI

        waxpeer_key = os.getenv("WAXPEER_API_KEY", "")
        if waxpeer_key:
            waxpeer_api = WaxpeerAPI(api_key=waxpeer_key)
    except ImportError:
        logger.warning("waxpeer_api_not_available")

    # Get or create DMarket API client
    dmarket_api = getattr(context.application, "dmarket_api", None)
    if not dmarket_api:
        dmarket_api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
            secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
        )

    return whitelist_checker, blacklist_filter, waxpeer_api, dmarket_api


async def _calculate_item_liquidity(
    item: dict,
    whitelist_checker: Any,
    blacklist_filter: Any,
    waxpeer_api: Any,
) -> tuple[int, bool, float | None, int]:
    """Calculate liquidity score for an item.

    Returns:
        Tuple of (liquidity_score, is_whitelisted, waxpeer_price, waxpeer_count)
    """
    item_title = item.get("title", "")
    dmarket_price = float(item.get("price", {}).get("USD", 0)) / 100

    # Skip items under $1
    if dmarket_price < 1.0:
        return -1, False, None, 0

    # Check Blacklist (MANDATORY)
    if blacklist_filter.is_blacklisted(item):
        return -2, False, None, 0

    liquidity_score = 0
    is_whitelisted = False

    # Check Whitelist (PRIORITY BOOST)
    if whitelist_checker.is_whitelisted(item, "csgo"):
        liquidity_score += 25
        is_whitelisted = True

    # Check DMarket offers count
    dmarket_offers = item.get("extra", {}).get("offers_count", 0)
    if dmarket_offers >= 3:
        liquidity_score += 25

    # Check suggested price exists
    suggested_price = item.get("suggestedPrice", {}).get("USD")
    if suggested_price:
        liquidity_score += 25

    # Check on Waxpeer if available
    waxpeer_price = None
    waxpeer_count = 0
    if waxpeer_api:
        try:
            async with waxpeer_api:
                price_info = await waxpeer_api.get_item_price_info(item_title)
                if price_info and price_info.count >= 5:
                    liquidity_score += 25
                    waxpeer_price = float(price_info.price_usd)
                    waxpeer_count = price_info.count
        except Exception as e:
            logger.debug("waxpeer_check_failed", item=item_title, error=str(e))

    # Popular items have category
    category = item.get("extra", {}).get("category", "")
    if category and category != "Other":
        liquidity_score += 15

    return liquidity_score, is_whitelisted, waxpeer_price, waxpeer_count


def _save_liquid_data_to_csv(liquid_items: list[dict], output_path: Path) -> None:
    """Save liquid items to CSV file."""
    import csv

    if not liquid_items:
        return

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=liquid_items[0].keys())
        writer.writeheader()
        writer.writerows(liquid_items)


def _train_model_on_liquid_data(liquid_items: list[dict]) -> str:
    """Train the price prediction model on liquid items data.

    Returns:
        Training result message
    """
    import csv
    from pathlib import Path

    from src.ai.price_predictor import PricePredictor

    predictor = PricePredictor()

    if len(liquid_items) < 50:
        return "⚠️ Недостаточно ликвидных данных для обучения (минимум 50)"

    # Save to standard path for training
    main_data_path = Path("data/market_history.csv")

    with open(main_data_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_name",
                "price",
                "float_value",
                "is_stat_trak",
                "game_id",
                "timestamp",
            ],
        )
        writer.writeheader()
        for item in liquid_items:
            writer.writerow({
                "item_name": item["item_name"],
                "price": item["price"],
                "float_value": item["float_value"],
                "is_stat_trak": item["is_stat_trak"],
                "game_id": item["game_id"],
                "timestamp": item["timestamp"],
            })

    return predictor.train_model(force_retrain=True)


# ============================================================================
# End of helper functions
# ============================================================================


async def ai_train_liquid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai_train_liquid command - Train AI only on liquid items.

    Phase 2 Refactoring: Logic split into helper functions.
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("ai_train_liquid_command", user_id=user_id)

    # Parse arguments
    args = context.args or []
    try:
        target_samples = min(int(args[0]), 1000) if args else 300
    except (ValueError, IndexError):
        target_samples = 300

    await update.message.reply_text(
        f"🤖 <b>Обучение AI на ликвидных предметах</b>\n\n"
        f"🎯 Цель: {target_samples} ликвидных предметов\n\n"
        f"⏳ Это может занять несколько минут...",
        parse_mode="HTML",
    )

    try:
        from datetime import datetime
        from pathlib import Path

        from src.dmarket.blacklist_filters import BLACKLIST_KEYWORDS, PATTERN_KEYWORDS
        from src.dmarket.whitelist_config import WHITELIST_ITEMS

        # Initialize components (Phase 2 - use helper)
        (
            whitelist_checker, blacklist_filter, waxpeer_api, dmarket_api
        ) = await _init_liquid_training_components(context)

        output_path = Path("data/liquid_items.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        await update.message.reply_text(
            f"🔍 Шаг 1/4: Получение предметов с DMarket...\n"
            f"📋 Whitelist: {sum(len(items) for items in WHITELIST_ITEMS.values())} | "
            f"🚫 Blacklist: {len(BLACKLIST_KEYWORDS) + len(PATTERN_KEYWORDS)}",
            parse_mode="HTML",
        )

        # Get items from DMarket
        dmarket_items = await dmarket_api.get_market_items(
            game="a8db", limit=500, price_from=100, price_to=50000,
        )
        items_list = dmarket_items.get("objects", [])
        total_scanned = len(items_list)

        await update.message.reply_text(
            f"📋 Найдено {total_scanned} предметов\n🔍 Шаг 2/4: Фильтрация...",
            parse_mode="HTML",
        )

        # Process items (Phase 2 - use helper for scoring)
        liquid_items: list[dict[str, Any]] = []
        blacklisted_count = 0
        whitelisted_count = 0

        for i, item in enumerate(items_list):
            if len(liquid_items) >= target_samples:
                break

            score, is_wl, waxpeer_price, waxpeer_count = await _calculate_item_liquidity(
                item, whitelist_checker, blacklist_filter, waxpeer_api
            )

            if score == -1:  # Too cheap
                continue
            if score == -2:  # Blacklisted
                blacklisted_count += 1
                continue
            if is_wl:
                whitelisted_count += 1

            min_score = 40 if is_wl else 50
            if score >= min_score:
                liquid_items.append({
                    "item_name": item.get("title", ""),
                    "price": float(item.get("price", {}).get("USD", 0)) / 100,
                    "float_value": item.get("extra", {}).get("float", 0),
                    "is_stat_trak": "StatTrak" in item.get("title", ""),
                    "game_id": "a8db",
                    "timestamp": datetime.now().isoformat(),
                    "liquidity_score": score,
                    "is_whitelisted": is_wl,
                    "dmarket_offers": item.get("extra", {}).get("offers_count", 0),
                    "waxpeer_price": waxpeer_price,
                    "waxpeer_count": waxpeer_count,
                })

            # Progress update every 100 items
            if (i + 1) % 100 == 0:
                await update.message.reply_text(
                    f"📊 {i + 1}/{len(items_list)} | ✅ {len(liquid_items)} liquid | 🚫 {blacklisted_count}",
                    parse_mode="HTML",
                )

        await update.message.reply_text(
            f"🔍 Шаг 3/4: Сохранение {len(liquid_items)} предметов...",
            parse_mode="HTML",
        )

        # Save to CSV (Phase 2 - use helper)
        _save_liquid_data_to_csv(liquid_items, output_path)

        await update.message.reply_text(
            "🧠 Шаг 4/4: Обучение модели...",
            parse_mode="HTML",
        )

        # Train model (Phase 2 - use helper)
        result = _train_model_on_liquid_data(liquid_items)

        summary = (
            f"🤖 <b>Обучение завершено!</b>\n\n"
            f"📊 Проверено: {total_scanned} | ✅ Ликвидных: {len(liquid_items)}\n"
            f"🚫 Blacklisted: {blacklisted_count} | 📋 Whitelist: {whitelisted_count}\n\n"
            f"<b>Результат:</b>\n{result}"
        )

        await update.message.reply_text(summary, parse_mode="HTML")

        logger.info(
            "ai_train_liquid_completed",
            user_id=user_id,
            total_scanned=total_scanned,
            liquid_count=len(liquid_items),
        )

    except Exception as e:
        logger.exception("ai_train_liquid_failed", error=str(e))
        await update.message.reply_text(
            "❌ <b>Ошибка:</b>\n\nПроизошла ошибка при обучении. "
            "Пожалуйста, попробуйте позже.",
            parse_mode="HTML",
        )


def register_ai_handlers(application: "Application") -> None:
    """Register AI-related command handlers.

    Args:
        application: Telegram Application instance
    """
    application.add_handler(CommandHandler("ai_train", ai_train_command))
    application.add_handler(CommandHandler("ai_status", ai_status_command))
    application.add_handler(CommandHandler("ai_scan", ai_scan_command))
    application.add_handler(CommandHandler("ai_analyze", ai_analyze_command))
    application.add_handler(CommandHandler("ai_collect", ai_collect_command))
    application.add_handler(CommandHandler("ai_train_real", ai_train_real_command))
    application.add_handler(CommandHandler("ai_train_liquid", ai_train_liquid_command))

    logger.info("AI handlers registered")
