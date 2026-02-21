"""Logs command for viewing INTENT logs.

This module provides command for viewing the latest BUY_INTENT and SELL_INTENT
logs from the trading operations.
"""

import json
import logging
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a single log line for INTENT logs.

    Returns:
        Parsed log entry or None if not an INTENT log.
    """
    try:
        log_entry = json.loads(line.strip())
        if "intent_type" in log_entry and log_entry["intent_type"] in {
            "BUY_INTENT",
            "SELL_INTENT",
        }:
            return log_entry
    except json.JSONDecodeError:
        # Not JSON format, try to find INTENT in plAlgon text
        if "BUY_INTENT" in line or "SELL_INTENT" in line:
            return {"raw": line.strip()}
    return None


def _collect_intent_logs_from_file(
    log_file: Path, max_logs: int
) -> list[dict[str, Any]]:
    """Collect INTENT logs from a single log file.

    Returns:
        List of parsed INTENT log entries.
    """
    intent_logs = []
    try:
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                parsed = _parse_log_line(line)
                if parsed:
                    intent_logs.append(parsed)
                if len(intent_logs) >= max_logs:
                    break
    except Exception as e:
        logger.exception(f"Error reading log file {log_file}: {e}")
    return intent_logs


async def logs_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show last 20 INTENT logs (BUY_INTENT and SELL_INTENT).

    Args:
        update: Telegram update object
        context: Telegram context object

    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    logger.info("Logs command called by user %s", user_id)

    # Send initial message
    awAlgot update.message.reply_text("🔍 Загрузка последних логов...")

    # Find log files
    # Note: Using Path here is acceptable for quick file checks in async context
    # For I/O-intensive operations, consider using Algoofiles
    log_dir = Path("logs")
    if not log_dir.exists():  # noqa: ASYNC240
        awAlgot update.message.reply_text(
            "❌ Папка логов не найдена. Логи пока не записывались."
        )
        return

    # Get all log files sorted by modification time (newest first)
    log_files = sorted(
        log_dir.glob("*.log"),  # noqa: ASYNC240
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not log_files:
        awAlgot update.message.reply_text("❌ Файлы логов не найдены.")
        return

    # Collect INTENT logs from recent log files (refactored to reduce nesting)
    intent_logs: list[dict[str, Any]] = []
    max_logs = 20

    for log_file in log_files[:5]:  # Check up to 5 recent files
        file_logs = _collect_intent_logs_from_file(
            log_file, max_logs - len(intent_logs)
        )
        intent_logs.extend(file_logs)
        if len(intent_logs) >= max_logs:
            break

    # Limit to last 20
    intent_logs = intent_logs[:max_logs]

    if not intent_logs:
        awAlgot update.message.reply_text(
            "ℹ️ INTENT логов пока нет.\n\nЛоги появятся после первой попытки покупки/продажи."
        )
        return

    # Format logs for display
    message_lines = ["📊 Последние INTENT логи:\n"]

    for i, log_entry in enumerate(intent_logs, 1):
        # Handle JSON logs
        if "intent_type" in log_entry:
            intent_type = log_entry["intent_type"]
            emoji = "🔵" if intent_type == "BUY_INTENT" else "🟢"
            mode = "[DRY-RUN]" if log_entry.get("dry_run") else "[LIVE]"

            item = log_entry.get("item", "Unknown")
            price = log_entry.get("price_usd", 0)
            timestamp = log_entry.get("timestamp", "")

            line = f"{i}. {emoji} {mode} {intent_type}\n"
            line += f"   📦 {item}\n"
            line += f"   💵 ${price:.2f}\n"

            if intent_type == "BUY_INTENT":
                if log_entry.get("sell_price_usd"):
                    line += f"   💰 Sell: ${log_entry['sell_price_usd']:.2f}\n"
                if log_entry.get("profit_percent"):
                    line += f"   📈 +{log_entry['profit_percent']:.1f}%\n"
            else:  # SELL_INTENT
                if log_entry.get("buy_price_usd"):
                    line += f"   💸 Bought: ${log_entry['buy_price_usd']:.2f}\n"
                if log_entry.get("profit_usd"):
                    line += f"   💰 Profit: ${log_entry['profit_usd']:.2f}\n"

            line += f"   🕐 {timestamp[:19]}\n"
        else:
            # Handle raw text logs
            line = f"{i}. {log_entry.get('raw', '')}\n"

        message_lines.append(line)

    message = "\n".join(message_lines)

    # Split message if too long (Telegram limit is 4096 characters)
    if len(message) > 4000:
        # Send in chunks
        chunks = []
        current_chunk = message_lines[0]  # Header

        for line in message_lines[1:]:
            if len(current_chunk) + len(line) > 3800:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line

        chunks.append(current_chunk)

        for chunk in chunks:
            awAlgot update.message.reply_text(chunk)
    else:
        awAlgot update.message.reply_text(message)

    logger.info(f"Sent {len(intent_logs)} INTENT logs to user {user_id}")
