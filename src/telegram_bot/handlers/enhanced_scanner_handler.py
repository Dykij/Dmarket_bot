"""Telegram handler для Enhanced Arbitrage Scanner.

Интерфейс для запуска продвинутого сканера арбитража через Telegram.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from src.dmarket.enhanced_arbitrage_scanner import EnhancedArbitrageScanner

logger = logging.getLogger(__name__)


async def show_enhanced_scanner_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Показать меню Enhanced Arbitrage Scanner."""
    keyboard = [
        [
            InlineKeyboardButton("🎯 CS:GO/CS2", callback_data="enhanced_scan_csgo"),
            InlineKeyboardButton("🎮 Dota 2", callback_data="enhanced_scan_dota2"),
        ],
        [
            InlineKeyboardButton("🔫 Rust", callback_data="enhanced_scan_rust"),
            InlineKeyboardButton("🎩 TF2", callback_data="enhanced_scan_tf2"),
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="enhanced_scan_settings"),
            InlineKeyboardButton("❓ Помощь", callback_data="enhanced_scan_help"),
        ],
        [InlineKeyboardButton("« Назад", callback_data="main_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🚀 <b>Enhanced Arbitrage Scanner</b>\n\n"
        "Продвинутый сканер с улучшениями:\n\n"
        "✅ <b>orderBy: best_discount</b> - приоритет лучшим скидкам\n"
        "✅ <b>External prices</b> - сравнение с Steam/CSGOFloat\n"
        "✅ <b>Sales history</b> - фильтрация падающих цен\n"
        "✅ <b>Smart liquidity</b> - анализ ликвидности\n"
        "✅ <b>Realistic thresholds</b> - порог 15-20%\n\n"
        "Выберите игру для сканирования:"
    )

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


async def handle_enhanced_scan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработать запуск enhanced сканирования."""
    query = update.callback_query
    await query.answer()

    # Извлекаем игру из callback_data
    game_map = {
        "enhanced_scan_csgo": ("csgo", "🎯 CS:GO/CS2"),
        "enhanced_scan_dota2": ("dota2", "🎮 Dota 2"),
        "enhanced_scan_rust": ("rust", "🔫 Rust"),
        "enhanced_scan_tf2": ("tf2", "🎩 TF2"),
    }

    game, game_name = game_map.get(query.data, ("csgo", "🎯 CS:GO/CS2"))

    # Отправляем уведомление о начале сканирования
    await query.edit_message_text(
        f"{game_name}\n\n"
        f"🔍 Запускаю Enhanced Arbitrage Scanner...\n"
        f"⏳ Это может занять 10-30 секунд\n\n"
        f"Анализирую:\n"
        f"• DMarket цены с orderBy=best_discount\n"
        f"• Внешние цены (Steam, CSGOFloat)\n"
        f"• Историю продаж\n"
        f"• Ликвидность предметов",
        parse_mode="HTML",
    )

    try:
        # Получаем API client из context
        dmarket_api = context.bot_data.get("dmarket_api")

        if not dmarket_api:
            await query.edit_message_text(
                "❌ Ошибка: API клиент недоступен\nПопробуйте позже или перезапустите бота.",
            )
            return

        # Создаем scanner
        scanner = EnhancedArbitrageScanner(
            api_client=dmarket_api,
            min_discount=15.0,  # Реалистичный порог
            enable_external_comparison=True,
            enable_sales_history=True,
        )

        # Запускаем сканирование
        game_ids = {
            "csgo": "a8db",
            "dota2": "9a92",
            "rust": "rust",
            "tf2": "tf2",
        }

        opportunities = await scanner.find_opportunities(
            game_id=game_ids.get(game, "a8db"),
            min_price=5.0,
            max_price=100.0,
            limit=10,
        )

        await scanner.close()

        # Формируем результат
        if not opportunities:
            await query.edit_message_text(
                f"{game_name}\n\n"
                f"❌ Не найдено арбитражных возможностей\n\n"
                f"Попробуйте:\n"
                f"• Снизить минимальный порог скидки\n"
                f"• Изменить ценовой диапазон\n"
                f"• Попробовать другую игру",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад", callback_data="enhanced_scanner_menu")]
                ]),
            )
            return

        # Формируем текст с результатами
        result_text = f"{game_name}\n\n🎯 <b>Найдено {len(opportunities)} возможностей</b>\n\n"

        for i, item in enumerate(opportunities[:5], 1):  # Показываем топ-5
            title = item.get("title", "Unknown")
            price = item.get("price_usd", 0)
            suggested = item.get("suggested_usd", 0)
            discount = item.get("discount_percent", 0)
            score = item.get("opportunity_score", 0)

            result_text += f"<b>{i}. {title}</b>\n"
            result_text += f"💰 Цена: ${price:.2f}\n"
            result_text += f"📊 Рекомендуемая: ${suggested:.2f}\n"
            result_text += f"📉 Скидка: {discount:.1f}%\n"
            result_text += f"⭐ Score: {score:.1f}\n"

            # Информация о внешних ценах
            ext_arb = item.get("external_arbitrage")
            if ext_arb and ext_arb.get("has_opportunity"):
                platform = ext_arb.get("best_platform")
                ext_price = ext_arb.get("best_price")
                net_profit = ext_arb.get("net_profit")
                result_text += f"🌐 {platform}: ${ext_price:.2f} (профит: ${net_profit:.2f})\n"

            # Информация о ликвидности
            sales_volume = item.get("sales_volume")
            if sales_volume:
                result_text += f"📈 Продаж: {sales_volume}\n"

            result_text += "\n"

        result_text += (
            "💡 <i>Используйте /auto_buy для автоматической покупки</i>\n"
            "💡 <i>Или /targets для создания buy orders</i>"
        )

        keyboard = [
            [InlineKeyboardButton("🔄 Повторить сканирование", callback_data=query.data)],
            [InlineKeyboardButton("« Назад", callback_data="enhanced_scanner_menu")],
        ]

        await query.edit_message_text(
            text=result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Ошибка в enhanced сканировании: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при сканировании\n\n"
            f"Детали: {e!s}\n\n"
            f"Попробуйте позже или обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data="enhanced_scanner_menu")]
            ]),
        )


async def show_enhanced_scanner_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Показать помощь по Enhanced Scanner."""
    query = update.callback_query
    await query.answer()

    help_text = (
        "❓ <b>Enhanced Arbitrage Scanner - Помощь</b>\n\n"
        "<b>Что это?</b>\n"
        "Продвинутый сканер арбитража с реализацией лучших практик:\n\n"
        "<b>1. orderBy: best_discount</b>\n"
        "• API возвращает предметы с максимальной скидкой первыми\n"
        "• Это критически важно для быстрого нахождения выгодных сделок\n\n"
        "<b>2. External Price Comparison</b>\n"
        "• Сравнение цен с Steam Community Market\n"
        "• Сравнение с CSGOFloat (для CS:GO)\n"
        "• Расчет реального профита с учетом комиссий\n\n"
        "<b>3. Sales History Check</b>\n"
        "• Проверка истории продаж предмета\n"
        "• Фильтрация предметов с падающей ценой\n"
        "• Анализ ликвидности (объем продаж)\n\n"
        "<b>4. Smart Liquidity Filter</b>\n"
        "• Исключение souvenir/sticker/case предметов\n"
        "• Проверка trade lock (не более 7 дней)\n"
        "• Фильтрация манипулированных цен\n\n"
        "<b>5. Realistic Thresholds</b>\n"
        "• Минимальная скидка: 15% (вместо 30%)\n"
        "• Реальные шансы найти сделки\n"
        "• Профессиональные боты работают с 10-20%\n\n"
        "<b>💡 Советы:</b>\n"
        "• Лучшее время: 10:00-14:00 UTC (пик активности)\n"
        "• Средние цены ($5-$30) более ликвидны\n"
        "• Проверяйте external arbitrage для кросс-платформенных сделок\n"
        "• Используйте auto_buy для мгновенной покупки"
    )

    keyboard = [[InlineKeyboardButton("« Назад", callback_data="enhanced_scanner_menu")]]

    await query.edit_message_text(
        text=help_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# Alias для совместимости с register_all_handlers.py
handle_enhanced_scan_help = show_enhanced_scanner_help


async def handle_enhanced_scan_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Показать настройки Enhanced Scanner."""
    query = update.callback_query
    await query.answer()

    settings_text = (
        "⚙️ <b>Настройки Enhanced Scanner</b>\n\n"
        "<b>Текущие параметры:</b>\n"
        "• Мин. скидка: 15%\n"
        "• Мин. цена: $5.00\n"
        "• Макс. цена: $100.00\n"
        "• Лимит результатов: 10\n"
        "• Внешнее сравнение: ✅\n"
        "• История продаж: ✅\n\n"
        "<i>Настройки можно изменить в конфигурации бота.</i>"
    )

    keyboard = [[InlineKeyboardButton("« Назад", callback_data="enhanced_scanner_menu")]]

    await query.edit_message_text(
        text=settings_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


def register_enhanced_scanner_handlers(application, bot_instance) -> None:
    """Зарегистрировать handlers для Enhanced Scanner.

    Args:
        application: Telegram Application instance
        bot_instance: DMarketTelegramBot instance for API access
    """
    # Store bot_instance in bot_data for handlers
    application.bot_data["bot_instance"] = bot_instance

    application.add_handler(
        CallbackQueryHandler(
            show_enhanced_scanner_menu,
            pattern="^enhanced_scanner_menu$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_enhanced_scan,
            pattern="^enhanced_scan_(csgo|dota2|rust|tf2)$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            show_enhanced_scanner_help,
            pattern="^enhanced_scan_help$",
        )
    )

    logger.info("✅ Enhanced Scanner handlers registered")
