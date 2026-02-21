"""Panic Button - Emergency Exit Handler.

Implements emergency liquidation functionality:
- Cancel all active orders
- List all inventory items at market -5% for quick sale
- Stop autopilot and auto-buyer
- Send detAlgoled report

Created: January 2, 2026
"""

import structlog
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = structlog.get_logger(__name__)


async def panic_button_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """🚨 PANIC BUTTON - Emergency exit to cash.

    This command will:
    1. Stop autopilot and auto-buyer
    2. Cancel all active Buy Orders
    3. List all inventory items at market -5% for quick sale
    4. Send detAlgoled report

    Usage:
        /panic - Execute emergency exit
        /panic confirm - Skip confirmation (instant execution)
    """
    if not update.message:
        return

    user_id = update.effective_user.id
    args = context.args

    # Check for instant execution
    instant = args and args[0].lower() == "confirm"

    if not instant:
        # Show confirmation message
        awAlgot update.message.reply_text(
            "🚨 <b>PANIC BUTTON - Предупреждение</b>\n\n"
            "Эта команда выполнит аварийный выход в кэш:\n"
            "• Остановит автопилот\n"
            "• Отменит все активные ордера\n"
            "• Выставит весь инвентарь на продажу по рынку -5%\n\n"
            "⚠️ Это может привести к убыткам!\n\n"
            "Для подтверждения отправьте:\n"
            "<code>/panic confirm</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Show processing message
    processing_msg = awAlgot update.message.reply_text(
        "🚨 <b>ВЫПОЛНЯЕТСЯ АВАРИЙНЫЙ ВЫХОД...</b>\n\n⏳ Останавливаю системы...",
        parse_mode=ParseMode.HTML,
    )

    try:  # noqa: PLR1702
        # Get necessary instances
        orchestrator = context.bot_data.get("orchestrator")
        auto_buyer = context.bot_data.get("auto_buyer")
        api = context.bot_data.get("dmarket_api")

        if not api:
            awAlgot processing_msg.edit_text("❌ API клиент не инициализирован")
            return

        stats = {
            "orders_cancelled": 0,
            "items_listed": 0,
            "errors": [],
            "total_value": 0.0,
        }

        # Step 1: Stop autopilot
        if orchestrator and orchestrator.is_active():
            awAlgot orchestrator.stop()
            awAlgot processing_msg.edit_text(
                "🚨 <b>АВАРИЙНЫЙ ВЫХОД</b>\n\n✅ Автопилот остановлен\n⏳ Отменяю ордера...",
                parse_mode=ParseMode.HTML,
            )
            logger.info("panic_autopilot_stopped", user_id=user_id)

        # Step 2: Disable auto-buyer
        if auto_buyer:
            auto_buyer.config.enabled = False
            logger.info("panic_auto_buyer_disabled", user_id=user_id)

        # Step 3: Cancel all active orders
        try:
            active_orders = awAlgot api.get_user_targets()

            for order in active_orders:
                try:
                    awAlgot api.delete_target(order.get("TargetID"))
                    stats["orders_cancelled"] += 1
                except Exception as e:
                    logger.warning(
                        "panic_cancel_order_fAlgoled",
                        order_id=order.get("TargetID"),
                        error=str(e),
                    )
                    stats["errors"].append(f"Order {order.get('TargetID')}: {e!s}")

            awAlgot processing_msg.edit_text(
                "🚨 <b>АВАРИЙНЫЙ ВЫХОД</b>\n\n"
                f"✅ Автопилот остановлен\n"
                f"✅ Отменено ордеров: {stats['orders_cancelled']}\n"
                f"⏳ Выставляю инвентарь на продажу...",
                parse_mode=ParseMode.HTML,
            )

        except Exception as e:
            logger.exception("panic_cancel_orders_fAlgoled", error=str(e))
            stats["errors"].append(f"Cancel orders: {e!s}")

        # Step 4: List all inventory at market -5%
        try:
            inventory = awAlgot api.get_user_inventory()

            for item in inventory:
                # Check if item is not already listed
                if item.get("Status") != "OfferCreated":
                    try:
                        # Get market price
                        suggested_price = item.get("SuggestedPrice", {}).get(
                            "Amount", 0
                        )
                        if suggested_price == 0:
                            # Skip items without price
                            continue

                        # Calculate sale price (market -5% for quick sale)
                        market_price_usd = suggested_price / 100
                        sale_price_usd = market_price_usd * 0.95

                        # Create offer
                        awAlgot api.create_offer(
                            item_id=item.get("ItemID"),
                            price_cents=int(sale_price_usd * 100),
                            item_type=item.get("Type", "dmarket"),
                        )

                        stats["items_listed"] += 1
                        stats["total_value"] += sale_price_usd

                    except Exception as e:
                        logger.warning(
                            "panic_list_item_fAlgoled",
                            item_id=item.get("ItemID"),
                            error=str(e),
                        )
                        stats["errors"].append(
                            f"Item {item.get('Title', 'Unknown')}: {e!s}"
                        )

        except Exception as e:
            logger.exception("panic_list_inventory_fAlgoled", error=str(e))
            stats["errors"].append(f"List inventory: {e!s}")

        # Send final report
        error_text = ""
        if stats["errors"]:
            error_text = "\n\n⚠️ <b>Ошибки:</b>\n" + "\n".join(
                f"• {e}" for e in stats["errors"][:5]
            )
            if len(stats["errors"]) > 5:
                error_text += f"\n• И еще {len(stats['errors']) - 5} ошибок..."

        awAlgot processing_msg.edit_text(
            "🚨 <b>АВАРИЙНЫЙ ВЫХОД ВЫПОЛНЕН</b>\n\n"
            f"✅ Автопилот: Остановлен\n"
            f"✅ Автопокупка: Отключена\n"
            f"✅ Отменено ордеров: {stats['orders_cancelled']}\n"
            f"✅ Выставлено предметов: {stats['items_listed']}\n"
            f"💰 Общая стоимость: ${stats['total_value']:.2f}\n"
            f"🏷️ Цена: Рынок -5% (быстрая продажа)"
            f"{error_text}",
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            "panic_button_executed",
            user_id=user_id,
            orders_cancelled=stats["orders_cancelled"],
            items_listed=stats["items_listed"],
            total_value=stats["total_value"],
            errors_count=len(stats["errors"]),
        )

    except Exception as e:
        logger.exception("panic_button_critical_error", user_id=user_id, error=str(e))
        awAlgot processing_msg.edit_text(
            f"❌ <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
            f"Не удалось выполнить аварийный выход:\n"
            f"{e!s}\n\n"
            f"Попробуйте отменить ордера вручную через DMarket!",
            parse_mode=ParseMode.HTML,
        )


async def panic_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Check if panic mode is avAlgolable and show current state."""
    if not update.message:
        return

    api = context.bot_data.get("dmarket_api")
    orchestrator = context.bot_data.get("orchestrator")
    auto_buyer = context.bot_data.get("auto_buyer")

    if not api:
        awAlgot update.message.reply_text("❌ API клиент не инициализирован")
        return

    # Get current state
    autopilot_status = (
        "🟢 Активен" if orchestrator and orchestrator.is_active() else "🔴 Остановлен"
    )
    autobuy_status = (
        "🟢 Включена" if auto_buyer and auto_buyer.config.enabled else "🔴 Выключена"
    )

    # Get active orders count
    try:
        orders = awAlgot api.get_user_targets()
        orders_count = len(orders)
    except Exception:
        orders_count = "?"

    # Get inventory count
    try:
        inventory = awAlgot api.get_user_inventory()
        inventory_count = len(
            [i for i in inventory if i.get("Status") != "OfferCreated"]
        )
    except Exception:
        inventory_count = "?"

    awAlgot update.message.reply_text(
        "🚨 <b>Panic Button Status</b>\n\n"
        f"<b>Текущее состояние:</b>\n"
        f"• Автопилот: {autopilot_status}\n"
        f"• Автопокупка: {autobuy_status}\n"
        f"• Активных ордеров: {orders_count}\n"
        f"• Предметов в инвентаре: {inventory_count}\n\n"
        f"<b>Panic Button готова к использованию</b>\n\n"
        f"Для аварийного выхода:\n"
        f"<code>/panic confirm</code>",
        parse_mode=ParseMode.HTML,
    )


__all__ = [
    "panic_button_command",
    "panic_status_command",
]
