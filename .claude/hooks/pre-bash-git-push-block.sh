#!/bin/bash
# Blocks git push without verification
# Returns exit code 2 to BLOCK the action

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

if echo "$COMMAND" | grep -qi "git push"; then
  VERIFY_FILE="$HOME/Projects/my-assistant/.claude/state/push-verified"
  if [ -f "$VERIFY_FILE" ]; then
    rm -f "$VERIFY_FILE"
    exit 0
  else
    echo "BLOCKED: git push attempted without verification." >&2
    echo "" >&2
    echo "To push, first run pc-verifier agent, then:" >&2
    echo "  touch ~/Projects/my-assistant/.claude/state/push-verified" >&2
    echo "Then retry the push." >&2
    exit 2
  fi
fi

exit 0
