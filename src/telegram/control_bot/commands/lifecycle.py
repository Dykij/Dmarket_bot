"""
lifecycle.py — Welcome + help + settings.

Informational commands that don't touch state or external APIs.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command

from src.config import Config

from ..keyboards import get_main_keyboard
from ..resilience import safe_call

logger = logging.getLogger("TelegramControl.commands.lifecycle")
router = Router(name="telegram-control-lifecycle")


# ============================================================
# Welcome
# ============================================================
@router.message(Command("start"))
@safe_call
async def cmd_start(message):
    mode = "🧪 SIMULATION (DRY_RUN)" if Config.DRY_RUN else "💸 LIVE TRADING"
    text = (
        f"🤖 *DMarket Sniper v{Config.BOT_VERSION} — Control Center*\n\n"
        f"📌 *Mode:* {mode}\n"
        f"🎯 *Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"💵 *Min Spread:* {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"💼 *Max Position:* {Config.MAX_POSITION_RISK_PCT}% of balance\n\n"
        f"Use the buttons below or type /help for all commands."
    )
    await message.answer(text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
@safe_call
async def cmd_help(message):
    text = (
        "🆘 *Available Commands*\n\n"
        "*Control:*\n"
        "🚀 /start\\_bot — Start the sniping loop\n"
        "🛑 /stop\\_bot — Stop the sniping loop\n"
        "🔥 /panic — Emergency stop (kill switch)\n\n"
        "*Info:*\n"
        "💰 /balance — Real DMarket balance\n"
        "📊 /status — Bot state + equity\n"
        "📦 /inventory — Virtual inventory\n"
        "📈 /profits — Realized + unrealized P&L\n"
        "⚙️ /settings — View configuration\n\n"
        "*Actions:*\n"
        "🧪 /test `<item>` — Test arbitrage for an item\n"
        "🔄 /refresh — Refresh clocksync + caches\n"
        "⏰ /clock — View clock sync status\n"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


@router.message(Command("settings"))
@router.message(F.text == "⚙️ SETTINGS")
@safe_call
async def cmd_settings(message):
    text = (
        f"⚙️ *Configuration (v{Config.BOT_VERSION})*\n\n"
        f"*Risk:*\n"
        f"   Min spread: {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"   Min price: ${Config.MIN_PRICE_USD}\n"
        f"   Max price: ${Config.MAX_PRICE_USD}\n"
        f"   Max position: {Config.MAX_POSITION_RISK_PCT}%\n"
        f"   Max inventory: {Config.MAX_OPEN_INVENTORY} items\n\n"
        f"*Strategy:*\n"
        f"   Active: {Config.ACTIVE_STRATEGY}\n"
        f"   Game: {Config.GAME_ID}\n"
        f"   Fee rate: {Config.FEE_RATE*100:.1f}%\n\n"
        f"*v12.2 Defenses:*\n"
        f"   Wash trading: {Config.WASH_TRADING_DETECTION}\n"
        f"   Liquidity filter: {Config.USE_LIQUIDITY_FILTER}\n"
        f"   Min sales (liquidity): {Config.MIN_TOTAL_SALES}\n\n"
        f"*Mode:*\n"
        f"   DRY\\_RUN: `{Config.DRY_RUN}` {'🧪' if Config.DRY_RUN else '💸'}\n\n"
        f"💡 *Edit src/config.py to change settings, then restart bot.*"
    )
    await message.answer(text, reply_markup=get_main_keyboard())
