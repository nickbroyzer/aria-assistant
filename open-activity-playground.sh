#!/bin/bash
# open-activity-playground.sh — Sync activity feed CSS from dashboard.html into playground, then open
set -euo pipefail

DASH="templates/dashboard.html"
PLAY="ash-activity-playground.html"
cd "$(dirname "$0")"

if [[ ! -f "$DASH" ]]; then echo "ERROR: $DASH not found"; exit 1; fi
if [[ ! -f "$PLAY" ]]; then echo "ERROR: $PLAY not found"; exit 1; fi

# Extract a CSS property value from a selector block (handles same-line and multi-line rules)
css_val() {
  local sel="$1" prop="$2"
  awk -v sel="$sel" -v prop="$prop" '
    $0 ~ sel {
      if ($0 ~ prop ":") {
        sub(".*" prop ":[[:space:]]*", "")
        match($0, /[0-9]+/)
        if (RSTART > 0) { print substr($0, RSTART, RLENGTH) }
        exit
      }
      found=1; count=0; next
    }
    found {
      count++
      if ($0 ~ prop ":") {
        sub(".*" prop ":[[:space:]]*", "")
        match($0, /[0-9]+/)
        if (RSTART > 0) { print substr($0, RSTART, RLENGTH) }
        exit
      }
      if (count > 15 || /^[[:space:]]*\}/) { exit }
    }
  ' "$DASH"
}

echo "=== Syncing dashboard.html → activity playground ==="
echo ""

# Extract feed CSS values from dashboard
nameF=$(css_val '\.ash-feed-name[[:space:]]*\{' 'font-size')
actionF=$(css_val '\.ash-feed-action[[:space:]]*\{' 'font-size')
qsF=$(css_val '\.ash-feed-qs[[:space:]]*\{' 'font-size')
timeF=$(css_val '\.ash-feed-time[[:space:]]*\{' 'font-size')
dateF=$(css_val '\.ash-feed-date[[:space:]]*\{' 'font-size')
rowGap=$(css_val '\.ash-feed-row[[:space:]]*\{' 'gap')
rowPad=$(css_val '\.ash-feed-row[[:space:]]*\{' 'padding')

# Read old values from playground
get_old() {
  local cls="$1" prop="$2"
  awk -v sel="$cls" -v prop="$prop" '
    $0 ~ sel {
      if ($0 ~ prop ":") {
        sub(".*" prop ":[[:space:]]*", "")
        match($0, /[0-9]+/)
        if (RSTART > 0) { print substr($0, RSTART, RLENGTH) }
        exit
      }
      found=1; count=0; next
    }
    found {
      count++
      if ($0 ~ prop ":") {
        sub(".*" prop ":[[:space:]]*", "")
        match($0, /[0-9]+/)
        if (RSTART > 0) { print substr($0, RSTART, RLENGTH) }
        exit
      }
      if (count > 15 || /^[[:space:]]*\}/) { exit }
    }
  ' "$PLAY"
}

oldNameF=$(get_old '\.ash-feed-name' 'font-size')
oldActionF=$(get_old '\.ash-feed-action' 'font-size')
oldQsF=$(get_old '\.ash-feed-qs[[:space:]]*\{' 'font-size')
oldTimeF=$(get_old '\.ash-feed-time' 'font-size')
oldDateF=$(get_old '\.ash-feed-date' 'font-size')
oldRowGap=$(get_old '\.ash-feed-row[[:space:]]*\{' 'gap')
oldRowPad=$(get_old '\.ash-feed-row[[:space:]]*\{' 'padding')

# Report
printf "%-14s  %6s  %6s  %s\n" "VARIABLE" "OLD" "NEW" "STATUS"
printf "%-14s  %6s  %6s  %s\n" "----------" "-----" "-----" "-------"

changed=0
report() {
  local name="$1" old="$2" new="$3"
  if [[ "$old" == "$new" ]]; then
    printf "%-14s  %6s  %6s  %s\n" "$name" "$old" "$new" "same"
  else
    printf "%-14s  %6s  %6s  %s\n" "$name" "$old" "$new" "CHANGED"
    changed=$((changed + 1))
  fi
}

report "nameF" "$oldNameF" "$nameF"
report "actionF" "$oldActionF" "$actionF"
report "qsF" "$oldQsF" "$qsF"
report "timeF" "$oldTimeF" "$timeF"
report "dateF" "$oldDateF" "$dateF"
report "rowGap" "$oldRowGap" "$rowGap"
report "rowPad" "$oldRowPad" "$rowPad"

echo ""
echo "Total: $changed changed"

# Apply changes via sed
sed -i '' "s/\.ash-feed-name { font-size:[0-9]*px/.ash-feed-name { font-size:${nameF}px/" "$PLAY"
sed -i '' "s/\.ash-feed-action { font-size:[0-9]*px/.ash-feed-action { font-size:${actionF}px/" "$PLAY"
sed -i '' "s/\.ash-feed-qs { font-size:[0-9]*px/.ash-feed-qs { font-size:${qsF}px/" "$PLAY"
sed -i '' "s/\.ash-feed-time { font-size:[0-9]*px/.ash-feed-time { font-size:${timeF}px/" "$PLAY"
sed -i '' "s/\.ash-feed-date { font-size:[0-9]*px/.ash-feed-date { font-size:${dateF}px/" "$PLAY"

echo ""
echo "Playground updated"

# Open
open "$PLAY"
echo "Opened in browser"
