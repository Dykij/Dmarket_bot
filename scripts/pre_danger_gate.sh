#!/bin/bash
PAYLOAD=$(cat)
CMD=$(echo "$PAYLOAD" | jq -r '.toolCall.args.CommandLine' 2>/dev/null)
JQ_EXIT_CODE=$?

if [ $JQ_EXIT_CODE -ne 0 ] || [[ -z "$CMD" || "$CMD" == "null" ]]; then
    echo '{"decision": "ask", "reason": "⚠ Invalid payload or empty command. Gate fails closed for safety."}'
    exit 0
fi

if [[ "$CMD" == *".env"* ]]; then
    echo '{"decision": "deny", "reason": "⛔ Access to .env files is strictly forbidden across all commands."}'
elif [[ "$CMD" == *"chattr "* ]]; then
    echo '{"decision": "ask", "reason": "⚠ Privileged command detected (chattr). Requires explicit user approval."}'
elif [[ "$CMD" == *"git clean -f"* ]]; then
    NEW_CMD="${CMD//-f/-n}"
    echo "{\"decision\": \"ask\", \"reason\": \"⚠ git clean -f is dangerous. Converted to dry-run (-n).\", \"overwrite\": {\"CommandLine\": \"$NEW_CMD\"}}"
elif [[ "$CMD" == *"rm "* && "$CMD" == *"*"* ]]; then
    TARGETS=$(echo "$CMD" | sed 's/.*rm \(-[a-zA-Z]* \)*//')
    NEW_CMD="ls -la $TARGETS"
    echo "{\"decision\": \"ask\", \"reason\": \"⚠ Mass deletion (rm with wildcard) is blocked (H19). Converted to ls -la.\", \"overwrite\": {\"CommandLine\": \"$NEW_CMD\"}}"
else
    echo '{"decision": "allow"}'
fi
