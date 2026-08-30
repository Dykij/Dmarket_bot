#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
cd "$WORKSPACE_DIR"
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)
for file in $CHANGED_FILES; do
    if [[ "$file" == *.md ]]; then continue; fi
    if [[ "$file" == .agents/* ]]; then continue; fi
    if [ -f "$file" ]; then
        if grep -qE "TODO|FIXME|pass  # implement|NotImplementedError|\.\.\. *#|placeholder|todo!\(\)|unimplemented!\(\)|unreachable!\(\)" "$file"; then
            echo "{\"decision\":\"continue\",\"reason\":\"Lazy marker found in $file. Please implement fully or mark task as BLOCKED.\"}"
            exit 0
        fi
    fi
done
echo '{"decision":"allow"}'
