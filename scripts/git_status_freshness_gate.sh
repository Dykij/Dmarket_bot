#!/bin/bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine' 2>/dev/null)
JQ_EXIT_CODE=$?

if [ $JQ_EXIT_CODE -ne 0 ] || [[ -z "$CMD" || "$CMD" == "null" ]]; then
    # Probably an invalid payload, ignore
    echo '{"decision": "allow"}'
    exit 0
fi

# Detect if PostToolUse or PreToolUse based on .result presence
if echo "$INPUT" | jq -e '.result' >/dev/null 2>&1; then
    # PostToolUse
    ERR=$(echo "$INPUT" | jq -r '.result.error // empty')
    
    # Check if CMD matches git status
    if [[ "$CMD" =~ git[[:space:]]+status([[:space:]]|$) ]] && [ -z "$ERR" ]; then
        mkdir -p .agents/scratch
        date +%s > .agents/scratch/.last_git_status_ts
    fi
    echo "{}"
    exit 0
else
    # PreToolUse
    # If it's a destructive git command
    if [[ "$CMD" =~ git[[:space:]]+(reset|clean[[:space:]]+-f|commit[[:space:]]+--amend) ]] || [[ "$CMD" =~ git[[:space:]]+checkout[[:space:]]+([^[:space:]-]+|-[^b]) ]]; then
        # Exclude git checkout -b explicitly if my regex didn't catch it properly
        if [[ "$CMD" =~ git[[:space:]]+checkout[[:space:]]+-b ]]; then
            echo '{"decision":"allow"}'
            exit 0
        fi

        # Need fresh git status
        if [ -f .agents/scratch/.last_git_status_ts ]; then
            LAST_TS=$(cat .agents/scratch/.last_git_status_ts)
            NOW=$(date +%s)
            DIFF=$((NOW - LAST_TS))
            if [ "$DIFF" -le 90 ]; then
                echo '{"decision":"allow"}'
                exit 0
            fi
        fi
        
        echo '{"decision":"ask","reason":"Перед этой git-операцией нужен свежий git status (не старше 90с). Запустите git status и повторите."}'
        exit 0
    fi
    echo '{"decision":"allow"}'
    exit 0
fi
