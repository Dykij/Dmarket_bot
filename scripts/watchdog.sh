#!/usr/bin/env bash
# =============================================================
# 24/7 Watchdog for DMarket Bot (v12.6 — exit-code aware)
# =============================================================
# This watchdog supervises the main trading bot. If the bot
# process dies, crashes, or hangs (no log activity for N min),
# the watchdog decides what to do based on the bot's exit code:
#
#   exit 0  → clean shutdown (don't restart)
#   exit 1+ → fatal error (don't restart; user must fix)
#   crash   → no exit code captured (process killed/hung); restart
#
# Usage:
#   ./watchdog.sh                  # start + supervise
#   ./watchdog.sh --once           # single check (for cron)
#   ./watchdog.sh --reset          # clear fatal state and restart
#
# State:
#   /tmp/dmarket_bot.pid             — bot's PID
#   data/watchdog_heartbeat.txt      — last heartbeat timestamp
#   data/watchdog_state.json         — last exit code (written by bot)
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="/tmp/dmarket_bot.pid"
HB_FILE="${PROJECT_ROOT}/data/watchdog_heartbeat.txt"
STATE_FILE="${PROJECT_ROOT}/data/watchdog_state.json"
LOG_FILE="${PROJECT_ROOT}/logs/watchdog.log"
HEARTBEAT_TIMEOUT_S=300   # 5 min without heartbeat = hung
RESTART_BACKOFF_S=30      # min wait between restarts
MAX_RESTARTS_PER_HOUR=10
SINGLE_CHECK=false
RESET_STATE=false

mkdir -p "${PROJECT_ROOT}/logs" "${PROJECT_ROOT}/data"

if [[ "${1:-}" == "--once" ]]; then
    SINGLE_CHECK=true
fi
if [[ "${1:-}" == "--reset" ]]; then
    RESET_STATE=true
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

read_last_exit_code() {
    # Reads the JSON state file the bot wrote on exit. Returns
    # the exit code, or empty string if no state file exists.
    if [[ ! -f "${STATE_FILE}" ]]; then
        return 1
    fi
    # Crude JSON parse — exit code is at "exit_code":N
    grep -oE '"exit_code"[[:space:]]*:[[:space:]]*-?[0-9]+' "${STATE_FILE}" \
        | grep -oE -- '-?[0-9]+$' || return 1
}

clear_state() {
    rm -f "${STATE_FILE}"
}

start_bot() {
    log "Starting DMarket bot..."
    cd "${PROJECT_ROOT}"
    clear_state
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

# --- main per-check decision tree ---
check_once() {
    if is_bot_alive; then
        # Bot is running. Check responsiveness.
        if is_bot_responsive; then
            return 0
        fi
        # Hung but alive → kill and restart (assume transient).
        log "Bot alive but unresponsive (no heartbeat for ${HEARTBEAT_TIMEOUT_S}s). Killing."
        send_telegram "⏰ Bot unresponsive for ${HEARTBEAT_TIMEOUT_S}s — restarting"
        kill_bot
        sleep "${RESTART_BACKOFF_S}"
        start_bot
        return 0
    fi

    # Bot is not running. Why?
    local last_exit
    last_exit=$(read_last_exit_code || echo "")
    if [[ -n "${last_exit}" ]] && (( last_exit > 0 )); then
        # Fatal: bot exited with non-zero code → user must fix.
        log "Bot is DOWN (last exit code = ${last_exit}, fatal). NOT restarting."
        send_telegram "🚨 Bot stopped with FATAL exit code ${last_exit}.
Inspect the log: /tmp/bot_dryrun/bot.log
Run './scripts/watchdog.sh --reset' once you've fixed the issue."
        return 1
    fi

    if [[ -n "${last_exit}" ]] && (( last_exit == 0 )); then
        log "Bot exited cleanly (code 0). Not restarting."
        return 0
    fi

    # No exit code captured → crash or external kill → restart.
    log "Bot not running (no exit code captured). Restarting."
    send_telegram "🔄 Bot was down (crash/kill) — restarting"
    start_bot
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

if ${RESET_STATE}; then
    log "Reset state file (cleared fatal-exit memory)"
    clear_state
    exit 0
fi

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
