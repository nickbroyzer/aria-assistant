# Fix Ash Activity Tab — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Ash Activity tab functional, visually consistent with Ash Inbox, and populated with dynamic demo data.

**Architecture:** Same pattern as Ash Inbox fix — dynamic timestamps in `routes/ash.py`, layout/scroll fixes in `dashboard.html`. No new routes, no new libraries.

**Tech Stack:** Flask/Python backend, vanilla JS/CSS frontend, existing CSS variables.

---

## Identified Problems

1. **Stale data** — `ASH_ACTIVITY_DEMO` has hardcoded `2026-03-15` timestamps. Today is `2026-03-16`, so nothing groups under "Today".
2. **Too few items** — only 14 activity entries; feed looks sparse.
3. **Stats count all items** — `loadAshActivity()` counts leads/invoices/calls across ALL activity, not just today's. Stats labels say "today" but numbers reflect all time.
4. **No internal scrolling** — `.ash-activity-two-col` uses `align-items:start`; feed grows unbounded and pushes the whole page to scroll. Inbox was fixed with `#content:has()` override + flex column + `min-height:0` chain; Activity needs the same treatment.
5. **Weekly data is static** — `ASH_WEEKLY_DEMO` is a plain dict, not dynamic. Minor issue but inconsistent with the Inbox approach.
6. **No DOMContentLoaded preload** — Activity only loads on tab click, unlike Inbox which now also loads on DOMContentLoaded. **Out of scope:** Activity data is heavier and only needed when the user navigates to it. The existing `showPage()` trigger at line 3591 is sufficient.

## Constraints (from AGENTS.md + prior instructions)

- Do NOT touch Ash Inbox layout
- Do NOT change `app.py`
- Do NOT add new libraries
- Do NOT change page structure / tab activation logic
- Smallest valid diff
- Only edit `routes/ash.py` and `templates/dashboard.html`

## File Structure

No new files. Modifications only:

| File | Responsibility |
|------|---------------|
| `routes/ash.py` | Convert `ASH_ACTIVITY_DEMO` to dynamic function; expand to ~25 items; make weekly data dynamic |
| `templates/dashboard.html` | Fix Activity layout CSS; fix stats to count today-only; add scroll containment |

---

## Task 1: Make Activity Demo Data Dynamic

**Files:**
- Modify: `routes/ash.py:251-395` (ASH_ACTIVITY_DEMO + ASH_WEEKLY_DEMO)

- [ ] **Step 1: Convert `ASH_ACTIVITY_DEMO` to `_build_activity_demo()` function**

Same pattern as `_build_inbox_demo()`. Use `_today_str()` and `_yesterday_str()` for timestamps. Keep all 14 existing items but shift their dates so:
- ~8 items land on today
- ~6 items land on yesterday

```python
def _build_activity_demo():
    t = _today_str()
    y = _yesterday_str()
    return [
        {"id": "act-001", "timestamp": f"{t}T09:15:00-07:00", "action_type": "lead_created",
         "description": "Created lead — Brian Holloway, Tacoma warehouse racking inquiry. Quality score 92.",
         "sender": "Brian Holloway", "quality_score": 92, "type": "call"},
        # ... (shift remaining items to t/y)
    ]
```

- [ ] **Step 2: Expand to ~25 activity items**

Add 11 new items matching inbox demo people (Rachel Dunn, Luis Medina, Puget Sound Brewing, David Park, Priya Sharma, Emerald City Distributors, etc.). Mix of `lead_created`, `invoice_logged`, `forwarded`, `not_qualified`, `spam_blocked`. ~13 today, ~12 yesterday.

- [ ] **Step 3: Update `api_ash_activity()` route to use the function**

```python
@ash_bp.route("/api/ash/activity", methods=["GET"])
@require_auth
def api_ash_activity():
    items = _build_activity_demo()
    return jsonify({
        "activity": items,
        "count": len(items)
    })
```

- [ ] **Step 4: Make `ASH_WEEKLY_DEMO` dynamic**

Convert to `_build_weekly_demo()` that derives counts from `_build_activity_demo()` and `_build_inbox_demo()` for "this week", with static "last week" baseline.

```python
def _build_weekly_demo():
    activity = _build_activity_demo()
    return {
        "this_week": {
            "leads": sum(1 for a in activity if a["action_type"] == "lead_created"),
            "invoices": sum(1 for a in activity if a["action_type"] == "invoice_logged"),
            "calls": sum(1 for a in activity if a["type"] == "call"),
            "not_qualified": sum(1 for a in activity if a["action_type"] == "not_qualified"),
            "messages": len(activity)
        },
        "last_week": {"leads": 4, "invoices": 3, "calls": 11, "not_qualified": 4, "messages": 18}
    }
```

Update `api_ash_weekly()` to call it.

- [ ] **Step 5: Verify routes return dynamic data**

Run:
```bash
source venv/bin/activate && python - <<'PY'
from app import app
import json
from datetime import date

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 'owner-jay'
    r = c.get('/api/ash/activity')
    data = json.loads(r.data)
    today = date.today().isoformat()
    today_items = [a for a in data['activity'] if a['timestamp'].startswith(today)]
    print(f"Total activity: {data['count']}, Today: {len(today_items)}")
    assert data['count'] >= 25
    assert len(today_items) >= 10
    print('PASS')
PY
```

Expected: `Total activity: 25, Today: 13` (approx), PASS

- [ ] **Step 6: Commit**

