#!/bin/bash
# Read stdin into a variable to parse JSON
PAYLOAD=$(cat)
ARTIFACT_DIR=$(echo "$PAYLOAD" | jq -r '.artifactDirectoryPath')

if [ -f "$ARTIFACT_DIR/task.md" ]; then
    UNFINISHED=$(grep -c "^\s*- \[ \]" "$ARTIFACT_DIR/task.md" || true)
    if [ "$UNFINISHED" -gt 0 ]; then
        echo '{"decision": "continue", "reason": "У вас остались невыполненные задачи в task.md! Вы не можете завершить работу, пока не отметите их как [x]."}'
        exit 0
    fi
fi

# Fallback allow
echo '{"decision": "stop"}'
