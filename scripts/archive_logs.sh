#!/usr/bin/env bash
# archive_logs.sh — Automatic log archiving for DMarket Bot
# Compresses rotated logs older than 1 day, removes archives older than 30 days.
# Run via cron: 0 */6 * * * /home/deck/dmarket/Dmarket_bot-main/scripts/archive_logs.sh

set -euo pipefail

LOG_DIR="/home/deck/dmarket/Dmarket_bot-main/logs"
ARCHIVE_DIR="${LOG_DIR}/archive"
TODAY=$(date +%Y-%m-%d)

mkdir -p "${ARCHIVE_DIR}"

# Compress rotated bot logs (bot_24_7.log.1, .log.2, etc.) older than 1 day
find "${LOG_DIR}" -maxdepth 1 -name "bot_24_7.log.*" -type f -mtime +1 | while read -r logfile; do
    base=$(basename "${logfile}")
    archive_name="${ARCHIVE_DIR}/${base}.${TODAY}.gz"
    if [ ! -f "${archive_name}" ]; then
        gzip -c "${logfile}" > "${archive_name}"
        rm -f "${logfile}"
        echo "[${TODAY}] Archived: ${base} -> ${archive_name}"
    fi
done

# Compress old dry_run logs older than 1 day
find "${LOG_DIR}" -maxdepth 1 -name "dry_run_*.log" -type f -mtime +1 | while read -r logfile; do
    base=$(basename "${logfile}")
    archive_name="${ARCHIVE_DIR}/${base}.${TODAY}.gz"
    if [ ! -f "${archive_name}" ]; then
        gzip -c "${logfile}" > "${archive_name}"
        rm -f "${logfile}"
        echo "[${TODAY}] Archived: ${base} -> ${archive_name}"
    fi
done

# Remove archives older than 30 days
find "${ARCHIVE_DIR}" -name "*.gz" -type f -mtime +30 -delete 2>/dev/null && \
    echo "[${TODAY}] Cleaned archives older than 30 days"

# Report current log sizes
echo "[${TODAY}] Current logs:"
du -sh "${LOG_DIR}"/*.log 2>/dev/null || true
echo "[${TODAY}] Archives:"
du -sh "${ARCHIVE_DIR}" 2>/dev/null || echo "  No archives yet"
