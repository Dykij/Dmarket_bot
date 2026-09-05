#!/bin/bash
# Hook to check if task.md exists before modifying src/ files

PAYLOAD=$(cat)
TARGET_FILE=$(echo "$PAYLOAD" | jq -r '.toolCall.args.TargetFile // ""')

# Check if modifying a file in src/
if [[ "$TARGET_FILE" == *"/src/"* || "$TARGET_FILE" == "src/"* ]]; then
  # Try to find task.md in the brain folder using artifactDirectoryPath (if provided) or in current dir
  ARTIFACT_DIR=$(echo "$PAYLOAD" | jq -r '.artifactDirectoryPath // ""')
  
  TASK_EXISTS=false
  if [ -f "task.md" ]; then
    TASK_EXISTS=true
  elif [ -n "$ARTIFACT_DIR" ] && [ -f "$ARTIFACT_DIR/../task.md" ]; then
    # In some versions, artifactDirectoryPath is a subfolder like 'artifacts'
    TASK_EXISTS=true
  elif [ -n "$ARTIFACT_DIR" ] && [ -f "$ARTIFACT_DIR/task.md" ]; then
    # In other versions, it is the root of the conversation folder
    TASK_EXISTS=true
  fi

  if [ "$TASK_EXISTS" = false ]; then
    echo '{"decision": "deny", "reason": "Mandatory artifact missing: task.md must exist before modifying src/ files."}'
    exit 0
  fi
fi

echo '{"decision": "allow"}'
