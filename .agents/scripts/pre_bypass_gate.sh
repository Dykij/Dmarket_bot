#!/bin/bash
INPUT=$(cat)
BYPASS_FLAG=$(echo "$INPUT" | jq -r '.toolCall.args.BypassSandbox // false')

if [ "$BYPASS_FLAG" != "true" ]; then
    echo '{"decision":"allow"}'
    exit 0
fi

WORKSPACE_DIR=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null || echo "/home/deck/dmarket/Dmarket_bot-main")
APPROVAL_FILE="$WORKSPACE_DIR/.agents/state/bypass-approved-$(date +%Y%m%d).flag"
if [ -f "$APPROVAL_FILE" ]; then
    echo '{"decision":"allow"}'
    exit 0
fi

echo '{"decision":"deny","reason":"BypassSandbox requested without a same-day approval file. Ask the user explicitly for permission and, ONLY after they confirm in the chat, request they create the approval file themselves (not you) — or wait for their explicit textual Proceed before retrying without bypass."}'
exit 0

