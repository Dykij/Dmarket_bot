#!/bin/bash
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')

if [ ! -f "$ARTIFACT_DIR/task.md" ]; then
    echo '{"decision":"deny","reason":"task.md is missing. Planning Mode requires task.md before editing files."}'
else
    echo '{"decision":"allow"}'
fi
