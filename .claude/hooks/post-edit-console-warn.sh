#!/bin/bash
# Warns if console.log found in recently edited files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if echo "$FILE_PATH" | grep -qE '\.(js|mjs|html)$'; then
  if [ -f "$FILE_PATH" ]; then
    MATCHES=$(grep -n 'console\.log' "$FILE_PATH" 2>/dev/null)
    if [ -n "$MATCHES" ]; then
      echo "[WARNING] console.log found in $FILE_PATH:" >&2
      echo "$MATCHES" >&2
      echo "Remove before committing." >&2
    fi
  fi
fi

exit 0
