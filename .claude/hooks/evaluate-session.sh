#!/bin/bash
# Evaluate Session — Stop Hook
# Extracts learnings from sessions and saves them as skills
# Only processes sessions with 10+ messages

INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null)
STOP_ACTIVE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null)

# Prevent infinite loops
if [ "$STOP_ACTIVE" = "True" ]; then
  exit 0
fi

LEARNED_DIR="$HOME/.claude/skills/learned"
mkdir -p "$LEARNED_DIR"

DATE=$(date +%Y-%m-%d)
SESSION_LOG="$LEARNED_DIR/session-$DATE.md"

# Only process if transcript exists and has content
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  LINE_COUNT=$(wc -l < "$TRANSCRIPT")
  if [ "$LINE_COUNT" -gt 20 ]; then
    # Log that we processed this session
    echo "## Session: $DATE" >> "$SESSION_LOG"
    echo "Transcript: $TRANSCRIPT" >> "$SESSION_LOG"
    echo "Lines: $LINE_COUNT" >> "$SESSION_LOG"
    echo "" >> "$SESSION_LOG"
    echo "Review this transcript for patterns to extract:" >> "$SESSION_LOG"
    echo "- Error resolutions (what broke, what fixed it)" >> "$SESSION_LOG"
    echo "- User corrections (field names, CSS classes, API responses)" >> "$SESSION_LOG"
    echo "- Workarounds discovered" >> "$SESSION_LOG"
    echo "- Debugging techniques that worked" >> "$SESSION_LOG"
    echo "" >> "$SESSION_LOG"
    echo "[evaluate-session] Session logged for pattern extraction"
  fi
fi

exit 0
