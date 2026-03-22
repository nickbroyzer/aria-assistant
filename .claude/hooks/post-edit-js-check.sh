#!/bin/bash
# Runs node --check on JS files after Edit/Write

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if echo "$FILE_PATH" | grep -qE '\.(js|mjs)$'; then
  if [ -f "$FILE_PATH" ]; then
    RESULT=$(node --check "$FILE_PATH" 2>&1)
    if [ $? -ne 0 ]; then
      echo "[JS CHECK FAILED] $FILE_PATH" >&2
      echo "$RESULT" >&2
      echo "Fix syntax errors before proceeding." >&2
    fi
  fi
fi

exit 0
