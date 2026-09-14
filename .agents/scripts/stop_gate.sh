#!/bin/bash
echo "$(date -Iseconds) CALLED: stop_gate_new.sh" >> /tmp/hooks_called.log
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')

CONVERSATION_ID=$(basename "$ARTIFACT_DIR")
COUNTER_FILE="/tmp/stop_gate_counter_${CONVERSATION_ID}"
MAX_CONSECUTIVE_REPLIES=15

# Wrapper function for the original logic
run_checks() {
    IS_SUBAGENT=0
    if [ ! -f "$ARTIFACT_DIR/task.md" ]; then
        IS_SUBAGENT=1
    fi

    WT_FILE="$ARTIFACT_DIR/walkthrough.md"

    if [ "$IS_SUBAGENT" -eq 0 ]; then
        # 1. Walkthrough Guard (from stop_hook.sh)
        if [ ! -s "$WT_FILE" ]; then
            echo '{"decision":"continue","reason":"walkthrough.md is missing or empty."}'
            return
        fi

        CHARS=$(wc -c < "$WT_FILE")
        if [ "$CHARS" -lt 100 ]; then
            echo '{"decision":"continue","reason":"walkthrough.md is too short (less than 100 chars). Provide a real summary."}'
            return
        fi
    fi

    cd "$WORKSPACE_DIR"
    CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)

    if [ "$IS_SUBAGENT" -eq 0 ]; then
        if [ -n "$CHANGED_FILES" ]; then
            CHANGED_SYMBOLS=$(git diff -U0 HEAD 2>/dev/null | grep -E '^\+' | grep -oE '[a-zA-Z_][a-zA-Z0-9_]{4,}' | sort -u)
            FOUND_MATCH=0
            if [ -n "$CHANGED_SYMBOLS" ]; then
                for sym in $CHANGED_SYMBOLS; do
                    if grep -qF "$sym" "$WT_FILE"; then
                        FOUND_MATCH=1; break
                    fi
                done
                if [ "$FOUND_MATCH" -eq 0 ]; then
                    echo '{"decision":"continue","reason":"walkthrough.md must mention changed symbols from git diff."}'
                    return
                fi
            else
                # fallback
                FOUND_FILE=0
                for file in $CHANGED_FILES; do
                    BASENAME=$(basename "$file")
                    if grep -qF "$BASENAME" "$WT_FILE"; then
                        FOUND_FILE=1; break
                    fi
                done
                if [ "$FOUND_FILE" -eq 0 ]; then
                    echo '{"decision":"continue","reason":"walkthrough.md must mention at least one of the files changed in this session."}'
                    return
                fi
            fi
        fi
    fi

    if [ "$IS_SUBAGENT" -eq 0 ]; then
        # 2. Stop Verification Gate (task.md & тесты)
        if grep -q "\[ \]" "$ARTIFACT_DIR/task.md"; then
            echo '{"decision":"ask","reason":"task.md contains uncompleted items [ ]. Click Proceed if this is intentional, or Reject to force the agent to complete them."}'
            return
        fi

        # Determine if there are actual code changes (across the entire session)
        SESSION_START_FILE="$ARTIFACT_DIR/session_start_commit.txt"
        if [ -f "$SESSION_START_FILE" ]; then
            SESSION_START=$(cat "$SESSION_START_FILE")
            ALL_SESSION_FILES=$(git diff --name-only "$SESSION_START" HEAD 2>/dev/null)
        else
            # Fallback for sub-agents or old sessions
            ALL_SESSION_FILES="$CHANGED_FILES"
        fi

        HAS_CODE_CHANGES=0
        for file in $ALL_SESSION_FILES $CHANGED_FILES; do
            if [[ "$file" != *.md ]] && [[ "$file" != .agents/* ]]; then
                HAS_CODE_CHANGES=1
                break
            fi
        done

        if [ "$HAS_CODE_CHANGES" -eq 1 ]; then
            if ! grep -qE "[0-9]+ passed|[0-9]+ failed|test result: (ok|FAILED)" "$WORKSPACE_DIR/.agents/logs/RAW_OUTPUT.log" 2>/dev/null; then
                echo '{"decision":"continue","reason":"RAW_OUTPUT.log does not contain a real test run result (e.g. X passed, Y failed)."}'
                return
            fi
        else
            # No code changes. Require explicit marker in walkthrough.md
            if ! grep -q "CODE_UNCHANGED_SESSION: true" "$WT_FILE"; then
                echo '{"decision":"continue","reason":"No code changes detected, but CODE_UNCHANGED_SESSION: true marker is missing in walkthrough.md. If this was an analytical session, add the marker. Otherwise, you must run tests."}'
                return
            fi
        fi

        # 3. Session Log Reminder (from check_session_log.sh)
        CHANGES=$(git status --porcelain | grep -v "^??")
        if [ -n "$CHANGES" ]; then
            if ! echo "$CHANGES" | grep -q "docs/SESSION_LOG.md"; then
                echo '{"decision": "continue", "reason": "You have made changes in this session. Please update docs/SESSION_LOG.md with a summary of your changes before exiting."}'
                return
            fi
        fi
    fi

    # 4. Lazy Work Guard
    echo "$CHANGED_FILES" | while IFS= read -r file; do
        [ -z "$file" ] && continue
        if [[ "$file" == *.md ]]; then continue; fi
        if [[ "$file" == .agents/* ]]; then continue; fi
        if [ -f "$file" ]; then
            if git ls-files --error-unmatch "$file" > /dev/null 2>&1; then
                ADDED_LINES=$(git diff HEAD -- "$file" 2>/dev/null | grep -E '^\+[^+]')
            else
                ADDED_LINES=$(sed 's/^/+/' "$file" 2>/dev/null)
            fi

            if echo "$ADDED_LINES" | grep -qE "TODO|FIXME|NotImplementedError|placeholder|todo\!\(\)|unimplemented\!\(\)|unreachable\!\(\)"; then
                jq -n --arg file "$file" '{"decision":"continue","reason":("Lazy marker (TODO/FIXME/NotImplementedError) found in added lines of " + $file + ". Please implement fully or mark task as BLOCKED.")}'
                return
            fi

            if echo "$ADDED_LINES" | grep -qE '^\+\s*pass\s*$|^\+\s*\.\.\.\s*(#.*)?$'; then
                jq -n --arg file "$file" '{"decision":"continue","reason":("Lazy marker: bare `pass` or `...` as function body in added lines of " + $file + ".")}'
                return
            fi
        fi
    done

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
    # increment counter
    if [ -f "$COUNTER_FILE" ]; then
        COUNT=$(cat "$COUNTER_FILE")
        COUNT=$((COUNT + 1))
    else
        COUNT=1
    fi
    echo "$COUNT" > "$COUNTER_FILE"

    if [ "$COUNT" -ge "$MAX_CONSECUTIVE_REPLIES" ]; then
        # Force ask to stop the loop
        jq -n --arg reason "LOOP GUARD TRIGGERED: $MAX_CONSECUTIVE_REPLIES consecutive 'continue' decisions. The agent is likely stuck in an infinite loop failing verification. Please intervene." '{"decision":"ask","reason":$reason}'
        rm -f "$COUNTER_FILE"
        exit 0
    fi
else
    # reset counter on allow or ask
    rm -f "$COUNTER_FILE"
fi

echo "$RESULT"
