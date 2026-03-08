"""ML/Algo handlers for main keyboard."""

from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


async def ml_Algo_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎓 Обучить модель", callback_data="ml_Algo_train")],
        [InlineKeyboardButton("📊 Статус Algo", callback_data="ml_Algo_status")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ]
    text = "🧠 <b>ML/Algo ОБУЧЕНИЕ</b>\n\nИспользуйте машинное обучение для предсказания цен."
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def ml_Algo_status_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    project_root = Path(__file__).resolve().parents[4]
    model_path = project_root / "data" / "price_model.pkl"
    if model_path.exists():
        text = f"🧠 <b>Статус ML/Algo</b>\n\n✅ <b>Модель обучена</b>\n💾 Размер: {model_path.stat().st_size / 1024:.1f} KB"
    else:
        text = "🧠 <b>Статус ML/Algo</b>\n\n❌ <b>Модель не обучена</b>"
    keyboard = [
        [InlineKeyboardButton("🎓 Обучить", callback_data="ml_Algo_train")],
        [InlineKeyboardButton("◀️ Назад", callback_data="ml_Algo_menu")],
    ]
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
    )
