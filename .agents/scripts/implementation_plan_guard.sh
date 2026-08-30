#!/bin/bash
INPUT=$(cat)
ARTIFACT_DIR=$(echo "$INPUT" | jq -r '.artifactDirectoryPath')
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolCall.name')
TARGET_FILE=$(echo "$INPUT" | jq -r '.toolCall.args.TargetFile // empty')

if [[ "$TOOL_NAME" == "write_to_file" || "$TOOL_NAME" == "replace_file_content" ]]; then
    if [[ "$TARGET_FILE" == *"task.md" ]]; then
        if [ ! -f "$ARTIFACT_DIR/implementation_plan.md" ]; then
            echo '{"decision":"deny","reason":"implementation_plan.md is missing. Must create plan before task.md."}'
            exit 0
        fi
    fi
fi
echo '{"decision":"allow"}'
