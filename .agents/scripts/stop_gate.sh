#!/bin/bash
echo "$(date -Iseconds) CALLED: stop_gate.sh" >> /tmp/hooks_called.log
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')

IS_SUBAGENT=0
if [ ! -f "$ARTIFACT_DIR/task.md" ]; then
    IS_SUBAGENT=1
fi

WT_FILE="$ARTIFACT_DIR/walkthrough.md"

if [ "$IS_SUBAGENT" -eq 0 ]; then
    # 1. Walkthrough Guard (from stop_hook.sh)
    if [ ! -s "$WT_FILE" ]; then
        echo '{"decision":"continue","reason":"walkthrough.md is missing or empty."}'
        exit 0
    fi

    CHARS=$(wc -c < "$WT_FILE")
    if [ "$CHARS" -lt 100 ]; then
        echo '{"decision":"continue","reason":"walkthrough.md is too short (less than 100 chars). Provide a real summary."}'
        exit 0
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
                exit 0
            fi
        else
            # fallback на имя файла только если у диффа нет узнаваемых символов
            FOUND_FILE=0
            for file in $CHANGED_FILES; do
                BASENAME=$(basename "$file")
                if grep -qF "$BASENAME" "$WT_FILE"; then
                    FOUND_FILE=1; break
                fi
            done
            if [ "$FOUND_FILE" -eq 0 ]; then
                echo '{"decision":"continue","reason":"walkthrough.md must mention at least one of the files changed in this session."}'
                exit 0
            fi
        fi
    fi
fi

if [ "$IS_SUBAGENT" -eq 0 ]; then
    # 2. Stop Verification Gate (task.md & тесты)
    if grep -q "\[ \]" "$ARTIFACT_DIR/task.md"; then
        echo '{"decision":"ask","reason":"task.md contains uncompleted items [ ]. Click Proceed if this is intentional, or Reject to force the agent to complete them."}'
        exit 0
    fi

    if ! grep -qE "[0-9]+ passed|[0-9]+ failed|test result: (ok|FAILED)" "$WORKSPACE_DIR/.agents/logs/RAW_OUTPUT.log" 2>/dev/null; then
        echo '{"decision":"continue","reason":"RAW_OUTPUT.log does not contain a real test run result (e.g. X passed, Y failed)."}'
        exit 0
    fi

    # 3. Session Log Reminder (from check_session_log.sh)
    CHANGES=$(git status --porcelain | grep -v "^??")
    if [ -n "$CHANGES" ]; then
        if ! echo "$CHANGES" | grep -q "docs/SESSION_LOG.md"; then
            echo '{"decision": "continue", "reason": "You have made changes in this session. Please update docs/SESSION_LOG.md with a summary of your changes before exiting."}'
            exit 0
        fi
    fi
fi

# 4. Lazy Work Guard (from lazy_work_guard.sh)
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
            exit 0
        fi

        if echo "$ADDED_LINES" | grep -qE '^\+\s*pass\s*$|^\+\s*\.\.\.\s*(#.*)?$'; then
            jq -n --arg file "$file" '{"decision":"continue","reason":("Lazy marker: bare `pass` or `...` as function body in added lines of " + $file + ".")}'
            exit 0
        fi
    fi
done

echo '{"decision":"allow"}'