```bash
git add routes/ash.py
git commit -m "feat(ash): make activity + weekly demo data dynamic with today/yesterday timestamps"
```

---

## Task 2: Fix Activity Stats to Count Today Only

**Files:**
- Modify: `templates/dashboard.html:11314-11328` (loadAshActivity stats section)

- [ ] **Step 1: Read current stats logic**

Current code at ~line 11321-11328 counts across ALL activity items. The stat labels say "today" but the numbers include yesterday and older.

- [ ] **Step 2: Filter to today before counting**

Change the stats section in `loadAshActivity()`:

```javascript
// Filter to today only for stats (labels say "auto-created today", "flagged today", etc.)
const today = new Date().toLocaleDateString('en-CA');
const todayActivity = allAshActivity.filter(a => a.timestamp.split('T')[0] === today);
const leads    = todayActivity.filter(a => a.action_type === 'lead_created').length;
const invoices = todayActivity.filter(a => a.action_type === 'invoice_logged').length;
const nq       = todayActivity.filter(a => a.action_type === 'not_qualified').length;
const calls    = todayActivity.filter(a => a.type === 'call').length;
```

- [ ] **Step 3: Verify stats render correctly**

Load dashboard, navigate to Ash Activity. Stats should show today-only counts, not all-time.

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard.html
git commit -m "fix(ash): activity stats now count today-only items to match stat labels"
```

---

## Task 3: Fix Activity Layout — Internal Scrolling

**Files:**
- Modify: `templates/dashboard.html` CSS at line ~243 (`#content:has()` rule) and lines ~1550, ~1570-1572 (Ash Activity CSS)

- [ ] **Step 1: Add `#page-ash-activity.active` rule and update `#content:has()` override**

Add new rule near the existing `#page-ash-inbox.active` rule (~line 1550):

```css
#page-ash-activity.active { display:flex; flex-direction:column; width:100%; height:100%; overflow:hidden; }
```

Update the existing `#content:has()` rule at **line 243** (NOT in the 1550 block) to also match activity:

```css
#content:has(#page-ash-inbox.active), #content:has(#page-ash-activity.active) { overflow:hidden; display:flex; flex-direction:column; }
```

- [ ] **Step 2: Make `.ash-activity-two-col` fill remaining height**

Change:
```css
.ash-activity-two-col { display:grid; grid-template-columns:40fr 60fr; gap:16px; align-items:start; }
```
To:
```css
.ash-activity-two-col { display:grid; grid-template-columns:40fr 60fr; gap:16px; align-items:stretch; flex:1; min-height:0; }
```

- [ ] **Step 3: Make left and right columns flex + scroll internally**

Change:
```css
.ash-act-left { display:flex; flex-direction:column; }
.ash-act-right { display:flex; flex-direction:column; }
```
To:
```css
.ash-act-left { display:flex; flex-direction:column; min-height:0; overflow:hidden; }
.ash-act-right { display:flex; flex-direction:column; min-height:0; overflow:hidden; }
```

- [ ] **Step 4: Make `#ash-activity-feed` scroll internally**

Insert new CSS rule immediately after `.ash-act-right` rule (~line 1572):
```css
#ash-activity-feed { flex:1; overflow-y:auto; padding-right:6px; scroll-behavior:smooth; }
#ash-activity-feed::-webkit-scrollbar { width:0px; background:transparent; }
```

- [ ] **Step 5: Make `#ash-weekly` non-scrolling (fits in view)**

The weekly comparison table is small — it should not need its own scroll. No change needed unless it overflows. Leave as-is.

- [ ] **Step 6: Verify scroll behavior**

Load dashboard → Ash Activity. Stats row and column headers should stay pinned. Activity feed should scroll internally. Page-level scrollbar should not appear.

- [ ] **Step 7: Commit**

```bash
git add templates/dashboard.html
git commit -m "fix(ash): activity page uses internal column scrolling, no page-level scroll"
```

---

## Task 4: Verify Full Integration

**Files:** None (verification only)

- [ ] **Step 1: Restart server**

```bash
lsof -ti:5000 | xargs kill -9 2>/dev/null
cd /Users/nickbroyzer/Projects/my-assistant && source venv/bin/activate && PORT=5001 python app.py
```

- [ ] **Step 2: Test Ash Activity page**

Navigate to `http://localhost:5001/dashboard` → Ash Activity:
- Stats show today-only counts
- Activity feed grouped by "Today" and "Yesterday" with correct dates
- Feed scrolls internally
- Weekly comparison table visible in right column
- No page-level scrollbar

- [ ] **Step 3: Test Ash Inbox still works**

Navigate to Ash Inbox:
- 15 Today, 15 Yesterday, 15 Bookkeeping items
- Internal column scrolling preserved
- No regressions

- [ ] **Step 4: Test other pages unaffected**

Navigate to Jobs, Leads, Mission Control — verify no layout regressions. The `#content:has()` rule should only activate for Ash pages.

- [ ] **Step 5: Final commit if any fixups needed**

```bash
git add -A && git commit -m "fix(ash): activity tab integration verified"
```

---

## Summary

| Task | Files | What |
|------|-------|------|
| 1 | `routes/ash.py` | Dynamic timestamps + expand to 25 items + dynamic weekly |
| 2 | `dashboard.html` JS | Stats filter to today-only |
| 3 | `dashboard.html` CSS | Internal scrolling for activity columns |
| 4 | — | Integration verification |

**Estimated diff size:** ~200 lines in `routes/ash.py`, ~15 lines in `dashboard.html`
