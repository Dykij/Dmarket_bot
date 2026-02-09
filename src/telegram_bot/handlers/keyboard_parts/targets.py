"""Target (buy order) handlers for main keyboard."""

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)

def _get_dmarket_api(context: ContextTypes.DEFAULT_TYPE):
    return getattr(context.application, "dmarket_api", None)

async def targets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Создать таргет", callback_data="target_create")],
        [InlineKeyboardButton("🤖 Авто-таргеты", callback_data="target_auto")],
        [InlineKeyboardButton("📋 Мои таргеты", callback_data="target_list")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ]
    await query.edit_message_text("🎯 <b>ТАРГЕТЫ (Buy Orders)</b>\n\nВыберите действие:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def target_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔫 CS2", callback_data="target_game_csgo"), InlineKeyboardButton("🏠 Rust", callback_data="target_game_rust")],
        [InlineKeyboardButton("⚔️ Dota 2", callback_data="target_game_dota2"), InlineKeyboardButton("🎩 TF2", callback_data="target_game_tf2")],
        [InlineKeyboardButton("◀️ Назад", callback_data="targets_menu")],
    ]
    await query.edit_message_text("➕ <b>СОЗДАНИЕ ТАРГЕТА</b>\n\nШаг 1: Выберите игру:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def _delete_all_targets(dmarket_api: Any) -> int:
    deleted_count = 0
    for game in ["csgo", "dota2", "tf2", "rust"]:
        try:
            targets_response = await dmarket_api.get_user_targets(game=game)
            targets = targets_response.get("Items", [])
            target_ids = [t.get("TargetID") or t.get("targetId") for t in targets if t.get("TargetID") or t.get("targetId")]
            if target_ids:
                await dmarket_api.delete_targets(target_ids=target_ids)
                deleted_count += len(target_ids)
        except Exception:
            continue
    return deleted_count

async def target_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Анализирую...")
    await query.edit_message_text("🤖 <b>АВТО-ТАРГЕТЫ</b>\n\n⏳ Подбираю выгодные позиции...", parse_mode="HTML")
