#!/bin/bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine // empty')
if [[ "$CMD" == *"git push"* || "$CMD" == *"rm "* || "$CMD" == *"--force"* ]]; then
    echo '{"decision":"ask","reason":"Destructive command detected. Requires explicit user approval."}'
else
    echo '{"decision":"allow"}'
fi
