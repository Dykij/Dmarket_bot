#!/bin/bash
PAYLOAD=$(cat)
WORKSPACE_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

COUNTER_FILE=".agents/.stop_gate_counter"
MAX_CONSECUTIVE_REPLIES=3

run_checks() {
    cd "$WORKSPACE_DIR"
    
    CHANGES=$(git status --porcelain | grep -v "^??")
    if [ -n "$CHANGES" ]; then
        if ! echo "$CHANGES" | grep -q "docs/SESSION_LOG.md"; then
            echo '{"decision": "continue", "reason": "You have made changes in this session. Please update docs/SESSION_LOG.md with a summary of your changes before exiting."}'
            return
        fi
    fi

    CURRENT_BRANCH=$(git branch --show-current)
    UNMERGED_INFO=""
    for branch in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
        if [ "$branch" != "$CURRENT_BRANCH" ]; then
            LOG=$(git log $CURRENT_BRANCH..$branch --oneline)
            if [ -n "$LOG" ]; then
                UNMERGED_INFO="${UNMERGED_INFO}Branch '$branch' has unmerged commits:\n$LOG\n\n"
            fi
        fi
    done

    if [ -n "$UNMERGED_INFO" ]; then
        jq -n --arg reason "Git hygiene warning: There are unmerged branches relative to $CURRENT_BRANCH:\n$UNMERGED_INFO\nPlease merge or delete them before stopping." '{"decision":"ask","reason":$reason}'
        return
    fi
    echo '{"decision":"allow"}'
}

RESULT=$(run_checks)
DECISION=$(echo "$RESULT" | jq -r '.decision')

if [ "$DECISION" = "continue" ]; then
    if [ -f "$COUNTER_FILE" ]; then
        COUNT=$(cat "$COUNTER_FILE")
        COUNT=$((COUNT + 1))
    else
        COUNT=1
    fi
    echo "$COUNT" > "$COUNTER_FILE"

    if [ "$COUNT" -ge "$MAX_CONSECUTIVE_REPLIES" ]; then
        jq -n --arg reason "LOOP GUARD TRIGGERED: $MAX_CONSECUTIVE_REPLIES consecutive 'continue' decisions." '{"decision":"ask","reason":$reason}'
        rm -f "$COUNTER_FILE"
        exit 0
    fi
else
    rm -f "$COUNTER_FILE"
fi

echo "$RESULT"
