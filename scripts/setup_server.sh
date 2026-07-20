#!/bin/bash
# setup_server.sh — One-click server setup for DMarket Bot dry run.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/YOUR_USER/Dmarket_bot-main/main/scripts/setup_server.sh | bash
#
# Or manual:
#   chmod +x scripts/setup_server.sh
#   sudo ./scripts/setup_server.sh
#
# Tested on: Ubuntu 22.04, Debian 12
# Requires: root or sudo

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[-]${NC} $1"; exit 1; }

# ─── Check root ───────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Run as root: sudo ./setup_server.sh"
fi

# ─── Configuration ────────────────────────────────────────────────
BOT_USER="dmarket"
BOT_DIR="/opt/dmarket-bot"
VENV_DIR="${BOT_DIR}/.venv"
LOG_DIR="/var/log/dmarket-bot"
DATA_DIR="${BOT_DIR}/data"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        DMarket Bot — Server Setup (CityHost NL)         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Step 1: System packages ──────────────────────────────────────
log "Updating system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev \
    git curl wget htop tmux sqlite3 \
    build-essential libssl-dev libffi-dev \
    > /dev/null 2>&1

log "Python version: $(python3.11 --version)"

# ─── Step 2: Create bot user ──────────────────────────────────────
if ! id -u "${BOT_USER}" &>/dev/null; then
    log "Creating user: ${BOT_USER}"
    useradd -m -s /bin/bash "${BOT_USER}"
else
    log "User ${BOT_USER} already exists"
fi

# ─── Step 3: Clone repository ─────────────────────────────────────
log "Setting up bot directory: ${BOT_DIR}"
mkdir -p "${BOT_DIR}"

if [[ -d "${BOT_DIR}/.git" ]]; then
    log "Repository exists, pulling latest..."
    cd "${BOT_DIR}"
    sudo -u "${BOT_USER}" git pull origin main
else
    log "Cloning repository..."
    sudo -u "${BOT_USER}" git clone https://github.com/YOUR_USER/Dmarket_bot-main.git "${BOT_DIR}"
fi

cd "${BOT_DIR}"

# ─── Step 4: Python virtual environment ───────────────────────────
log "Creating Python virtual environment..."
sudo -u "${BOT_USER}" python3.11 -m venv "${VENV_DIR}"
sudo -u "${BOT_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools -q

log "Installing dependencies..."
sudo -u "${BOT_USER}" "${VENV_DIR}/bin/pip" install -r requirements.txt -q 2>/dev/null || \
sudo -u "${BOT_USER}" "${VENV_DIR}/bin/pip" install -e . -q 2>/dev/null || \
warn "Some dependencies may need manual installation"

# ─── Step 5: Create directories ───────────────────────────────────
log "Creating directories..."
mkdir -p "${LOG_DIR}" "${DATA_DIR}"
chown -R "${BOT_USER}:${BOT_USER}" "${BOT_DIR}" "${LOG_DIR}"

# ─── Step 6: Environment file ─────────────────────────────────────
ENV_FILE="${BOT_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    log "Creating .env file..."
    cat > "${ENV_FILE}" << 'EOF'
# ═══════════════════════════════════════════════════════════
# DMarket Bot — Environment Configuration
# ═══════════════════════════════════════════════════════════

# Mode
DRY_RUN=true
LOG_LEVEL=INFO
LOG_TO_FILE=true

# Telegram Notifications (REQUIRED for dry run reports)
TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE

# DMarket API (optional for dry run)
DMARKET_PUBLIC_KEY=
DMARKET_SECRET_KEY=

# Dry Run Settings
DRY_RUN_DURATION=336
REPORT_INTERVAL=90

# Balance (dry run fallback)
DRY_RUN_BALANCE_FALLBACK=1000.0
EOF
    chown "${BOT_USER}:${BOT_USER}" "${ENV_FILE}"
    warn "Edit .env file with your Telegram credentials:"
    warn "  nano ${ENV_FILE}"
else
    log ".env file already exists"
fi

# ─── Step 7: Systemd service ──────────────────────────────────────
log "Creating systemd service..."

cat > /etc/systemd/system/dmarket-dryrun.service << EOF
[Unit]
Description=DMarket Bot — 14-Day Dry Run
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USER}
Group=${BOT_USER}
WorkingDirectory=${BOT_DIR}
Environment=PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python tests/sandbox/dry_run_14d.py
Restart=on-failure
RestartSec=30
StandardOutput=append:${LOG_DIR}/dry_run_stdout.log
StandardError=append:${LOG_DIR}/dry_run_stderr.log

# Resource limits
MemoryMax=3G
CPUQuota=200%

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${BOT_DIR} ${LOG_DIR}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
log "Systemd service created: dmarket-dryrun.service"

# ─── Step 8: Log rotation ─────────────────────────────────────────
log "Setting up log rotation..."
cat > /etc/logrotate.d/dmarket-bot << EOF
${LOG_DIR}/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ${BOT_USER} ${BOT_USER}
    postrotate
        systemctl reload dmarket-dryrun.service 2>/dev/null || true
    endscript
}
EOF

# ─── Step 9: SQLite optimization ──────────────────────────────────
log "Optimizing SQLite settings..."
cat >> "${BOT_DIR}/.env" << 'EOF'

# SQLite Optimization
SQLITE_CACHE_SIZE=10000
SQLITE_JOURNAL_MODE=WAL
SQLITE_SYNCHRONOUS=NORMAL
EOF

# ─── Step 10: Health check script ─────────────────────────────────
log "Creating health check script..."
cat > "${BOT_DIR}/scripts/health_check.sh" << 'HEALTHEOF'
#!/bin/bash
# Health check for DMarket Bot
STATUS=$(systemctl is-active dmarket-dryrun.service)
MEM=$(ps -o rss= -p $(pgrep -f dry_run_14d.py 2>/dev/null || echo 1) 2>/dev/null | awk '{print int($1/1024)}')
LOG_LINES=$(wc -l < /var/log/dmarket-bot/dry_run_14d.log 2>/dev/null || echo 0)

echo "Status: ${STATUS}"
echo "Memory: ${MEM:-0} MB"
echo "Log lines: ${LOG_LINES}"

if [[ "${STATUS}" != "active" ]]; then
    echo "RESTARTING..."
    systemctl restart dmarket-dryrun.service
fi
HEALTHEOF
chmod +x "${BOT_DIR}/scripts/health_check.sh"

# ─── Done ─────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE!                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "  1. Edit .env with your Telegram credentials:"
echo "     nano ${ENV_FILE}"
echo ""
echo "  2. Start the dry run:"
echo "     systemctl start dmarket-dryrun"
echo ""
echo "  3. Enable auto-start on boot:"
echo "     systemctl enable dmarket-dryrun"
echo ""
echo "  4. Check status:"
echo "     systemctl status dmarket-dryrun"
echo ""
echo "  5. View logs:"
echo "     tail -f ${LOG_DIR}/dry_run_14d.log"
echo ""
echo "  6. View Telegram notifications:"
echo "     Check your Telegram bot for reports every 1.5 hours"
echo ""
