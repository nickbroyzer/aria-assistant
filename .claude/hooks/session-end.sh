#!/bin/bash
# Session End — Stop Hook
# Auto-writes session summary to Obsidian folder

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null)
LAST_MSG=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('last_assistant_message','')[:500])" 2>/dev/null)

# Prevent infinite loops
if [ "$STOP_ACTIVE" = "True" ]; then
  exit 0
fi

OBSIDIAN_DIR="$HOME/Documents/Obsidian/MyVault/PC Project"
PROJECT_DIR="$HOME/Projects/my-assistant"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
NOTE_FILE="$OBSIDIAN_DIR/Session-$DATE.md"

mkdir -p "$OBSIDIAN_DIR"

cd "$PROJECT_DIR" 2>/dev/null && {

# Only create if doesn't already exist (don't overwrite mid-day notes)
if [ ! -f "$NOTE_FILE" ]; then
cat > "$NOTE_FILE" << NOTEEOF
# Session $DATE

## Date: $DATE
## Time: $TIME

## Git State
- Branch: $(git branch --show-current)
- Last commit: $(git log --oneline -1)

## Last 5 Commits
$(git log --oneline -5)

## Uncommitted Changes
$(git status --short)

## Session Summary
(Auto-generated stub - review and update manually if needed)

## Next Steps
- Review this note at next session start
NOTEEOF
echo "[session-end] Obsidian note created: $NOTE_FILE"
else
  # Append update to existing note
  echo "" >> "$NOTE_FILE"
  echo "---" >> "$NOTE_FILE"
  echo "## Updated: $TIME" >> "$NOTE_FILE"
  echo "- Last commit: $(git log --oneline -1)" >> "$NOTE_FILE"
  echo "- Status: $(git status --short | wc -l) uncommitted files" >> "$NOTE_FILE"
  echo "[session-end] Obsidian note updated: $NOTE_FILE"
fi

} || echo "[session-end] Could not access project directory"

exit 0
