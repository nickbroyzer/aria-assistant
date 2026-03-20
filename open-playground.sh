#!/bin/bash
# open-playground.sh — Sync dashboard.html CSS values into playground defaults, then open
set -euo pipefail

DASH="templates/dashboard.html"
PLAY="ash-overview-playground.html"
cd "$(dirname "$0")"

if [[ ! -f "$DASH" ]]; then echo "ERROR: $DASH not found"; exit 1; fi
if [[ ! -f "$PLAY" ]]; then echo "ERROR: $PLAY not found"; exit 1; fi

# --- Extract first numeric value of a CSS property inside a selector block ---
css_val() {
  local sel="$1" prop="$2"
  awk -v sel="$sel" -v prop="$prop" '
    $0 ~ sel {
      # Check if property is on the same line (single-line rule)
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

# --- Extract two numeric values from a shorthand property (e.g. padding: 18px 22px) ---
css_two() {
  local sel="$1" prop="$2"
  awk -v sel="$sel" -v prop="$prop" '
    function extract_two() {
      n=0
      s=$0
      # skip past the property name to just the values
      sub(".*" prop ":[[:space:]]*", "", s)
      while (match(s, /[0-9]+/) && n < 2) {
        vals[n++] = substr(s, RSTART, RLENGTH)
        s = substr(s, RSTART + RLENGTH)
      }
      if (n == 1) print vals[0] " " vals[0]
      else print vals[0] " " vals[1]
      exit
    }
    $0 ~ sel {
      if ($0 ~ prop ":") { extract_two() }
      found=1; count=0; next
    }
    found {
      count++
      if ($0 ~ prop ":") { extract_two() }
      if (count > 15 || /^[[:space:]]*\}/) { exit }
    }
  ' "$DASH"
}

# --- Extract max-width from .ash-ov-stat-grid (0 if absent) ---
get_grid_max_w() {
  local val
  val=$(awk '
    /\.ash-ov-stat-grid[[:space:]]*\{/ { found=1; count=0; next }
    found {
      count++
      if (/max-width/) {
        match($0, /[0-9]+/)
        if (RSTART > 0) { print substr($0, RSTART, RLENGTH); exit }
      }
      if (count > 15 || /^[[:space:]]*\}/) { print "0"; exit }
    }
  ' "$DASH")
  echo "${val:-0}"
}

# --- Read old default value for a key from playground line 135 ---
get_old() {
  local key="$1"
  sed -n '135p' "$PLAY" | sed -n "s/.*${key}:\([0-9]*\).*/\1/p"
}

echo "=== Syncing dashboard.html → playground defaults ==="
echo ""

# Extract all values
padVals=$(css_two '\.ash-ov-content[[:space:]]*\{' 'padding')
padTop=$(echo "$padVals" | cut -d' ' -f1)
padSide=$(echo "$padVals" | cut -d' ' -f2)

statusMB=$(css_val '\.ash-ov-status-bar[[:space:]]*\{' 'margin-bottom')
badgeFont=$(css_val '\.ash-ov-live-badge[[:space:]]*\{' 'font-size')

gridGap=$(css_val '\.ash-ov-stat-grid[[:space:]]*\{' 'gap')
gridMB=$(css_val '\.ash-ov-stat-grid[[:space:]]*\{' 'margin-bottom')
gridMaxW=$(get_grid_max_w)

cardPad=$(css_val '\.ash-ov-stat-card[[:space:]]*\{' 'padding')
cardMinH=$(css_val '\.ash-ov-stat-card[[:space:]]*\{' 'min-height')
cardR=$(css_val '\.ash-ov-stat-card[[:space:]]*\{' 'border-radius')

lblF=$(css_val '\.ash-ov-stat-label[[:space:]]*\{' 'font-size')
valF=$(css_val '\.ash-ov-stat-value[[:space:]]*\{' 'font-size')
subF=$(css_val '\.ash-ov-stat-sub[[:space:]]*\{' 'font-size')

divM=$(css_val '\.ash-ov-divider[[:space:]]*\{' 'margin')

gap=$(css_val '\.ash-ov-lower[[:space:]]*\{' 'gap')
cW=$(css_val '\.ash-ov-col-calls[[:space:]]*\{' 'width')
iW=$(css_val '\.ash-ov-col-insight[[:space:]]*\{' 'width')
hdrF=$(css_val '\.ash-ov-col-header[[:space:]]*\{' 'font-size')

rGap=$(css_val '\.ash-ov-call-row[[:space:]]*\{' 'gap')
rowPad=$(css_two '\.ash-ov-call-row[[:space:]]*\{' 'padding')
rpV=$(echo "$rowPad" | cut -d' ' -f1)
rpH=$(echo "$rowPad" | cut -d' ' -f2)
rMB=$(css_val '\.ash-ov-call-row[[:space:]]*\{' 'margin-bottom')

nF=$(css_val '\.ash-ov-call-name[[:space:]]*\{' 'font-size')
oF=$(css_val '\.ash-ov-call-outcome[[:space:]]*\{' 'font-size')
sF=$(css_val '\.ash-ov-call-score[[:space:]]*\{' 'font-size')
tF=$(css_val '\.ash-ov-call-time[[:space:]]*\{' 'font-size')

eyeF=$(css_val '\.ash-ov-insight-eyebrow[[:space:]]*\{' 'font-size')
insF=$(css_val '\.ash-ov-insight-num[[:space:]]*\{' 'font-size')
dscF=$(css_val '\.ash-ov-insight-desc[[:space:]]*\{' 'font-size')

navP=$(css_val '\.ash-ov-nav-links[[:space:]]*\{' 'gap')
navF=12  # no corresponding dashboard rule

# Validate no empty values
missing=""
for k in padTop padSide statusMB badgeFont gridGap gridMB cardPad cardMinH cardR lblF valF subF divM gap cW iW hdrF rGap rpV rpH rMB nF oF sF tF eyeF insF dscF navP; do
  v=$(eval echo "\$$k")
  if [[ -z "$v" ]]; then missing="$missing $k"; fi
done
if [[ -n "$missing" ]]; then
  echo "ERROR: Failed to extract:$missing"
  exit 1
fi

# Build the new const D={...} line
NEW_LINE="const D={gridMaxW:${gridMaxW},padTop:${padTop},padSide:${padSide},badgeFont:${badgeFont},statusMB:${statusMB},cardPad:${cardPad},cardMinH:${cardMinH},gridGap:${gridGap},cardR:${cardR},lblF:${lblF},valF:${valF},subF:${subF},gridMB:${gridMB},divM:${divM},gap:${gap},cW:${cW},iW:${iW},hdrF:${hdrF},rpV:${rpV},rpH:${rpH},rGap:${rGap},rMB:${rMB},nF:${nF},oF:${oF},sF:${sF},tF:${tF},eyeF:${eyeF},insF:${insF},dscF:${dscF},navF:${navF},navP:${navP}};"

# --- Comparison report ---
printf "\n%-14s  %6s  %6s  %s\n" "VARIABLE" "OLD" "NEW" "STATUS"
printf "%-14s  %6s  %6s  %s\n" "----------" "-----" "-----" "-------"

changed=0
keys="gridMaxW padTop padSide badgeFont statusMB cardPad cardMinH gridGap cardR lblF valF subF gridMB divM gap cW iW hdrF rpV rpH rGap rMB nF oF sF tF eyeF insF dscF navF navP"
for k in $keys; do
  old=$(get_old "$k")
  new=$(eval echo "\$$k")
  if [[ "$old" == "$new" ]]; then
    status="same"
  else
    status="CHANGED"
    changed=$((changed + 1))
  fi
  printf "%-14s  %6s  %6s  %s\n" "$k" "${old:-?}" "$new" "$status"
done

echo ""
echo "Total: $changed changed"

# Replace line 135 — use awk to avoid sed delimiter issues
awk -v line="$NEW_LINE" 'NR==135{print line;next}{print}' "$PLAY" > "${PLAY}.tmp" && mv "${PLAY}.tmp" "$PLAY"
echo ""
echo "Line 135 updated in $PLAY"

# Open in browser
open "$PLAY"
echo "Opened in browser"
