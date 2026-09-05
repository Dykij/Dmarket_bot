#!/bin/bash
WORKSPACE_DIR=$(git rev-parse --show-toplevel)
INPUT=$(cat)
cd "$WORKSPACE_DIR"
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)

for file in $CHANGED_FILES; do
    if [[ "$file" == *.md ]]; then continue; fi
    if [[ "$file" == .agents/* ]]; then continue; fi
    if [ -f "$file" ]; then
        # Check only added lines
        if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
            ADDED_LINES=$(git diff HEAD -- "$file" 2>/dev/null | grep -E '^\+[^+]')
        else
            ADDED_LINES=$(sed 's/^/+/' "$file" 2>/dev/null)
        fi

        # Standard lazy markers in added lines
        if echo "$ADDED_LINES" | grep -qE "TODO|FIXME|NotImplementedError|placeholder|todo\!\(\)|unimplemented\!\(\)|unreachable\!\(\)"; then
            echo "{\"decision\":\"continue\",\"reason\":\"Lazy marker (TODO/FIXME/NotImplementedError) found in added lines of $file. Please implement fully or mark task as BLOCKED.\"}"
            exit 0
        fi

        # pass or ... as full line body in added lines
        if echo "$ADDED_LINES" | grep -qE '^\+\s*pass\s*$|^\+\s*\.\.\.\s*(#.*)?$'; then
            echo "{\"decision\":\"continue\",\"reason\":\"Lazy marker: bare \`pass\` or \`...\` as function body in added lines of $file.\"}"
            exit 0
        fi
    fi
done
echo '{"decision":"allow"}'
