"""Telegram handler для расширенных ордеров (Advanced Orders).

Реализует интерфейс для создания и управления ордерами с фильтрами:
- Float Value фильтры
- Pattern ID фильтры
- Doppler Phase фильтры
- Sticker фильтры

Команды:
/advanced_orders - меню расширенных ордеров
/float_order <item> <float_min> <float_max> <price> - создать float ордер
/templates - показать шаблоны ордеров
/create_template <name> - создать ордер из шаблона

Январь 2026
"""

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

# Состояния conversation
(
    SELECTING_ORDER_TYPE,
    ENTERING_ITEM_TITLE,
    ENTERING_FLOAT_RANGE,
    ENTERING_PRICE,
    CONFIRMING_ORDER,
) = range(5)


class AdvancedOrderHandler:
    """Handler для управления расширенными ордерами."""

    def __init__(self, advanced_order_manager=None, float_arbitrage=None):
        """Инициализация handler'а.

        Args:
            advanced_order_manager: Менеджер расширенных ордеров
            float_arbitrage: Модуль Float Value арбитража
        """
        self.order_manager = advanced_order_manager
        self.float_arbitrage = float_arbitrage

        logger.info("AdvancedOrderHandler initialized")

    async def show_advanced_orders_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Показать главное меню расширенных ордеров."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Float Order", callback_data="adv_order_float"),
                InlineKeyboardButton(
                    "💎 Doppler Order", callback_data="adv_order_doppler"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎨 Pattern Order", callback_data="adv_order_pattern"
                ),
                InlineKeyboardButton(
                    "🏷️ Sticker Order", callback_data="adv_order_sticker"
                ),
            ],
            [
                InlineKeyboardButton("📋 Шаблоны", callback_data="adv_order_templates"),
                InlineKeyboardButton(
                    "📈 Мои ордера", callback_data="adv_order_my_orders"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔍 Float Arbitrage", callback_data="adv_order_float_scan"
                ),
            ],
            [
                InlineKeyboardButton("❌ Закрыть", callback_data="adv_order_close"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "🎯 *Расширенные ордера*\n\n"
            "Создавайте ордера с фильтрами как на CS Float:\n\n"
            "• *Float Order* - фильтр по диапазону флоата\n"
            "• *Doppler Order* - фильтр по фазе Doppler\n"
            "• *Pattern Order* - фильтр по PAlgont Seed\n"
            "• *Sticker Order* - фильтр по стикерам\n\n"
            "Выберите тип ордера:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

        return SELECTING_ORDER_TYPE

    async def handle_order_type_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработать выбор типа ордера."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "adv_order_close":
            await query.edit_message_text("Меню закрыто.")
            return ConversationHandler.END

        if data == "adv_order_templates":
            return await self.show_templates(update, context)

        if data == "adv_order_my_orders":
            return await self.show_my_orders(update, context)

        if data == "adv_order_float_scan":
            return await self.scan_float_opportunities(update, context)

        if data == "adv_order_float":
            context.user_data["order_type"] = "float"
            text = (
                "📊 *Float Order*\n\n"
                "Введите название предмета:\n\n"
                "Пример: `AK-47 | Redline (Field-Tested)`"
            )
        elif data == "adv_order_doppler":
            context.user_data["order_type"] = "doppler"
            text = (
                "💎 *Doppler Order*\n\n"
                "Введите название ножа:\n\n"
                "Пример: `★ Karambit | Doppler (Factory New)`"
            )
        elif data == "adv_order_pattern":
            context.user_data["order_type"] = "pattern"
            text = (
                "🎨 *Pattern Order*\n\n"
                "Введите название предмета:\n\n"
                "Пример: `AK-47 | Case Hardened (Field-Tested)`"
            )
        elif data == "adv_order_sticker":
            context.user_data["order_type"] = "sticker"
            text = (
                "🏷️ *Sticker Order*\n\n"
                "Введите название предмета:\n\n"
                "Пример: `AK-47 | Redline`"
            )
        else:
            return SELECTING_ORDER_TYPE

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="adv_order_cancel")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ENTERING_ITEM_TITLE

    async def handle_item_title(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработать ввод названия предмета."""
        item_title = update.message.text.strip()
        context.user_data["item_title"] = item_title
        order_type = context.user_data.get("order_type", "float")

        if order_type == "float":
            text = (
                f"📊 *Float Order для:*\n`{item_title}`\n\n"
                "Введите диапазон флоата (мин макс):\n\n"
                "Примеры:\n"
                "• `0.15 0.155` - премиальный FT\n"
                "• `0.00 0.01` - лучший FN\n"
                "• `0.90 1.00` - Blackiimov BS"
            )
            next_state = ENTERING_FLOAT_RANGE

        elif order_type == "doppler":
            keyboard = [
                [
                    InlineKeyboardButton("Phase 1", callback_data="doppler_phase_1"),
                    InlineKeyboardButton("Phase 2", callback_data="doppler_phase_2"),
                ],
                [
                    InlineKeyboardButton("Phase 3", callback_data="doppler_phase_3"),
                    InlineKeyboardButton("Phase 4", callback_data="doppler_phase_4"),
                ],
                [
                    InlineKeyboardButton("💎 Ruby", callback_data="doppler_ruby"),
                    InlineKeyboardButton(
                        "💙 Sapphire", callback_data="doppler_sapphire"
                    ),
                ],
                [
                    InlineKeyboardButton("🖤 Black Pearl", callback_data="doppler_bp"),
                    InlineKeyboardButton("💚 Emerald", callback_data="doppler_emerald"),
                ],
                [InlineKeyboardButton("❌ Отмена", callback_data="adv_order_cancel")],
            ]

            await update.message.reply_text(
                f"💎 *Doppler Order для:*\n`{item_title}`\n\n" "Выберите фазу:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return ENTERING_FLOAT_RANGE  # Используем для выбора фазы

        elif order_type == "pattern":
            text = (
                f"🎨 *Pattern Order для:*\n`{item_title}`\n\n"
                "Введите PAlgont Seed (номера паттернов через пробел):\n\n"
                "Примеры Blue Gem:\n"
                "• AK-47 CH: `661 670 321 955`\n"
                "• Karambit CH: `387 269 463`"
            )
            next_state = ENTERING_FLOAT_RANGE

        elif order_type == "sticker":
            text = (
                f"🏷️ *Sticker Order для:*\n`{item_title}`\n\n"
                "Введите категорию стикеров:\n\n"
                "Примеры:\n"
                "• `Katowice 2014`\n"
                "• `Katowice 2015`\n"
                "• `Crown (Foil)`"
            )
            next_state = ENTERING_FLOAT_RANGE
        else:
            return SELECTING_ORDER_TYPE

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="adv_order_cancel")]
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return next_state

    async def handle_float_range(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработать ввод диапазона/параметров."""
        order_type = context.user_data.get("order_type", "float")

        if update.callback_query:
            # Обработка выбора фазы Doppler
            query = update.callback_query
            await query.answer()

            data = query.data
            if data == "adv_order_cancel":
                await query.edit_message_text("Создание ордера отменено.")
                return ConversationHandler.END

            if data.startswith("doppler_"):
                phase_map = {
                    "doppler_phase_1": "Phase 1",
                    "doppler_phase_2": "Phase 2",
                    "doppler_phase_3": "Phase 3",
                    "doppler_phase_4": "Phase 4",
                    "doppler_ruby": "Ruby",
                    "doppler_sapphire": "Sapphire",
                    "doppler_bp": "Black Pearl",
                    "doppler_emerald": "Emerald",
                }
                context.user_data["doppler_phase"] = phase_map.get(data, "Phase 1")

                text = (
                    f"💎 *Doppler {context.user_data['doppler_phase']}*\n"
                    f"Предмет: `{context.user_data['item_title']}`\n\n"
                    "Введите максимальную цену в USD:\n\n"
                    "Пример: `500`"
                )

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "❌ Отмена", callback_data="adv_order_cancel"
                        )
                    ]
                ]
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
                return ENTERING_PRICE

        # Обработка текстового ввода
        text = update.message.text.strip()

        if order_type == "float":
            try:
                parts = text.split()
                if len(parts) != 2:
                    raise ValueError("Need 2 values")
                float_min = float(parts[0])
                float_max = float(parts[1])

                if not (0 <= float_min < float_max <= 1):
                    raise ValueError("Invalid float range")

                context.user_data["float_min"] = float_min
                context.user_data["float_max"] = float_max

            except ValueError as e:
                await update.message.reply_text(
                    f"❌ Ошибка: {e}\n\nВведите два числа от 0 до 1, например: `0.15 0.155`",
                    parse_mode="Markdown",
                )
                return ENTERING_FLOAT_RANGE

        elif order_type == "pattern":
            try:
                paint_seeds = [int(x) for x in text.split()]
                if not paint_seeds:
                    raise ValueError("No patterns provided")
                context.user_data["paint_seeds"] = paint_seeds
            except ValueError:
                await update.message.reply_text(
                    "❌ Ошибка: введите номера паттернов через пробел\n\n"
                    "Пример: `661 670 321`",
                    parse_mode="Markdown",
                )
                return ENTERING_FLOAT_RANGE

        elif order_type == "sticker":
            context.user_data["sticker_category"] = text

        # Переход к вводу цены
        item_title = context.user_data.get("item_title", "Unknown")

        if order_type == "float":
            filter_text = f"Float: {context.user_data['float_min']:.3f} - {context.user_data['float_max']:.3f}"
        elif order_type == "pattern":
            filter_text = f"Patterns: {context.user_data['paint_seeds']}"
        elif order_type == "sticker":
            filter_text = f"Stickers: {context.user_data['sticker_category']}"
        else:
            filter_text = "Unknown"

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="adv_order_cancel")]
        ]

        await update.message.reply_text(
            f"📦 *Создание ордера*\n\n"
            f"Предмет: `{item_title}`\n"
            f"Фильтр: {filter_text}\n\n"
            "Введите максимальную цену в USD:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return ENTERING_PRICE

    async def handle_price(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработать ввод цены."""
        try:
            price = float(
                update.message.text.strip().replace("$", "").replace(",", ".")
            )
            if price <= 0:
                raise ValueError("Price must be positive")
            context.user_data["max_price"] = price
        except ValueError:
            await update.message.reply_text(
                "❌ Ошибка: введите положительное число\n\nПример: `55.50`",
                parse_mode="Markdown",
            )
            return ENTERING_PRICE

        return await self.show_confirmation(update, context)

    async def show_confirmation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Показать подтверждение ордера."""
        order_type = context.user_data.get("order_type", "float")
        item_title = context.user_data.get("item_title", "Unknown")
        max_price = context.user_data.get("max_price", 0)

        # Формируем описание фильтра
        if order_type == "float":
            float_min = context.user_data.get("float_min", 0)
            float_max = context.user_data.get("float_max", 1)
            filter_desc = f"Float: {float_min:.4f} - {float_max:.4f}"
        elif order_type == "doppler":
            phase = context.user_data.get("doppler_phase", "Unknown")
            filter_desc = f"Doppler: {phase}"
        elif order_type == "pattern":
            seeds = context.user_data.get("paint_seeds", [])
            filter_desc = f"Patterns: {seeds}"
        elif order_type == "sticker":
            category = context.user_data.get("sticker_category", "Unknown")
            filter_desc = f"Stickers: {category}"
        else:
            filter_desc = "Unknown"

        # Расчёт ожидаемой прибыли (примерный)
        commission = 0.05  # 5% DMarket
        estimated_sell = max_price * 1.2  # Примерная премия 20%
        estimated_profit = estimated_sell * (1 - commission) - max_price
        roi = (estimated_profit / max_price) * 100 if max_price > 0 else 0

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Подтвердить", callback_data="adv_order_confirm"
                ),
                InlineKeyboardButton("❌ Отмена", callback_data="adv_order_cancel"),
            ],
        ]

        text = (
            "🎯 *Подтверждение ордера*\n\n"
            f"📦 Предмет: `{item_title}`\n"
            f"🔍 Фильтр: {filter_desc}\n"
            f"💰 Макс. цена: ${max_price:.2f}\n\n"
            f"📊 *Оценка прибыли:*\n"
            f"• Ожидаемая продажа: ~${estimated_sell:.2f}\n"
            f"• Прибыль: ~${estimated_profit:.2f}\n"
            f"• ROI: ~{roi:.1f}%\n\n"
            "Создать ордер?"
        )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return CONFIRMING_ORDER

    async def handle_confirmation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработать подтверждение."""
        query = update.callback_query
        await query.answer()

        if query.data == "adv_order_cancel":
            await query.edit_message_text("❌ Создание ордера отменено.")
            return ConversationHandler.END

        if query.data == "adv_order_confirm":
            # Создаём ордер
            result = await self._create_order_from_context(context)

            if result.get("success"):
                await query.edit_message_text(
                    f"✅ *Ордер создан!*\n\n"
                    f"ID: `{result.get('target_id', 'N/A')}`\n"
                    f"Статус: Активен\n\n"
                    "Ордер будет выполнен автоматически при появлении подходящего предмета.",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    f"❌ *Ошибка создания ордера*\n\n"
                    f"Причина: {result.get('error', 'Unknown')}\n\n"
                    "Попробуйте снова с командой /advanced_orders",
                    parse_mode="Markdown",
                )

            return ConversationHandler.END

        return CONFIRMING_ORDER

    async def _create_order_from_context(
        self,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> dict[str, Any]:
        """Создать ордер из данных контекста."""
        if self.order_manager is None:
            return {"success": False, "error": "Order manager not initialized"}

        order_type = context.user_data.get("order_type", "float")
        item_title = context.user_data.get("item_title", "")
        max_price = context.user_data.get("max_price", 0)

        try:
            from src.dmarket.advanced_order_system import (
                AdvancedOrder,
                AdvancedOrderFilter,
                DopplerPhase,
            )
            from src.dmarket.models.target_enhancements import StickerFilter

            # Создаём фильтр в зависимости от типа
            if order_type == "float":
                filter_obj = AdvancedOrderFilter(
                    float_min=context.user_data.get("float_min"),
                    float_max=context.user_data.get("float_max"),
                )
            elif order_type == "doppler":
                phase_str = context.user_data.get("doppler_phase", "Phase 1")
                phase_map = {
                    "Phase 1": DopplerPhase.PHASE_1,
                    "Phase 2": DopplerPhase.PHASE_2,
                    "Phase 3": DopplerPhase.PHASE_3,
                    "Phase 4": DopplerPhase.PHASE_4,
                    "Ruby": DopplerPhase.RUBY,
                    "Sapphire": DopplerPhase.SAPPHIRE,
                    "Black Pearl": DopplerPhase.BLACK_PEARL,
                    "Emerald": DopplerPhase.EMERALD,
                }
                filter_obj = AdvancedOrderFilter(
                    phase=phase_map.get(phase_str, DopplerPhase.PHASE_1)
                )
            elif order_type == "pattern":
                filter_obj = AdvancedOrderFilter(
                    paint_seeds=context.user_data.get("paint_seeds", [])
                )
            elif order_type == "sticker":
                filter_obj = AdvancedOrderFilter(
                    sticker_filter=StickerFilter(
                        sticker_categories=[
                            context.user_data.get("sticker_category", "")
                        ],
                        min_stickers=1,
                    )
                )
            else:
                filter_obj = AdvancedOrderFilter()

            order = AdvancedOrder(
                item_title=item_title,
                max_price_usd=max_price,
                filter=filter_obj,
            )

            result = await self.order_manager.create_order(order)

            return {
                "success": result.success,
                "target_id": result.target_id,
                "error": result.message if not result.success else None,
            }

        except Exception as e:
            logger.exception(f"Error creating order: {e}")
            return {"success": False, "error": str(e)}

    async def show_templates(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Показать доступные шаблоны."""
        if self.order_manager is None:
            text = "❌ Order manager not initialized"
        else:
            templates = self.order_manager.list_templates()
            text = "📋 *Доступные шаблоны:*\n\n"

            for t in templates[:10]:  # Первые 10
                text += (
                    f"• *{t['name']}*\n"
                    f"  {t['description']}\n"
                    f"  База: ${t['base_price']:.2f}, Премия: x{t['expected_premium']:.1f}\n\n"
                )

            text += "\nИспользуйте /create_template <name> для создания"

        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="adv_order_back")],
        ]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        return SELECTING_ORDER_TYPE

    async def show_my_orders(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Показать мои активные ордера."""
        if self.order_manager is None:
            text = "❌ Order manager not initialized"
            orders = []
        else:
            orders = self.order_manager.get_active_orders()
            if orders:
                text = "📈 *Мои активные ордера:*\n\n"
                for i, order in enumerate(orders[:10], 1):
                    profit = order.calculate_expected_profit()
                    roi = order.calculate_roi()
                    text += (
                        f"{i}. *{order.item_title[:30]}*\n"
                        f"   💰 ${order.max_price_usd:.2f} → ${order.expected_sell_price or 0:.2f}\n"
                        f"   📊 Profit: ${profit:.2f} ({roi:.1f}%)\n\n"
                    )
            else:
                text = "📭 У вас нет активных расширенных ордеров."

        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="adv_order_back")],
        ]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        return SELECTING_ORDER_TYPE

    async def scan_float_opportunities(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Сканировать возможности арбитража на флоате."""
        query = update.callback_query
        await query.answer("🔍 Сканирование...")

        if self.float_arbitrage is None:
            await query.edit_message_text("❌ Float arbitrage module not initialized")
            return SELECTING_ORDER_TYPE

        try:
            opportunities = (
                await self.float_arbitrage.find_float_arbitrage_opportunities(
                    game="csgo",
                    min_price=10.0,
                    max_price=100.0,
                    limit=10,
                )
            )

            if opportunities:
                text = "🔍 *Float Arbitrage Opportunities:*\n\n"

                for opp in opportunities[:5]:
                    text += (
                        f"🎯 *{opp.item_title[:35]}*\n"
                        f"   Float: {opp.float_value:.4f} ({opp.quality.value})\n"
                        f"   ${opp.current_price_usd:.2f} → ${opp.expected_sell_price:.2f}\n"
                        f"   Profit: ${opp.profit_usd:.2f} ({opp.profit_percent:.1f}%)\n\n"
                    )
            else:
                text = "🔍 Возможности не найдены. Попробуйте позже."

        except Exception as e:
            logger.exception(f"Error scanning: {e}")
            text = f"❌ Ошибка сканирования: {e}"

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="adv_order_float_scan")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="adv_order_back")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return SELECTING_ORDER_TYPE

    async def cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Отменить операцию."""
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Операция отменена.")
        else:
            await update.message.reply_text("❌ Операция отменена.")

        context.user_data.clear()
        return ConversationHandler.END

    def get_conversation_handler(self) -> ConversationHandler:
        """Получить ConversationHandler для регистрации."""
        return ConversationHandler(
            entry_points=[
                CommandHandler("advanced_orders", self.show_advanced_orders_menu),
                CommandHandler("float_orders", self.show_advanced_orders_menu),
            ],
            states={
                SELECTING_ORDER_TYPE: [
                    CallbackQueryHandler(
                        self.handle_order_type_selection,
                        pattern="^adv_order_",
                    ),
                ],
                ENTERING_ITEM_TITLE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_item_title,
                    ),
                    CallbackQueryHandler(
                        self.cancel,
                        pattern="^adv_order_cancel$",
                    ),
                ],
                ENTERING_FLOAT_RANGE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_float_range,
                    ),
                    CallbackQueryHandler(
                        self.handle_float_range,
                        pattern="^doppler_",
                    ),
                    CallbackQueryHandler(
                        self.cancel,
                        pattern="^adv_order_cancel$",
                    ),
                ],
                ENTERING_PRICE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_price,
                    ),
                    CallbackQueryHandler(
                        self.cancel,
                        pattern="^adv_order_cancel$",
                    ),
                ],
                CONFIRMING_ORDER: [
                    CallbackQueryHandler(
                        self.handle_confirmation,
                        pattern="^adv_order_",
                    ),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CallbackQueryHandler(self.cancel, pattern="^adv_order_cancel$"),
            ],
            name="advanced_orders_conversation",
            persistent=False,
        )
