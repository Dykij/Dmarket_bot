#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine // empty')
echo "[$(date -Iseconds)] COMMAND RUN: $CMD" >> "$WORKSPACE_DIR/.agents/logs/RAW_OUTPUT.log"
echo "{}"
