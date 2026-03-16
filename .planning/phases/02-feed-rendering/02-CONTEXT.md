# Phase 2: Feed Rendering - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the activity feed row renderer to consume structured API fields (`sender`, `quality_score`, `type`) instead of parsing description strings. Each row displays as one clean horizontal line: `[icon] [Name] [action summary] [QS pill] [time]` — no redundant text. This phase covers JS rendering logic and minimal CSS for the QS pill. Pixel-perfect spacing/typography polish is Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Row Layout & Content
- Column order: Icon → Name → Action summary → QS pill → Time
- Name column shows `sender` field only (no company name)
- Name column uses white-space:nowrap with no fixed width — takes only the space the name needs, no truncation
- Rows have subtle hover highlight (background shift) but no click action
- Flex row layout: Icon 24px, Name auto (nowrap), Action flex:1, QS pill ~50px, Time ~60px

### Quality Score Pill
- Display format: number only with percent sign, e.g. "92%"
- Style: outlined/subtle — transparent background, colored border + colored text (not solid fill)
- Color thresholds: green >=80, orange 50-79, red <50
- If no quality_score on an item (e.g. spam_blocked), hide the pill entirely — don't show a placeholder
- Existing CSS class `.ash-feed-qs` is available but unused — activate it

### Icon Mapping
- Map from the new `type` field (call/email/sms), NOT from `action_type`
- Letters in colored circles: C (call), E (email), S (sms)
- Distinct colors per channel type (C=green, E=blue, S=purple or similar)
- Keep existing letter-in-circle style — no icon library needed

### Action Summary Text
- Content: action_type label + short context extracted from description
- Example: "Lead created — Tacoma warehouse racking inquiry"
- Derivation: strip sender name and "Quality score X" from the existing description, use remainder as summary after the action label
- Uniform styling for the whole action column (no bright/dim split between label and summary)
- Truncate with ellipsis when too long

### Claude's Discretion
- Exact hover highlight color/opacity
- Exact channel icon colors (as long as distinct per type and fitting dark theme)
- How to strip sender/QS from description (regex vs split approach)
- Whether to refactor parseAshDescription() or replace it entirely

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Feed Renderer (current implementation)
- `templates/dashboard.html` lines 11187-11243 — Current `parseAshDescription()` and `loadAshActivity()` functions (the code being rewritten)
- `templates/dashboard.html` lines 1558-1565 — Existing CSS classes for feed rows (`.ash-feed-row`, `.ash-feed-name`, `.ash-feed-action`, `.ash-feed-summary`, `.ash-feed-qs`, `.ash-feed-time`)

### API Data (Phase 1 output)
- `routes/ash.py` lines 228-420 — `ASH_ACTIVITY_DEMO` with enriched fields (`sender`, `quality_score`, `type`)
- `.planning/REQUIREMENTS.md` — FEED-01 through FEED-05, QS-01 through QS-04 acceptance criteria

### Approved Mockup
- `~/Desktop/PC-Screenshots/ash-approved-mockups.html` — Mockup 2: Ash Activity (visual target)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.ash-feed-qs` CSS class: Already defined (font-size:10px, font-weight:700, padding:1px 6px, border-radius:8px) but never rendered in the JS — just needs to be used
- `.ash-ch-icon` classes (`ch-c`, `ch-e`, `ch-s`): Already styled as colored circle backgrounds — remap from `type` field instead of `action_type`
- `actionLabels` map in `loadAshActivity()`: Maps action_type to human labels — keep and use in the action column

### Established Patterns
- Vanilla JS DOM rendering via string concatenation (`html += '<div>...'`)
- Date grouping with `lastDate` tracking — must be preserved
- Stats counters at top of function (leads, invoices, calls, nq) — unrelated to rendering, leave as-is

### Integration Points
- `loadAshActivity()` is called when navigating to ash-activity page (line 3576)
- Feed renders into `#ash-activity-feed` div (line 2130)
- `allAshActivity` global array populated from API response — used elsewhere for stats

</code_context>

<specifics>
## Specific Ideas

- The action summary should feel like a log entry: "[Action type] — [what happened]"
- Hover effect should be subtle — just enough to show the row is interactive-future, not a full button highlight

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-feed-rendering*
*Context gathered: 2026-03-16*
