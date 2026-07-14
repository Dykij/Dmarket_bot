#!/usr/bin/env bash
# start.sh — Start DMarket Bot with watchdog supervision
# Usage:
#   ./scripts/start.sh              # Start bot + watchdog in background
#   ./scripts/start.sh --bot-only   # Start only the bot (no watchdog)
#   ./scripts/start.sh --status     # Check if bot is running
#   ./scripts/start.sh --stop       # Stop bot + watchdog
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="/tmp/dmarket_bot.pid"
WD_PID_FILE="/tmp/dmarket_watchdog.pid"

cd "${PROJECT_ROOT}"

# Ensure log directories exist
mkdir -p logs logs/archive data

status() {
    local bot_running=false
    local wd_running=false

    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}" 2>/dev/null || echo "")
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            echo "✅ Bot running (PID ${pid})"
            bot_running=true
        fi
    fi
    if [[ -f "${WD_PID_FILE}" ]]; then
        local wpid
        wpid=$(cat "${WD_PID_FILE}" 2>/dev/null || echo "")
        if [[ -n "${wpid}" ]] && kill -0 "${wpid}" 2>/dev/null; then
            echo "✅ Watchdog running (PID ${wpid})"
            wd_running=true
        fi
    fi
    if ! ${bot_running}; then
        echo "❌ Bot not running"
    fi
    if ! ${wd_running}; then
        echo "❌ Watchdog not running"
    fi

    # Show log file sizes
    echo ""
    echo "📊 Log files:"
    du -sh logs/*.log 2>/dev/null || echo "  No log files"
    echo ""
    echo "💾 Databases:"
    du -sh data/*.db 2>/dev/null || echo "  No databases"
}

stop_all() {
    echo "Stopping bot..."
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}" 2>/dev/null || echo "")
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill -TERM "${pid}" 2>/dev/null || true
            sleep 3
            kill -KILL "${pid}" 2>/dev/null || true
            echo "  Bot stopped (PID ${pid})"
        fi
        rm -f "${PID_FILE}"
    fi

    echo "Stopping watchdog..."
    if [[ -f "${WD_PID_FILE}" ]]; then
        local wpid
        wpid=$(cat "${WD_PID_FILE}" 2>/dev/null || echo "")
        if [[ -n "${wpid}" ]] && kill -0 "${wpid}" 2>/dev/null; then
            kill -TERM "${wpid}" 2>/dev/null || true
            sleep 2
            echo "  Watchdog stopped (PID ${wpid})"
        fi
        rm -f "${WD_PID_FILE}"
    fi

    rm -f "${PROJECT_ROOT}/bot.lock"
    echo "All stopped."
}

case "${1:-}" in
    --status)
        status
        ;;
    --stop)
        stop_all
        ;;
    --bot-only)
        echo "Starting bot (no watchdog)..."
        export DRY_RUN="${DRY_RUN:-true}"
        export USE_V12_LOOP=true
        exec python -m src.__main__
        ;;
    *)
        echo "Starting DMarket Bot + Watchdog..."
        echo "  Log: logs/bot_24_7.log"
        echo "  Mode: DRY_RUN=${DRY_RUN:-true}"
        echo ""

        # Start watchdog in background (it will start the bot)
        nohup bash "${SCRIPT_DIR}/watchdog.sh" >> logs/watchdog.log 2>&1 &
        echo $! > "${WD_PID_FILE}"
        echo "Watchdog started (PID $(cat "${WD_PID_FILE}"))"

        sleep 5
        status
        echo ""
        echo "To follow logs: tail -f logs/bot_24_7.log"
        echo "To stop: ./scripts/start.sh --stop"
        ;;
esac
