# Roadmap: Ash Activity Feed Fix

## Overview

Three-phase surgical fix: enrich the Activity API data to match the Inbox shape, rewrite the feed renderer to display structured rows with quality score pills, then polish styling to match the approved mockup. Each phase builds on the last — data first, rendering second, visual polish third.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: API Data Layer** - Enrich activity items with structured fields and clean up duplicate definitions
- [ ] **Phase 2: Feed Rendering** - Rewrite row renderer with structured layout and quality score pills
- [ ] **Phase 3: Visual Polish** - Match approved mockup spacing, typography, and colors

## Phase Details

### Phase 1: API Data Layer
**Goal**: Activity API returns clean, structured data that the renderer can consume without parsing description strings
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. `/api/ash/activity` response includes `sender`, `quality_score`, and `type` fields on every item
  2. Only one `ASH_ACTIVITY_DEMO` definition exists in `ash.py` (duplicate removed)
  3. Activity data shape matches the existing Inbox data shape for shared fields
**Plans:** 1 plan

Plans:
- [ ] 01-01-PLAN.md — Enrich ASH_ACTIVITY_DEMO and remove duplicate constants block

### Phase 2: Feed Rendering
**Goal**: Each activity row displays as one clean horizontal line with icon, name, action summary, quality score pill, and timestamp — no redundant text
**Depends on**: Phase 1
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, QS-01, QS-02, QS-03, QS-04
**Success Criteria** (what must be TRUE):
  1. Each feed row shows exactly: channel icon (C/E/S), contact name, action summary, QS percentage pill, and timestamp — in that order
  2. Quality score pill is green (>=80), orange (50-79), or red (<50)
  3. No data appears more than once per row — icon label, parsed action, and name are not concatenated together
  4. Date grouping headers (Today, Yesterday, older dates) still separate rows correctly
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Visual Polish
**Goal**: Feed rows match the approved mockup pixel-for-pixel in layout, spacing, and color
**Depends on**: Phase 2
**Requirements**: CSS-01, CSS-02, CSS-03
**Success Criteria** (what must be TRUE):
  1. Feed rows use flex layout with spacing that matches the approved mockup screenshot
  2. Typography (font sizes, weights, colors for name vs action vs timestamp) matches mockup
  3. Date group headers are visually consistent with the rest of the feed styling
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. API Data Layer | 0/1 | Not started | - |
| 2. Feed Rendering | 0/1 | Not started | - |
| 3. Visual Polish | 0/1 | Not started | - |
