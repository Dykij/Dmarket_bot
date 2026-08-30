#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')
WT_FILE="$ARTIFACT_DIR/walkthrough.md"

if [ ! -s "$WT_FILE" ]; then
    echo '{"decision":"continue","reason":"walkthrough.md is missing or empty."}'
    exit 0
fi

CHARS=$(wc -c < "$WT_FILE")
if [ "$CHARS" -lt 100 ]; then
    echo '{"decision":"continue","reason":"walkthrough.md is too short (less than 100 chars). Provide a real summary."}'
    exit 0
fi

cd "$WORKSPACE_DIR"
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)
FOUND_FILE=0
if [ -n "$CHANGED_FILES" ]; then
    for file in $CHANGED_FILES; do
        BASENAME=$(basename "$file")
        if grep -qF "$BASENAME" "$WT_FILE"; then
            FOUND_FILE=1
            break
        fi
    done
    if [ "$FOUND_FILE" -eq 0 ]; then
        echo '{"decision":"continue","reason":"walkthrough.md must mention at least one of the files changed in this session."}'
        exit 0
    fi
fi

echo '{"decision":"allow"}'
