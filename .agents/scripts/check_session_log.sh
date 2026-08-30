#!/bin/bash
cat > /dev/null
# Only check for tracked changes (modified/added/deleted in index or working tree)
CHANGES=$(git status --porcelain | grep -v "^??")
if [ -n "$CHANGES" ]; then
    if ! echo "$CHANGES" | grep -q "docs/SESSION_LOG.md"; then
        echo '{"decision": "continue", "reason": "You have made changes in this session. Please update docs/SESSION_LOG.md with a summary of your changes before exiting."}'
        exit 0
    fi
fi
echo "{}"
