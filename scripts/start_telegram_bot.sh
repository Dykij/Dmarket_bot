#!/usr/bin/env bash
# Start the DMarket Telegram Control Bot
# Usage:
#   ./scripts/start_telegram_bot.sh                # start in foreground
#   nohup ./scripts/start_telegram_bot.sh &        # start in background
#   DRY_RUN=false ./scripts/start_telegram_bot.sh  # start in LIVE mode
#
# Robustness features (v12.2):
#   - Auto-detects project root (works from any cwd)
#   - Validates Python version (>= 3.11)
#   - Prefers local .venv python if present
#   - Validates .env has required vars
#   - Writes logs to logs/telegram_bot.log
#   - Writes PID to .run/telegram_bot.pid for clean shutdown
#   - Color-coded status messages

set -u  # Don't `set -e`: we want graceful error messages, not abrupt exits

# --- Colors (if terminal supports them) ---
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m' # No Color
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

info()    { printf "${BLUE}ℹ${NC}  %s\n" "$*"; }
ok()      { printf "${GREEN}✓${NC}  %s\n" "$*"; }
warn()    { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }
err()     { printf "${RED}✗${NC}  %s\n" "$*" >&2; }
header()  { printf "\n${BOLD}${BLUE}== %s ==${NC}\n" "$*"; }

# --- Project root auto-detection ---
PROJECT_ROOT=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Strategy 1: project root is parent of scripts/ (when running from project)
if [ -d "$SCRIPT_DIR/../src/telegram" ] && [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

# Strategy 2: check common locations
if [ -z "$PROJECT_ROOT" ]; then
    for candidate in \
        "/tmp/opencode/Dmarket_bot" \
        "$HOME/Dmarket_bot" \
        "$HOME/projects/Dmarket_bot" \
        "$HOME/repos/Dmarket_bot" \
        "$SCRIPT_DIR/../.."
    do
        if [ -d "$candidate/src/telegram" ] && [ -f "$candidate/pyproject.toml" ]; then
            PROJECT_ROOT="$candidate"
            break
        fi
    done
fi

# Strategy 3: walk up from cwd
if [ -z "$PROJECT_ROOT" ]; then
    dir="$(pwd)"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if [ -d "$dir/src/telegram" ] && [ -f "$dir/pyproject.toml" ]; then
            PROJECT_ROOT="$dir"
            break
        fi
        parent="$(dirname "$dir")"
        [ "$parent" = "$dir" ] && break
        dir="$parent"
    done
fi

if [ -z "$PROJECT_ROOT" ]; then
    err "Could not locate DMarket project root"
    err "Run this script from inside the project, or set DMARKET_BOT_ROOT=/path/to/Dmarket_bot"
    exit 1
fi

cd "$PROJECT_ROOT"
ok "Project root: $PROJECT_ROOT"

# --- Python interpreter selection ---
PYTHON_BIN=""
if [ -n "${DMARKET_PYTHON:-}" ] && [ -x "$DMARKET_PYTHON" ]; then
    PYTHON_BIN="$DMARKET_PYTHON"
elif [ -x "./.venv/bin/python" ]; then
    PYTHON_BIN="./.venv/bin/python"
elif [ -x "./venv/bin/python" ]; then
    PYTHON_BIN="./venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    err "No python interpreter found in PATH or .venv"
    exit 1
fi

info "Using Python: $($PYTHON_BIN --version 2>&1)"

# --- Python version check ---
PY_VERSION="$($PYTHON_BIN -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_MAJOR="$(echo "$PY_VERSION" | cut -d. -f1)"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    err "Python >= 3.11 required, found $PY_VERSION"
    exit 1
fi
ok "Python version: $PY_VERSION (>= 3.11)"

# --- .env validation ---
if [ ! -f ".env" ]; then
    err ".env file not found in $PROJECT_ROOT"
    err "Create one with TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY"
    exit 1
fi

# Check required vars are non-empty (without exposing values)
MISSING=()
for var in TELEGRAM_BOT_TOKEN TELEGRAM_ADMIN_ID DMARKET_PUBLIC_KEY DMARKET_SECRET_KEY; do
    val="$(grep -E "^${var}=" .env | cut -d= -f2- | tr -d '"' | tr -d "'")"
    if [ -z "$val" ]; then
        MISSING+=("$var")
    fi
done

if [ "${#MISSING[@]}" -gt 0 ]; then
    err "Missing/empty vars in .env: ${MISSING[*]}"
    exit 1
fi
ok ".env validated"

# --- DRY_RUN safety check ---
if [ -z "${DRY_RUN:-}" ]; then
    export DRY_RUN=true
    warn "DRY_RUN not set — defaulting to DRY_RUN=true (safe)"
fi

if [ "$DRY_RUN" = "true" ]; then
    MODE_STR="🧪 SIMULATION (DRY_RUN=true)"
else
    MODE_STR="💸 LIVE TRADING (DRY_RUN=false)"
    warn "LIVE mode: real money at risk!"
    # Confirm
    if [ -t 0 ] && [ -z "${CI:-}" ]; then
        read -p "Continue in LIVE mode? (type 'yes' to confirm): " confirm
        if [ "$confirm" != "yes" ]; then
            err "Aborted"
            exit 1
        fi
    fi
fi
ok "Mode: $MODE_STR"

# --- Logs and PID ---
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$PROJECT_ROOT/.run"
mkdir -p "$LOG_DIR" "$PID_DIR"
LOG_FILE="$LOG_DIR/telegram_bot.log"
PID_FILE="$PID_DIR/telegram_bot.pid"

# Check if another instance is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || echo '')"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        err "Bot is already running (PID=$OLD_PID). Stop it first: kill $OLD_PID"
        exit 1
    else
        warn "Stale PID file found (PID=$OLD_PID not running) — removing"
        rm -f "$PID_FILE"
    fi
fi

# --- Header ---
header "DMarket Telegram Control Bot v12.2"
printf "${BOLD}Project:${NC}  %s\n" "$PROJECT_ROOT"
printf "${BOLD}Mode:${NC}     %s\n" "$MODE_STR"
printf "${BOLD}Log file:${NC} %s\n" "$LOG_FILE"
printf "${BOLD}PID file:${NC} %s\n" "$PID_FILE"
printf "${BOLD}Python:${NC}   %s\n" "$PY_VERSION"
printf "\n"

# --- Cleanup on exit (only if we don't exec) ---
cleanup() {
    local exit_code=$?
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
    fi
    if [ $exit_code -ne 0 ] && [ $exit_code -ne 130 ] && [ $exit_code -ne 143 ]; then
        warn "Bot exited with code $exit_code — see $LOG_FILE for details"
    fi
}
trap cleanup EXIT INT TERM

# --- Run the bot ---
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1  # Don't buffer stdout — important for `tail -f` of logs
export TELEGRAM_BOT_PID_FILE="$PID_FILE"  # Tell python where the pid file is, so it can clean up on shutdown

info "Starting bot..."
echo $$ > "$PID_FILE"
ok "PID: $$ written to $PID_FILE"

# Run python as a child (NOT exec) so we can clean up the PID file via trap
"$PYTHON_BIN" -m src.telegram.control_bot
