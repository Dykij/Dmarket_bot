#!/bin/bash
PAYLOAD=$(cat)
CMD=$(echo "$PAYLOAD" | jq -r '.toolCall.args.CommandLine')

if [[ "$CMD" == *"git push"* ]]; then
    echo '{"decision": "ask", "reason": "⚠️ Правило AGENTS.md: git push требует явного разрешения. Вы уверены, что хотите выполнить пуш?"}'
    exit 0
fi

echo '{"decision": "allow"}'
