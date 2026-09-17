#!/bin/bash
PAYLOAD=$(cat)
CMD=$(echo "$PAYLOAD" | jq -r '.toolCall.args.CommandLine')

if [[ "$CMD" == *"git push"* || "$CMD" == *"sudo "* || "$CMD" == *"chattr "* ]]; then
    # Hard rules: ask as-is (no overwrite)
    echo '{"decision": "ask", "reason": "⚠ Privileged or network-destructive command detected. Requires explicit user approval."}'
elif [[ "$CMD" == *"git clean -f"* ]]; then
    # Overwrite git clean -f to git clean -n
    NEW_CMD="${CMD//-f/-n}"
    echo "{\"decision\": \"ask\", \"reason\": \"⚠ git clean -f is dangerous. Converted to dry-run (-n).\", \"overwrite\": {\"CommandLine\": \"$NEW_CMD\"}}"
elif [[ "$CMD" == *"rm "* && "$CMD" == *"*"* ]]; then
    # Overwrite rm with wildcards to ls to prevent accidental mass deletion
    TARGETS=$(echo "$CMD" | sed 's/.*rm \(-[a-zA-Z]* \)*//')
    NEW_CMD="ls -la $TARGETS"
    echo "{\"decision\": \"ask\", \"reason\": \"⚠ Mass deletion (rm with wildcard) is blocked (H19). Converted to ls -la.\", \"overwrite\": {\"CommandLine\": \"$NEW_CMD\"}}"
elif [[ "$CMD" == *"rm "* || "$CMD" == *"--force"* ]]; then
    echo '{"decision": "ask", "reason": "⚠ Destructive command detected. Requires explicit user approval."}'
else
    echo '{"decision": "allow"}'
fi
