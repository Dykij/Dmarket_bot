---
name: checkpoint-manager
description: Use before major operations (deploy, refactor, strategy changes) to create checkpoints for rollback. Trigger keywords: "checkpoint", "create checkpoint", "автооткат", "save state", "backup", "создай чекпоинт".
---

# Checkpoint Manager

Automatic checkpoint creation and rollback mechanism for safe code changes.

## Capabilities

1. **Auto-Checkpoint** - Create git stash before major operations
2. **Checkpoint Tracking** - Record all checkpoints in memory
3. **Quick Rollback** - Restore from any checkpoint
4. **Checkpoint Cleanup** - Remove old checkpoints

## Usage Patterns

### Pattern 1: Create Checkpoint Before Deploy

```markdown
Task: Create checkpoint before deployment

Steps:
1. Generate checkpoint ID: checkpoint-{timestamp}
2. git stash push -m "checkpoint-{id}"
3. Record to memory/checkpoints.json
4. Proceed with deployment
5. On failure: git stash pop to restore
```

### Pattern 2: Create Checkpoint Before Refactor

```markdown
Task: Create checkpoint before major refactoring

Steps:
1. git add -A (stage current state)
2. git stash push -m "pre-refactor-{timestamp}"
3. Record checkpoint with description
4. Proceed with refactoring
5. On failure: git stash pop
```

### Pattern 3: Rollback to Checkpoint

```markdown
Task: Rollback to specific checkpoint

Steps:
1. List all checkpoints from memory/checkpoints.json
2. User selects checkpoint to restore
3. git stash pop (or git stash apply for non-destructive)
4. Verify restoration successful
5. Remove checkpoint from tracking
```

## Checkpoint Storage

### Memory File: memory/checkpoints.json

```json
{
  "checkpoints": [
    {
      "id": "checkpoint-20260709-100000",
      "timestamp": "2026-07-09T10:00:00Z",
      "description": "Pre-deploy checkpoint",
      "stash_ref": "stash@{0}",
      "files_changed": 15,
      "operation": "deploy"
    }
  ],
  "max_checkpoints": 10,
  "auto_cleanup_days": 7
}
```

## Workflow Integration

### Pre-Deploy Checkpoint

Use before deployment to enable quick rollback:

```
Step 1: checkpoint-manager (create pre-deploy checkpoint)
        ↓
Step 2: git-gate (validate changes)
        ↓
Step 3: full-test-suite (run all tests)
        ↓
Step 4: deploy (execute deployment)
        ↓
Step 5: If failure → checkpoint-manager (rollback)
```

### Pre-Refactor Checkpoint

Use before major code changes:

```
Step 1: checkpoint-manager (create pre-refactor checkpoint)
        ↓
Step 2: Execute refactoring
        ↓
Step 3: full-test-suite (verify no regressions)
        ↓
Step 4: If failure → checkpoint-manager (rollback)
```

## Best Practices

1. **Always checkpoint before risky operations** - Deploy, refactor, strategy changes
2. **Use descriptive names** - Include what operation will follow
3. **Clean up old checkpoints** - Prevent stash bloat
4. **Test rollback procedure** - Verify checkpoints work before relying on them

## Output Format

Provide results as:

- **Checkpoint Created**: ID, timestamp, description
- **Stash Reference**: git stash reference for rollback
- **Files Changed**: Number of files in checkpoint
- **Rollback Available**: Yes/No with instructions

If checkpoint fails: explicitly state the error and suggest alternative backup methods.
