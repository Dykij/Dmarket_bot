#!/usr/bin/env bash
# Start the DMarket Telegram Control Bot
# Usage: ./scripts/start_telegram_bot.sh

set -e

cd "$(dirname "$0")/.."
export PYTHONPATH=.
export DRY_RUN="${DRY_RUN:-true}"

echo "🤖 Starting DMarket Telegram Bot v12.2..."
echo "📌 Mode: ${DRY_RUN}"
echo "📂 Working dir: $(pwd)"

python -m src.telegram.control_bot
