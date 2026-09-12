#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
TARGET_FILE=$(echo "$INPUT" | jq -r '.toolCall.args.TargetFile // empty')

if [[ -z "$TARGET_FILE" || ! -f "$WORKSPACE_DIR/$TARGET_FILE" ]]; then
    echo "{}"
    exit 0
fi

OLD_FILE=$(mktemp)
# If file exists in HEAD, get it. Otherwise it's a new file.
if git ls-tree -r HEAD --name-only | grep -qx "$TARGET_FILE"; then
    git show "HEAD:$TARGET_FILE" > "$OLD_FILE"
else
    touch "$OLD_FILE"
fi

# Run difft
if difft --check-only --exit-code "$OLD_FILE" "$WORKSPACE_DIR/$TARGET_FILE" > /dev/null 2>&1; then
    # difft exits 0 if NO changes were detected
    echo "No structural/syntactic changes detected by difftastic in $TARGET_FILE." >&2
    rm -f "$OLD_FILE"
    exit 1
fi

rm -f "$OLD_FILE"
echo "{}"
exit 0
