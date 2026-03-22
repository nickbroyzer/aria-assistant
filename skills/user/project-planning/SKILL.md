# Project Planning Skill

## Purpose
Structure any multi-phase implementation into clear, executable phases with tool assignments, time estimates, and defined outputs. Prevents scope creep, missed steps, and confusion about who/what does each part.

## When to Use
- Starting any new feature, integration, or system
- Scoping work that spans multiple sessions
- Any task requiring coordination between Cowork, Claude Code, and user actions
- Before writing any code on a complex feature

## Planning Process

### Step 1: Research First
Before planning, gather all technical requirements:
- API documentation
- Authentication requirements
- Infrastructure dependencies
- Potential gotchas or renewal requirements
- Cost implications

Present research summary to user. Get confirmation before proceeding to planning.

### Step 2: Phase Breakdown
Organize work into logical phases. Standard phase pattern:

| Phase | Typical Content |
|-------|-----------------|
| Infrastructure | Cloud services, APIs, external accounts |
| Authentication | OAuth, API keys, service accounts |
| Database | Schema, migrations, connections |
| Backend Code | Endpoints, business logic, integrations |
| Frontend Code | UI components, API wiring |
| Integration | Connecting pieces, deployment |
| Verification | Testing, tuning, production readiness |

Not every project needs all phases. Adapt to the specific work.

### Step 3: Phase Detail Template
For each phase, use this format:

    ## **Phase N: [Phase Name]**
    *Tool: [Cowork / Claude Code / User / Mixed]*

    | Step | Task | Notes |
    |------|------|-------|
    | N.1 | [Specific action] | [Context, gotchas, dependencies] |
    | N.2 | [Specific action] | [Context, gotchas, dependencies] |

    **Phase N output:** [What "done" looks like for this phase]

### Step 4: Summary Table
End every plan with:

    ## **Summary**

    | Phase | Tool | Time estimate |
    |-------|------|---------------|
    | 1. [Name] | [Tool] | [X min] |
    | 2. [Name] | [Tool] | [X min] |

    **Total: ~[X hours]** across [N] sessions

## Tool Assignment Rules

| Tool | Use For |
|------|---------|
| **Cowork** | Browser automation, cloud console setup, GUI configuration, visual verification |
| **Claude Code** | Writing code, file creation, terminal commands, git operations |
| **User** | OAuth consent clicks, account logins, decisions requiring human judgment |
| **Mixed** | Phases requiring handoff between tools |

## Time Estimation Guidelines

| Task Type | Estimate |
|-----------|----------|
| Cloud console setup (per service) | 5-10 min |
| OAuth/auth configuration | 15-20 min |
| Database schema + migration | 20-30 min |
| Single API endpoint | 15-20 min |
| Complex integration logic | 30-45 min |
| Verification + tuning | 20-30 min |

Add buffer for troubleshooting: multiply total by 1.25 for realistic estimate.

## Plan Storage
After plan approval, save to Obsidian at:

    /Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/Plans/[Project-Name]-Plan.md

Update plan status as phases complete:
- [ ] Phase 1: Infrastructure
- [x] Phase 2: Authentication (completed 2024-03-21)

## Handoff Protocol
At phase boundaries:
1. Verify phase output matches definition
2. Screenshot/curl test as evidence
3. Commit if code was written
4. Update plan status in Obsidian
5. State next phase clearly before proceeding

## Example Usage

**User:** "I want to add Twilio SMS notifications"

**Claude Response:**
1. Research Twilio API requirements, costs, auth flow
2. Present findings, confirm scope
3. Break into phases (Infrastructure -> Auth -> Code -> Integration -> Verification)
4. Present full plan in table format
5. Get approval
6. Save plan to Obsidian
7. Execute phase by phase with handoffs
