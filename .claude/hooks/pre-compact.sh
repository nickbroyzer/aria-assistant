#!/bin/bash
# PC Dashboard — PreCompact Hook
# Saves state before context compaction

PROJECT_DIR="$HOME/Projects/my-assistant"
STATE_DIR="$PROJECT_DIR/.claude/state"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$STATE_DIR"

STATE_FILE="$STATE_DIR/pre-compact-$TIMESTAMP.md"

cd "$PROJECT_DIR" 2>/dev/null && {
cat > "$STATE_FILE" << STATEEOF
# Pre-Compaction State Snapshot
## Captured: $(date)

### Git State
- Branch: $(git branch --show-current)
- Last commit: $(git log --oneline -1)
- Uncommitted files:
$(git status --short)

### Recent Commits (last 5)
$(git log --oneline -5)

### Modified Files
$(git diff --name-only HEAD 2>/dev/null || echo "none")
STATEEOF

echo "[PreCompact] State saved to $STATE_FILE"
} || echo "[PreCompact] Could not access project directory"

# Keep last 10 state files, clean up older ones
ls -t "$STATE_DIR"/pre-compact-*.md 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null

echo ""
echo "---"
echo "**[COMPACTION OCCURRING]** Context is being summarized."
echo "State snapshot saved. Preserve: current task, pending fixes, API field names, CSS class names."
