#!/bin/bash
PAYLOAD=$(cat)
CMD=$(echo "$PAYLOAD" | jq -r '.toolCall.args.CommandLine')
if [[ "$CMD" == *"git push"* || "$CMD" == *"rm "* || "$CMD" == *"--force"* || "$CMD" == *"sudo"* || "$CMD" == *"chattr"* ]]; then
    echo '{"decision": "ask", "reason": "⚠ Destructive/privileged command detected. Requires explicit user approval."}'
else
    echo '{"decision": "allow"}'
fi
