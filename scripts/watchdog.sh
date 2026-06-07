#!/usr/bin/env bash
# =============================================================
# 24/7 Watchdog for DMarket Bot (v12.5)
# =============================================================
# This watchdog supervises the main trading bot. If the bot
# process dies, crashes, or hangs (no log activity for N min),
# the watchdog restarts it and notifies via Telegram.
#
# Usage:
#   ./watchdog.sh                  # start + supervise
#   ./watchdog.sh --once           # single check (for cron)
#
# State: writes the bot's child PID to /tmp/dmarket_bot.pid
# and heartbeat time to data/watchdog_heartbeat.txt.
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="/tmp/dmarket_bot.pid"
HB_FILE="${PROJECT_ROOT}/data/watchdog_heartbeat.txt"
LOG_FILE="${PROJECT_ROOT}/logs/watchdog.log"
HEARTBEAT_TIMEOUT_S=300   # 5 min without a log line = hung bot
RESTART_BACKOFF_S=30      # min wait between restarts
MAX_RESTARTS_PER_HOUR=10
SINGLE_CHECK=false

mkdir -p "${PROJECT_ROOT}/logs" "${PROJECT_ROOT}/data"

if [[ "${1:-}" == "--once" ]]; then
    SINGLE_CHECK=true
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

send_telegram() {
    local msg="$1"
    local token="${TELEGRAM_BOT_TOKEN:-}"
    local chat="${TELEGRAM_CHAT_ID:-}"
    if [[ -z "${token}" || -z "${chat}" || "${token}" == ROTATE_ME* ]]; then
        return 0
    fi
    curl -fsS -m 10 \
        -d "chat_id=${chat}" \
        -d "text=${msg}" \
        "https://api.telegram.org/bot${token}/sendMessage" >/dev/null 2>&1 || true
}

is_bot_alive() {
    if [[ ! -f "${PID_FILE}" ]]; then
        return 1
    fi
    local pid
    pid=$(cat "${PID_FILE}" 2>/dev/null || echo "")
    if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
        return 1
    fi
    # Make sure it's our bot (could be a recycled PID)
    local cmdline
    cmdline=$(ps -o args= -p "${pid}" 2>/dev/null || true)
    if [[ "${cmdline}" != *"src.__main__"* ]]; then
        return 1
    fi
    return 0
}

is_bot_responsive() {
    if [[ ! -f "${HB_FILE}" ]]; then
        return 1
    fi
    local last_ts
    last_ts=$(cat "${HB_FILE}" 2>/dev/null || echo 0)
    local now
    now=$(date +%s)
    local diff=$(( now - last_ts ))
    if (( diff > HEARTBEAT_TIMEOUT_S )); then
        return 1
    fi
    return 0
}

start_bot() {
    log "Starting DMarket bot..."
    cd "${PROJECT_ROOT}"
    # setsid so the bot survives this script exiting; redirect both
    # stdout+stderr to the bot's log; write its PID to PID_FILE.
    setsid bash -c '
        DRY_RUN="${DRY_RUN:-true}" \
        USE_V12_LOOP=true \
        exec python -m src.__main__ > /tmp/bot_dryrun/bot.log 2>&1 &
        echo $! > /tmp/dmarket_bot.pid
    '
    sleep 3
    if is_bot_alive; then
        log "Bot started successfully (PID $(cat ${PID_FILE}))"
        send_telegram "✅ DMarket bot restarted by watchdog (PID $(cat ${PID_FILE}))"
    else
        log "ERROR: bot failed to start"
        send_telegram "❌ DMarket bot FAILED to start"
    fi
}

kill_bot() {
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}" 2>/dev/null || echo "")
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            log "Killing bot (PID ${pid})..."
            kill -TERM "${pid}" 2>/dev/null || true
            sleep 5
            kill -KILL "${pid}" 2>/dev/null || true
        fi
        rm -f "${PID_FILE}"
    fi
    # Also clean the bot's own lock file
    rm -f "${PROJECT_ROOT}/bot.lock"
}

check_once() {
    if is_bot_alive; then
        if is_bot_responsive; then
            # All good
            return 0
        else
            log "Bot alive but unresponsive (no heartbeat for ${HEARTBEAT_TIMEOUT_S}s). Killing."
            send_telegram "⏰ Bot unresponsive for ${HEARTBEAT_TIMEOUT_S}s — restarting"
            kill_bot
            sleep "${RESTART_BACKOFF_S}"
            start_bot
        fi
    else
        log "Bot not running. Starting."
        send_telegram "🔄 Bot was down — restarting"
        start_bot
    fi
}

# Rate-limit restarts
RATE_FILE="/tmp/dmarket_bot.restarts"
COUNT_LAST_HOUR() {
    if [[ ! -f "${RATE_FILE}" ]]; then
        echo 0
        return
    fi
    local cutoff
    cutoff=$(($(date +%s) - 3600))
    awk -v c="${cutoff}" '$1 > c' "${RATE_FILE}" | wc -l
}

RECORD_RESTART() {
    date +%s >> "${RATE_FILE}"
    # Keep only last 24h
    local cutoff
    cutoff=$(($(date +%s) - 86400))
    awk -v c="${cutoff}" '$1 > c' "${RATE_FILE}" > "${RATE_FILE}.tmp" && mv "${RATE_FILE}.tmp" "${RATE_FILE}"
}

if ${SINGLE_CHECK}; then
    check_once
    exit 0
fi

# === Main loop ===
trap 'log "Watchdog terminated"; exit 0' SIGINT SIGTERM
log "Watchdog started. PID=$$"
while true; do
    count=$(COUNT_LAST_HOUR)
    if (( count >= MAX_RESTARTS_PER_HOUR )); then
        log "Too many restarts in the last hour (${count}). Backing off 10 min."
        send_telegram "🚨 Watchdog: ${count} restarts/hour — pausing 10min"
        sleep 600
        continue
    fi
    check_once
    RECORD_RESTART || true
    sleep 60
done
