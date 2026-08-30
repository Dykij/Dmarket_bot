#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')

if ! grep -qE "[0-9]+ passed|[0-9]+ failed|test result: (ok|FAILED)" "$WORKSPACE_DIR/.agents/logs/RAW_OUTPUT.log" 2>/dev/null; then
    echo '{"decision":"continue","reason":"RAW_OUTPUT.log does not contain a real test run result (e.g. X passed, Y failed)."}'
    exit 0
fi

if [ -f "$ARTIFACT_DIR/task.md" ]; then
    if grep -q "\[ \]" "$ARTIFACT_DIR/task.md"; then
        echo '{"decision":"continue","reason":"task.md contains uncompleted items [ ]."}'
        exit 0
    fi
fi
echo '{"decision":"allow"}'
