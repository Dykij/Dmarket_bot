#!/bin/bash
cd /home/deck/dmarket/Dmarket_bot-main
export PYTHONUNBUFFERED=1
export DRY_RUN=true
.venv/bin/python tests/sandbox/dry_run_8h.py > logs/dry_run_8h_stdout.log 2>&1
echo "EXIT: $?" >> logs/dry_run_8h_stdout.log
