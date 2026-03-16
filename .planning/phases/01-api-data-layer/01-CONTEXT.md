# Phase 1: API Data Layer - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrich `ASH_ACTIVITY_DEMO` with structured fields (`sender`, `quality_score`, `type`) so the renderer can consume them without parsing description strings. Clean up all duplicated data constants in `ash.py`. No new endpoints, no rendering changes.

</domain>

<decisions>
## Implementation Decisions

### Activity-Inbox Alignment
- Add `sender`, `quality_score`, and `type` fields directly to each `ASH_ACTIVITY_DEMO` entry (no derivation from inbox at request time)
- Activity items correspond 1:1 with inbox items where applicable (act-001 gets Brian Holloway's data from item-001, etc.)
- Extra activity items (act-011 through act-014) get their own consistent values matching the activity description content

### Field Semantics
- Keep both `type` (call/email/sms — communication channel) and `action_type` (lead_created/forwarded/etc. — outcome) on activity items
- `type` field values must be one of: `call`, `email`, `sms` (matching inbox's vocabulary)
- Keep `description` field as-is — the Phase 2 renderer will use the new structured fields for display and can ignore description
- No new fields beyond what's required (sender, quality_score, type)

### Duplicate Cleanup
- Remove the entire second block of duplicated constants in `ash.py` (lines ~328-485): `ASH_INBOX_DEMO`, `ASH_ACTIVITY_DEMO`, `ASH_WEEKLY_DEMO`, and the duplicate section header comment
- Keep the first block (lines ~105-260) — data constants defined before the routes that use them
- The enriched `ASH_ACTIVITY_DEMO` lives in the first (surviving) block

### Claude's Discretion
- Exact quality_score values for activity items act-011 through act-014 (not in inbox data)
- Sender names and type for act-011 through act-014 (infer from description text)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Data
- `routes/ash.py` — Contains both `ASH_INBOX_DEMO` (reference shape) and `ASH_ACTIVITY_DEMO` (target for enrichment), plus the `/api/ash/activity` endpoint
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-04 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ASH_INBOX_DEMO` in `routes/ash.py`: Reference data shape with all target fields (`sender`, `quality_score`, `type`, `sender_contact`, `summary`, `outcome`, etc.)

### Established Patterns
- Demo data defined as module-level Python lists/dicts in route files
- API endpoints return `jsonify()` with the demo data directly
- No database layer — all data is hardcoded constants for now

### Integration Points
- `/api/ash/activity` endpoint (line 304) returns `ASH_ACTIVITY_DEMO` — this is what the Phase 2 renderer will consume
- `/api/ash/inbox` endpoint (line 263) returns `ASH_INBOX_DEMO` — activity shape should match for shared fields

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-api-data-layer*
*Context gathered: 2026-03-16*
