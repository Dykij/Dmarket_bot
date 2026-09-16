#!/bin/bash
PAYLOAD=$(cat)
TOOL_NAME=$(echo "$PAYLOAD" | jq -r '.toolCall.name')
ARTIFACT_DIR=$(echo "$PAYLOAD" | jq -r '.artifactDirectoryPath')

is_destructive=0

if [[ "$TOOL_NAME" == "write_to_file" || "$TOOL_NAME" == "replace_file_content" ]]; then
    TARGET=$(echo "$PAYLOAD" | jq -r '.toolCall.args.TargetFile // .toolCall.args.AbsolutePath // ""')
    if [[ "$TARGET" != "$ARTIFACT_DIR/task.md" ]]; then
        is_destructive=1
    fi
fi

if [[ "$TOOL_NAME" == "run_command" ]]; then
    CMD=$(echo "$PAYLOAD" | jq -r '.toolCall.args.CommandLine')
    if [[ "$CMD" == *"git commit"* || "$CMD" == *"rm "* || "$CMD" == *"git rm"* ]]; then
        is_destructive=1
    fi
    if [[ "$CMD" == *"python3"* || "$CMD" == *".venv/bin/python"* ]] && \
       [[ "$CMD" == *"delete"* || "$CMD" == *"Remove"* || "$CMD" == *"remove"* ]]; then
        is_destructive=1
    fi
fi

if [[ "$is_destructive" -eq 1 ]] && [ -f "$ARTIFACT_DIR/task.md" ]; then
    if grep -q -E "^\s*-\s*\[[ /]\].*\[WAIT-FOR-USER\]" "$ARTIFACT_DIR/task.md"; then
        echo '{"decision": "ask", "reason": "В task.md обнаружен незакрытый чек-поинт [WAIT-FOR-USER]. Попытка деструктивного действия до подтверждения. Требуется явный Proceed."}'
        exit 0
    fi
fi

echo '{"decision": "allow"}'
