# Ash Activity Feed Fix

## What This Is

A targeted UI fix for the Pacific Construction Dashboard's Ash Activity page. The activity feed rows currently display redundant, poorly-structured text — icon label + parsed action + name all running together. This project rewrites the feed to match the approved mockup layout: `[icon] [Name] [action — short summary] [quality score % pill] [time]`.

## Core Value

The Ash Activity feed must display each row in the exact layout from the approved mockup — one clean horizontal line per activity item with structured, non-redundant data.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Activity API returns structured `sender` and `quality_score` fields per item
- [ ] Feed rows render as: icon, contact name, action summary, QS pill, timestamp
- [ ] No redundant text — each data point appears once in the correct position
- [ ] Quality score pill is color-coded (green for high, orange for medium, red for low)
- [ ] Icon type (C/E/S) matches the communication channel (call/email/SMS)
- [ ] Date grouping headers preserved (Today, Yesterday, older dates)
- [ ] CSS matches the approved mockup styling (spacing, colors, typography)

### Out of Scope

- Ash Inbox page changes — only Activity feed
- New Activity API endpoints — just enriching existing data shape
- Weekly comparison table — already working correctly

## Context

- Approved mockup: `~/Desktop/PC-Screenshots/ash-approved-mockups.html` (Mockup 2: Ash Activity)
- Current implementation: `templates/dashboard.html` (lines ~11185-11243 for JS, ~1555-1565 for CSS)
- API data: `routes/ash.py` — `ASH_ACTIVITY_DEMO` lacks `sender` and `quality_score` fields
- The inbox API (`/api/ash/inbox`) already has the right data shape with `sender`, `quality_score`, `type` — Activity needs to match
- There's a duplicate `ASH_ACTIVITY_DEMO` definition in ash.py (line 228 and line 453) that needs cleanup

## Constraints

- **Tech stack**: Flask + vanilla JS + single-file dashboard.html — no framework changes
- **Data**: Demo data only (no real backend) — enrich `ASH_ACTIVITY_DEMO` with structured fields
- **Scope**: Surgical fix — don't touch other Ash pages or dashboard components

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Enrich activity API data rather than parse from description strings | Parsing is fragile; inbox API already has the right shape | — Pending |
| Match inbox item data structure (sender, quality_score, type) | Consistency between Ash endpoints | — Pending |

---
*Last updated: 2026-03-16 after initialization*
