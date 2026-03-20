# Requirements: Ash Activity Feed Fix

**Defined:** 2026-03-16
**Core Value:** Feed rows match the approved mockup — one clean horizontal line per activity with no redundant data

## v1 Requirements

### API Data

- [x] **DATA-01**: Activity items include `sender` field (contact/company name)
- [x] **DATA-02**: Activity items include `quality_score` field (integer 0-100)
- [x] **DATA-03**: Activity items include `type` field (call/email/sms)
- [x] **DATA-04**: Duplicate `ASH_ACTIVITY_DEMO` definition cleaned up

### Feed Renderer

- [x] **FEED-01**: Each row renders as: `[icon] [Name] [action — summary] [QS pill] [time]`
- [x] **FEED-02**: Icon shows C/E/S based on communication channel type
- [x] **FEED-03**: Name column shows contact/company name (bold, white)
- [x] **FEED-04**: Action column shows short action summary (dimmed, truncates with ellipsis)
- [x] **FEED-05**: No redundant text — each piece of data appears exactly once

### Quality Score Pill

- [x] **QS-01**: Quality score displays as percentage in colored pill
- [x] **QS-02**: Green pill for scores >= 80%
- [x] **QS-03**: Orange pill for scores 50-79%
- [x] **QS-04**: Red pill for scores < 50%

### Styling

- [ ] **CSS-01**: Feed rows use flex layout with proper spacing matching mockup
- [ ] **CSS-02**: Date group headers preserved (Today, Yesterday, older dates)
- [ ] **CSS-03**: Typography and colors match approved mockup

## v2 Requirements

(None — this is a focused fix)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Ash Inbox page changes | Only fixing Activity feed |
| New API endpoints | Enriching existing data shape only |
| Weekly comparison table | Already works correctly |
| Click-to-detail panel on activity rows | Not in current scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| FEED-01 | Phase 2 | Complete |
| FEED-02 | Phase 2 | Complete |
| FEED-03 | Phase 2 | Complete |
| FEED-04 | Phase 2 | Complete |
| FEED-05 | Phase 2 | Complete |
| QS-01 | Phase 2 | Complete |
| QS-02 | Phase 2 | Complete |
| QS-03 | Phase 2 | Complete |
| QS-04 | Phase 2 | Complete |
| CSS-01 | Phase 3 | Pending |
| CSS-02 | Phase 3 | Pending |
| CSS-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 after roadmap creation*
