"""Info handlers for main keyboard (balance, inventory)."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _get_dmarket_api(context: ContextTypes.DEFAULT_TYPE):
    return getattr(context.application, "dmarket_api", None)


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        dmarket_api = _get_dmarket_api(context)
        if not dmarket_api:
            raise ValueError("API not initialized")
        balance_data = await dmarket_api.get_balance()
        usd = (
            float(balance_data.get("balance", 0))
            if isinstance(balance_data, dict)
            else 0.0
        )
        message = f"💰 <b>ВАШ БАЛАНС</b>\n\n💵 USD: <b>${usd:.2f}</b>"
    except Exception as e:
        message = f"❌ Ошибка: {e}"
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="show_balance")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        dmarket_api = _get_dmarket_api(context)
        if not dmarket_api:
            raise ValueError("API not initialized")
        inventory = await dmarket_api.get_user_inventory(limit=20)
        items = inventory.get("objects", [])
        if not items:
            message = "📦 <b>ИНВЕНТАРЬ</b>\n\nВаш инвентарь пуст."
        else:
            total_value = sum(
                float(i.get("price", {}).get("USD", 0)) / 100 for i in items
            )
            message = f"📦 <b>ИНВЕНТАРЬ ({len(items)} предметов)</b>\n\n💰 Общая стоимость: <b>${total_value:.2f}</b>\n\n"
            for i, item in enumerate(items[:10], 1):
                message += f"{i}. {item.get('title', '?')[:25]} — ${float(item.get('price', {}).get('USD', 0)) / 100:.2f}\n"
    except Exception as e:
        message = f"❌ Ошибка: {e}"
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="show_inventory")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )
