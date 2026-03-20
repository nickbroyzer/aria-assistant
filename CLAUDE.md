# CLAUDE.md — Mission Control Dashboard

**Project:** Pacific Construction business management dashboard ("Mission Control")
**Client:** Jay Farber, Pacific Construction — commercial shelving/warehouse installation, Pacific WA
**Developer:** Kolya (Nikolai Broyzer) — sole developer, startup founder
**Stack:** Flask + vanilla JS/HTML/CSS SPA, JSON/JSONL file storage, Railway deployment
**Repo:** `~/Projects/my-assistant/` → GitHub `nickbroyzer/aria-assistant`
**Local dev:** `http://localhost:5001` → push to Railway when verified end-to-end
**AI assistant name:** Ash (not Aria)

---

## Identity & Communication

- Kolya is 48, a non-developer founder learning AI tools. Background in real estate, mortgage lending, and commercial cannabis cultivation — currently pivoting into AI and studying cybersecurity (CompTIA A+ track, networking concepts).
- Primary machine: MacBook Pro M5 (32GB RAM, 1TB SSD). Also has a Windows PC.
- Has a family including a young child.
- Give practical, scannable explanations. Direct answers, no hedging. Prefers SWOT-style business analysis when relevant.
- When something breaks, diagnose root cause — don't guess.
- Studies engineering and cloud/security concepts via ByteByteGo (testing hierarchy, AWS architecture, security domains).

### Pacing Rule
**One thing at a time. Wait for confirmation before moving on.**

Kolya gets overwhelmed when Claude dumps multiple steps, blocks, or instructions in a single message. The correct pattern:

1. Give ONE instruction or ONE block
2. End with a clear question: *"Done? Ready for the next step?"* or *"Does this look right?"*
3. WAIT for Kolya to respond
4. Only then proceed to the next step

**Never:**
- Drop two code blocks in one message and say "do both"
- Give a 5-step plan and expect Kolya to execute it all at once
- Say "first do X, then do Y, then do Z" in one message — give X, wait, then give Y

**The only exception:** When Kolya explicitly asks for everything at once (e.g. "just give me the whole thing"). Otherwise, default to staged delivery.

This applies everywhere: handoffs, implementation instructions, debugging steps, Cowork prompts, and file changes.

### Copy-Paste Ready Rule
**Everything Kolya needs to execute must be in a code block he can copy with one click.** 

Never give instructions as prose that Kolya has to mentally parse and retype. If it goes into a terminal, a file, a chat, or a browser — it goes in a code block.

**Correct:**
```bash
cd ~/Projects/my-assistant && git add CLAUDE.md && git commit -m "Add CLAUDE.md with project rules"
```

**Wrong:**
"Go to your project folder, then git add the CLAUDE.md file, and commit it with a message about adding project rules."

**Rules:**
- Terminal commands → bash code block, always. One block per step (pacing rule).
- File paths → in backticks so they're unambiguous: `/Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/`
- Text to paste into claude.ai chat → in a code block labeled "Paste into new chat"
- CSS values to type into Hoverify → in a code block: `.ash-three-col { grid-gap: 12px; }`
- URLs → full URL, not "go to the Railway dashboard" — give `https://railway.app/dashboard`
- If Claude is explaining something and NOT asking Kolya to do anything, prose is fine. But the moment there's an action to take, it becomes a code block.

---

## Hard Rules (Zero Tolerance)

These rules exist because violating them caused multi-hour regressions in past sessions. Every one was learned the hard way.

### The Golden Rule
**Never declare a task finished until it is verified end-to-end in the browser.**
"It looks right" is not verification. "node --check passed" is not verification. Seeing it work in the browser is verification.

### Planning First
- **ALWAYS read the planning session instructions fully before touching any code.** Sessions 15-16 proved that skipping this causes cascading failures.
- **ALWAYS read the most recent Obsidian note** in `/Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/` at session start.
- When stuck, ask the planning session for the correct fix rather than guessing.
- **Never start coding in the planning session. Never make architectural decisions in the build session.** If a build session uncovers something the plan missed, stop — return to planning before continuing.

### Implementation Methodology (Phased, Sequential)
Every feature follows this exact order. No skipping steps.

1. **Audit** — Read existing code, understand current state
2. **Backend** — Build/modify API endpoints, test with `curl`
3. **HTML** — Add markup, verify it renders
4. **CSS** — One block at a time, verify after each
5. **JS** — One function group at a time, `node --check` after each insertion, zero errors before proceeding
6. **Wire** — Connect JS to API endpoints
7. **End-to-end verify** — Full manual test of the complete flow
8. **Railway push** — Only after everything is verified locally

### Code Quality Gates
- **Never guess at field names.** Check actual endpoint responses first. Sessions 16-17 wasted hours on `sender`/`channel`/`quality_score` fields that didn't exist — the real fields were `action_type`, `description`, `timestamp`.
- **`node --check` after every JS insertion.** Zero errors before proceeding to next function group.
- **Never declare a task finished or ask to refresh until the fix is verified end-to-end.**
- **Never push to Railway until full end-to-end verification.**
- **Commit at every meaningful milestone.** Small, descriptive commits.

### UI Rules
- **Approved mockups must be followed exactly — no improvisation.**
- **Always show a visual mockup and get explicit approval before any UI implementation.**
- **When a UI issue is identified, scan the entire codebase and fix every instance at once** (global fixes, not whack-a-mole).
- **No wrapping/overflow:** If meta rows or tab bars overflow, immediately shrink font (min 10px), reduce gap (min 6px), reduce padding, widen container — all in one command, never ask first.

### Mockup Standards — Hoverify-Measured

Every mockup must be built from measured values, not Claude's assumptions. The old problem: Claude would guess viewport dimensions, sidebar widths, and font sizes — producing mockups that looked plausible but didn't match the actual dashboard. Hoverify eliminates this.

**Before building any mockup, Kolya captures a measurement set using Hoverify:**

1. Open the dashboard at `localhost:5001`, navigate to the area where the new component will live
2. Use Hoverify Inspector to hover over the **parent container** — note its exact width and height in px
3. Hover over the **sidebar** — note exact width (should be 96px but verify)
4. Hover over the **topbar** — note exact height (should be 27px but verify)
5. Hover over **adjacent elements** that the new component must align with — note their widths, heights, gaps, padding, font sizes
6. Use Hoverify's **eyedropper** to grab the exact colors from surrounding elements (background, text, borders, accents)
7. Note the **font family and sizes** Hoverify shows on neighboring text elements
8. Screenshot the area with Hoverify's capture tool for visual reference

**Then paste the measurement set into Claude Code / claude.ai:**
```
Mockup measurement set (from Hoverify):
  Parent container: [W]px × [H]px
  Sidebar: [N]px | Topbar: [N]px
  Content area: [W]px × [H]px
  Adjacent element widths: [list]
  Gaps between elements: [N]px
  Colors: background [hex], text [hex], border [hex], accent [hex]
  Font: [family] at [size]px, line-height [N]px
  [attach Hoverify screenshot]
```

**Claude builds the mockup using ONLY these values.** Rules:
- Use `aspect-ratio:W/H` on wrapper based on the measured parent container
- All widths, heights, gaps, padding in fixed px from the measurement set — never default to training data
- Font sizes miniaturized proportionally (5-10px range) to fit in chat, but ratios preserved from measurements
- Colors must be the exact hex values from the eyedropper, not approximations
- No `transform:scale()`. Full page edge-to-edge.
- If a value wasn't measured, Claude must flag it as `UNMEASURED — need Hoverify value` instead of guessing

**After mockup approval, the same measurement set carries into implementation** — no re-measuring, no drift between what the mockup showed and what gets built.

### Demo Data
- **Every feature must ship with fully realistic demo data.** No empty states, no placeholder text, no "coming soon." This is a client-facing product.

### Git Discipline
- Never push mid-session — commit locally, push only after verification.
- Small commits with descriptive messages.
- `.env` files, credential JSONs, and tokens are gitignored. Never commit secrets.

---

## Verification Techniques

These techniques force Claude to externalize reasoning before committing to an answer. Use them whenever the cost of a wrong answer is high.

### 1. Chain-of-Thought Verification
**When to use:** Claude says "this should work" without showing logic; answer involves field names, API responses, or CSS values; answer has multiple dependencies.

```
Before you give me your final answer, reason through this step by step.
Show: (1) what you know for certain from the actual code/data I've provided,
(2) what you're inferring or assuming, (3) where your reasoning could be wrong,
(4) your final answer ONLY after completing steps 1-3.
Do not skip to the answer first.
```

**Example — Session 17:** Claude was about to write JS using fields `sender`, `channel`, `quality_score`. After Chain-of-Thought, Claude stated: "I'm inferring these field names from the frontend design, not from the actual API response." Correct fields after checking: `action_type`, `description`, `timestamp`.

### 2. Best-of-N Verification
**When to use:** Calculating layout values, pixel dimensions, or formulas; Claude produced a confident numeric answer with no math shown; same question gave different answers in a previous session.

```
Solve this three separate times showing your work each time.
Then compare all three answers. If they agree: state the answer.
If any disagree: identify where reasoning diverged and which is correct.
[Your question here]
```

**Example — Sessions 9-10:** Responsive zoom calculation. Single attempt guessed `zoom = window.innerWidth / 1440`. Three-run test: all three produced `zoom = h / 1298`, matching the Fiverr dev fix. Committed as `17e7b75`.

### 3. Iterative Refinement (Self-Review)
**When to use:** Claude just wrote a function and declared it "done"; implementation feels right but untested; suspicion of off-by-one, missing condition, or edge case.

```
Here is the output you just produced: [paste output]

Review it as if you didn't write it. Look for:
1. Unconfirmed assumptions  2. Missing edge cases
3. Silent failure modes     4. Contradictions with earlier session decisions

List every issue found, then produce a corrected version.
```

**Example — Session 16:** `loadAshInbox()` had an `el is not defined` ReferenceError. Self-review caught: variable declared in outer `forEach` but not accessible inside click handler closure. Fixed before commit.

### 4. CSS Dual-Run Consistency Check
**When to use:** Claude is proposing specific pixel dimensions; about to implement a grid/flex/sidebar width; layout looked right in planning but broke in implementation.

```
Answer this layout question twice independently.
First answer: [solution + values].
Second answer: derive from first principles without referencing your first answer.
Then compare: do both produce identical px values?
Known measurements (use ONLY these): Viewport [W]x[H] | Sidebar [N]px | Topbar [N]px
[Your layout question]
```

---

## Input Restriction Techniques

By default, Claude blends your input with training data — filling gaps with assumptions. These techniques close those gaps.

### 5. External Knowledge Restriction — Documents
**When to use:** Asking about any field name, API endpoint, or database column; writing JS that references Flask routes or response objects; Claude references a general pattern instead of your actual pattern.

```
Use ONLY the code/data I've provided. Do not fill gaps with training data.
If something is missing: tell me what's missing. Do NOT invent it.
[Paste actual code / curl output / schema here]
My question: [question]
```

**Example — Session 17:** Before this technique, Claude assumed Activity endpoint returned `{ sender, channel, quality_score }`. After pasting actual curl output: `{ action_type, description, timestamp, entity_id }`. Every wrong JS reference was corrected before implementation.

### 6. External Knowledge Restriction — CSS Measurements
**When to use:** Any layout task involving specific pixel values; Claude proposes a size you didn't give it; working on a component after changing viewport setup.

```
Use ONLY these measured values. Do not default to training-data layout dimensions.
Viewport: [W]px x [H]px | Sidebar: [N]px | Topbar: [N]px | Content: [W-N]px x [H-N]px
Every px value in your answer must trace back to this list.
Task: [layout task]
```

### 7. Maximum Precision Mode (Combined)
**When to use:** Writing JS that reads API data AND renders into a measured layout; starting a new tab/section/component from scratch; previous session had a regression from assumed values.

```
MAXIMUM PRECISION MODE
Data: use ONLY this API response. Flag missing fields. [paste curl output]
Measurements: use ONLY these Hoverify values. Viewport [W]x[H] | Sidebar [N]px | Topbar [N]px
Format answer as: 1. Confirmed fields  2. Confirmed measurements  3. Implementation
```

---

## Prompting Structure

### 8. Format Specification
**When to use:** Need code in a specific form; want a list not prose; Claude over-explains when you just need implementation; building multi-step prompt sequence.

```
Format your answer as follows — do not deviate:
Section 1 — [label]: [what goes here]
Section 2 — [label]: [what goes here]
No preamble outside these sections. If info is missing: write MISSING: [reason]
```

### 9. Sequential Step Instructions
**When to use:** Implementing a full feature (backend → HTML → CSS → JS → verify → commit); task has more than two dependent steps; Claude previously skipped a step.

```
Complete these steps IN ORDER. Report output of each step before proceeding.
If any step produces unexpected output: STOP and report it.
Step 1: [action] — expected: [output]
Step 2: [action] — expected: [output]
Step 3: [action] — expected: [output]
```

### 10. Positive and Negative Examples
**When to use:** Claude keeps producing a specific wrong pattern; correct output diverges from common pattern; feature has shipped with wrong aesthetic twice or more.

```
CORRECT — produce something like this:  <good>[example]</good>
WRONG — do NOT produce this:  <bad>[example]</bad>
Key difference: [one sentence]
Now produce: [task]
```

---

## Session Protocol

### Pre-Session Checklist
Run this at the start of every build session. Do not start implementation until all items are checked.

1. Read most recent Obsidian note in `/Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/`
2. Run `/gsd:progress` — confirm current phase
3. Run `/gsd:work_scope` — confirm what this session ships
4. Identify the single highest-risk step in today's work
5. Decide which verification technique applies to that step (Chain-of-Thought, Best-of-N, Iterative Refinement, CSS Dual-Run, or External Knowledge Restriction)
6. If any new endpoints are involved: `curl` them NOW, paste response
7. If any layout work is involved: open Hoverify NOW, measure container
8. Confirm Flask is running on port 5001
9. Confirm last git commit is clean (no uncommitted changes)
10. Set session message counter to 0 — flag at 20 messages

### Techniques by GSD Phase

| GSD Phase | Techniques |
|-----------|------------|
| **Work Scope** | Chain-of-Thought to confirm what's actually broken vs assumed. External Knowledge Restriction when analyzing endpoints or schema. |
| **Plan** | Best-of-N for any measurement or formula. Positive/Negative Examples for mockup approval and layout specs. |
| **Build** | Sequential Steps (mandatory). CSS Dual-Run before any layout commit. Iterative Refinement after each function group before `node --check`. |
| **Verify** | Iterative Refinement as final self-review. QA skill trigger. Never skip — "it looks right" is not verification. |
| **Ship** | Format Specification for the session-end handoff blocks. No bash in chat block. Two blocks only. |

### Mid-Session Warning Signs
These signals mean something has gone wrong — **STOP, don't continue:**

- Claude says "this should work" with no supporting logic → apply Chain-of-Thought
- Claude references a field name you didn't confirm → stop, `curl` the endpoint
- Claude proposes a pixel value you didn't measure → stop, open Hoverify
- Two consecutive messages changed the same thing → you're in a regression loop — `git reset` to last clean commit, re-read planning notes
- Session is at 18+ messages and you're mid-implementation → start fresh session
- Claude is guessing at Flask route structure → paste your actual `app.py` routes section
- The fix introduced a new issue → `git reset` to last known-good commit, then plan

### Session End — Handoff Protocol

When Kolya says "get ready for new session", "wrap up", "handoff", or when Claude hits ~20 messages: run this protocol **one stage at a time.** Do NOT dump everything at once. Wait for Kolya's confirmation after each stage before proceeding to the next.

**STAGE 1 — Summary**
Say this and STOP. Wait for Kolya to confirm before moving to Stage 2:
```
Wrapping up. Here's what we did this session:

SHIPPED:
- [commit hash] [one-line description]
- [commit hash] [one-line description]
(or: "No commits this session")

SAFE RESTORE: [last clean commit hash on main]

CURRENT STATE:
- Flask: [running/stopped] on port [5001/other]
- Branch: [branch name]  
- Uncommitted changes: [yes (list files) / no]

Does this look right? Anything I'm missing?
```
→ WAIT for Kolya to confirm or correct.

**STAGE 2 — Chat handoff block**
After Kolya confirms Stage 1, say: *"Here's the block to paste into your new claude.ai chat:"* then give ONLY this block and STOP:
```
Session [NUMBER] handoff — [DATE]

SHIPPED:
- [commit hash] [one-line description]

SAFE RESTORE: [last clean commit hash]

PENDING (next session):
- [ ] [specific task 1]
- [ ] [specific task 2]
(or: "Clean — no carryover")

VALUES FOR NEXT SESSION:
[Hoverify measurements / curl responses / field names / "No carried values"]
```
Then say: *"Paste that into a new claude.ai chat when you start next session. Ready for the terminal block?"*
→ WAIT for Kolya to confirm.

**STAGE 3 — Terminal block**
After Kolya confirms Stage 2, say: *"Paste this into Claude Code terminal:"* then give ONLY this block:
```bash
# Write session note
cat > "/Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/Session-[DATE].md" << 'OBSIDIAN'
# Session [NUMBER] — [DATE]

## Completed
- [commit hash] [description]

## Current State
- Branch: [branch name]
- Last clean commit: [hash]

## Unresolved
- [issue or "None"]

## Next Session
- [ ] [task 1]

## Carried Values
[measurements, field names, or "None"]
OBSIDIAN

# Check status
/gsd:progress
git status
git log --oneline -3
```
Then say: *"You're set. Start a fresh session when ready."*
→ Session is over. Do not add anything else.

**HANDOFF RULES:**
- **Three stages. Three pauses.** Never combine stages. Never skip the wait.
- Output 1 (chat block) is plain text. No bash. No code fences around the whole thing.
- Output 2 (terminal block) is a single bash block. No prose inside it.
- Never add commentary or extra tips after Stage 3. The handoff ends with *"You're set."*
- If Kolya didn't ship anything: SHIPPED says "No commits this session."
- VALUES FOR NEXT SESSION is never empty — always "No carried values" at minimum.

### Session Length
At ~20 messages, proactively suggest starting a fresh session. Don't wait to be asked. Say it plainly: *"We're at ~20 messages — recommend starting a new session. Want me to run the handoff?"*

---

## Failure Mode Decision Tree

When something feels wrong mid-session, run through this:

1. **Is Claude citing a field name, endpoint, or schema you didn't confirm?** → External Knowledge Restriction + curl the endpoint
2. **Is Claude using a pixel value you didn't measure?** → CSS Measurement Restriction + open Hoverify
3. **Did Claude say "this should work" with no logic shown?** → Chain-of-Thought Verification
4. **Did Claude just write a function and declare it done?** → Iterative Refinement + `node --check`
5. **Are two consecutive messages fixing the same thing?** → STOP. `git reset` to last clean commit. Re-read planning notes.
6. **Is a numeric value uncertain (layout, formula, measurement)?** → Best-of-N — run it three times
7. **Is the output format wrong again despite corrections?** → Positive + Negative Examples

---

## Failure Mode Reference

| Failure Mode | Where It Showed Up | Fix / Prevention |
|---|---|---|
| Invented field names | Ash tab JS (Sessions 16-17): used `sender`, `channel` instead of `action_type`, `description` | External Knowledge Restriction — always curl endpoint first |
| Assumed layout dimensions | Responsive zoom (Sessions 9-10): used 1440px instead of measured 1737px | CSS Measurement Restriction — measure with Hoverify first |
| Silent JS errors | `el is not defined` ReferenceError in Ash Inbox click handler (Session 17) | Iterative Refinement + `node --check` after every function group |
| Confident wrong answer | Blueprint refactor (Sessions 11-13): declared "complete" before end-to-end verify | Chain-of-Thought — never accept "this should work" without logic shown |
| Format drift in handoffs | Session start blocks contained bash commands mixed with chat paste blocks | Format Specification — two blocks rule, enforced every session |
| Regression from bulk edits | Session 15 bulk JS insertion caused cascading failures across the file | Sequential Steps — one function group at a time, check after each |
| Wrong viewport mockup size | Mockups at 1440px real size, unviewable in chat | Positive/Negative Examples — established correct mockup format |
| Schema invented from context | Blueprint refactor guessed utility module structure from general Flask patterns | External Knowledge Restriction — read actual `app.py` first |
| Skipped verification step | Declared done before QA check in multiple sessions pre-S16 | QA skill trigger — mandatory before any commit |
| Two answers, different values | CSS grid calculations gave different column widths in planning vs build | Best-of-N — if runs 1 and 2 disagree, the value is unreliable |

---

## Architecture Overview

**Single-page app:** `templates/dashboard.html` (623KB all-in-one SPA — HTML/CSS/JS, no build step)

**Backend layers:**
- `app.py` — Flask app creation, blueprint registration, daemon startup (42 lines)
- `routes/*.py` — 8 blueprints (jobs, leads, invoices, people, payroll, settings, ash, etc.)
- `utils/data.py` — Centralized file I/O with file-lock synchronization
- `utils/auth.py` — Session management, `@require_auth`, `@require_owner` decorators
- `utils/config.py` — `config.json` management, integration credentials via `_integ_val()`
- `utils/constants.py` — All file paths, system prompt, defaults, env vars
- `utils/activity.py` — Append-only audit log to `activity_log.jsonl`

**Data storage:** JSON/JSONL flat files (jobs.json, leads.jsonl, invoices.json, people.json, payroll.json, etc.) with file-lock safety via `utils/file_locks.py`.

**Background daemons:** Quote follow-up sequences, Gmail invoice polling — started on app boot.

**Key integrations:** Google Calendar (OAuth, UTC→Pacific timezone), Gmail (OAuth, invoice inbox polling), Retell AI (phone secretary — SIP routing issue unresolved), Twilio SMS (deferred).

---

## Ash Tab (AI Assistant Interface)

The Ash tab has Inbox and Activity sub-pages with four confirmed API endpoints:
- `/api/ash/inbox/stats` — inbox statistics
- `/api/ash/inbox` — inbox messages
- `/api/ash/activity` — activity feed
- `/api/ash/weekly` — weekly summary table

Sessions 14-17 built this tab. Key lessons:
- Bulk JS insertion fails — always insert one function group at a time.
- The `el is not defined` ReferenceError in Session 17 was caused by scope issues in `showPage()` wiring.
- Field names from these endpoints: `action_type`, `description`, `timestamp`. No `sender`, `channel`, or `quality_score`.

---

## Responsive Zoom

The dashboard was designed on an external display and clipped on MacBook Pro. The correct fix (from Fiverr developer, commit `17e7b75`):

```javascript
zoom = h / DESIGN_HEIGHT  // DESIGN_HEIGHT = 1298
```

**Rule:** Never guess layout values, always calculate mathematically.

Skill file: `~/Projects/my-assistant/skills/user/responsive-zoom/SKILL.md`

---

## Layout & Design Workflow

**The playground has been retired.** It added a translation layer that introduced its own bugs — components that looked correct in the playground would break when placed inside the actual dashboard with the sidebar, topbar, zoom calculation, and surrounding sections. All layout and design work happens directly on the live dashboard.

### Core Principle
Claude cannot see the screen. Every layout fix where Claude writes CSS blind is a guess. The workflow below eliminates guessing by making Kolya the eyes and Claude the typist.

### Required Tool: Hoverify
Chrome extension — $30/year or $89 lifetime. Install from Chrome Web Store (developer: tryhoverify.com). This is the primary CSS inspection and editing tool for all layout work.

### The Layout Fix Protocol

**Phase 1 — Identify (Kolya in browser)**

1. Open the dashboard at `localhost:5001` and navigate to the broken section
2. Activate Hoverify Inspector (hover over the problem element)
3. Read the current CSS values Hoverify shows — note the selector, current property values, and the computed box model (margin, padding, border, content size)
4. If the issue is spacing: use Hoverify's **CSS Box visualization** to see exactly where the extra/missing space is — margin vs padding vs border vs content
5. If the issue is color/theme: use Hoverify's **eyedropper** to grab the exact color values from elements that look correct
6. Screenshot the current broken state using Hoverify's capture tool (annotate if helpful)

**Phase 2 — Experiment (Kolya in browser)**

7. Use Hoverify's **live CSS editor** to adjust values in real-time directly on the page — change grid gaps, widths, padding, font sizes, colors until the layout looks correct
8. If testing responsive behavior: use Hoverify's **responsive viewer** to see the change across multiple viewport sizes simultaneously
9. Once it looks right, note the **exact values** you changed:
   - Which selector (e.g. `.ash-three-col`, `#activity-feed .row`)
   - Which properties (e.g. `grid-gap`, `padding`, `font-size`)
   - What the new values are (e.g. `12px`, `8px 14px`, `13px`)
   - Screenshot the corrected state

**Phase 3 — Commit (Claude Code)**

10. Tell Claude Code the exact changes — e.g. *"In dashboard.html, set `.ash-three-col` grid-gap to 12px, `.feed-row` padding to 8px 14px"*
11. Claude Code writes the values into the source file — no proposing alternatives, no "I think it should be", just the exact values Kolya specified
12. Claude Code runs a quick sanity check — is the selector correct? Does it exist in the file? Are there conflicting rules elsewhere that would override this?
13. If Claude Code finds a conflicting rule: report it to Kolya with both selectors and their specificity, don't silently fix it

**Phase 4 — Verify (Cowork)**

14. Cowork refreshes the browser and takes a screenshot
15. Screenshot saved to `/Users/nickbroyzer/Desktop/PC-Screenshots/[descriptive-name].png`
16. Kolya confirms the screenshot matches what they saw in Phase 2
17. If it matches: commit. If it doesn't: something overrode the change — go back to Phase 1

### When to Use Which Hoverify Feature

| Problem | Hoverify Feature | What to Look For |
|---|---|---|
| Element is the wrong size | Inspector + Box Model | Check if it's content, padding, margin, or border causing the size |
| Spacing between elements is off | CSS Box visualization | Hover both elements — is it margin on one, padding on the other, or gap on the parent? |
| Colors don't match the design | Eyedropper | Grab the correct color from a reference element, compare hex values |
| Can't figure out which CSS rule is winning | Inspector → Code tab | Shows all selectors affecting the element with specificity order |
| Layout breaks at different screen sizes | Responsive viewer | Test synced interactions across viewports — spot where it breaks |
| Need to show Claude what's wrong | Screenshot + Annotate | Capture, draw arrows/boxes on the problem area, paste into chat |
| Quick "what if" test before committing | Live CSS editor | Change values in real-time, see result instantly, revert if wrong |

### Rules (Zero Tolerance)

- **Claude Code NEVER proposes pixel values for layout.** All pixel values come from Kolya's measurements via Hoverify.
- **No layout change is complete without a Cowork screenshot.** Period.
- **If Kolya says "fix the spacing" without giving values:** Claude Code must ask for the exact values, or ask Kolya to inspect with Hoverify and report back. Do not guess.
- **Global fix rule still applies:** When a spacing/layout issue is found, Claude Code scans the entire file for the same pattern and fixes every instance — not just the one Kolya pointed at.
- **Hoverify's live edits are temporary.** They disappear on page refresh. The source of truth is always `dashboard.html`. Every change must be written into the source file by Claude Code.

### Enforcement Gates

Rules only work if there are hard stops that prevent skipping them. These gates are checkpoints where Claude Code **must pause and cannot proceed** without the required input.

**GATE 1 — No measurements, no work.**
Before writing ANY CSS/layout change, Claude Code must confirm it has received at least one of:
- Exact pixel values from Kolya (e.g. "set gap to 12px")
- A Hoverify measurement set (the structured block with container sizes, colors, fonts)
- A screenshot with annotated values

If none of these are present, Claude Code responds with:
> "I need measurements before I can make this change. Can you open Hoverify, inspect [the element], and give me the selector, current values, and what you want them changed to?"

Claude Code does NOT say "I'll try..." or "Based on the code, I think..." — it asks for measurements. Full stop.

**GATE 2 — Mockup requires measurement set.**
Before building ANY mockup, Claude Code must confirm it has received a measurement set (see Mockup Standards section). If Kolya says "build me a mockup for [new feature]" without measurements, Claude Code responds with:
> "I need a Hoverify measurement set before building this mockup. Can you hover over the parent container where this will go and give me: container width × height, adjacent element sizes, gaps, colors (hex from eyedropper), and font sizes?"

**GATE 3 — No commit without screenshot.**
After writing a layout change, Claude Code must generate the Cowork verification prompt. Claude Code does NOT say "done, refresh to check" — it produces the full Cowork prompt with refresh + screenshot steps. If Kolya confirms the screenshot matches: commit. If not: investigate.

**GATE 4 — Conflicting rules require human decision.**
If Claude Code finds that writing the requested CSS value would be overridden by another rule (higher specificity, `!important`, media query), Claude Code must STOP and present both rules to Kolya. Claude Code does NOT silently add `!important` or restructure selectors without approval.

### Self-Check: How Claude Catches Itself

Before writing any layout CSS, Claude Code runs this internal check:

1. **Am I about to write a pixel value that Kolya didn't give me?** → STOP. Ask for measurement.
2. **Am I about to "improve" or "adjust" a value Kolya specified?** → STOP. Write exactly what was asked.
3. **Am I proposing a layout change based on reading the code instead of visual measurement?** → STOP. Code reading tells you what the CSS says, not what it looks like. Ask Kolya to verify visually.
4. **Did I skip the Cowork screenshot step because "it's a small change"?** → No such thing as too small. Generate the Cowork prompt.
5. **Am I about to say "this should fix it"?** → That phrase is banned. Say "I've written the values you specified — here's the Cowork prompt to verify."

### Cowork Prompt Format

**General rule (all Cowork prompts, not just layout):**
Every Cowork prompt MUST be a single fully copy-pasteable code block. Never split across multiple blocks. The LAST two steps inside the block MUST always be:
- Second-to-last: *"Display a summary of all changes made with a copy button so it can be pasted back into the Claude chat window."*
- Last: *"Save a screenshot of the final result to /Users/nickbroyzer/Desktop/PC-Screenshots/[descriptive-name].png"*

Never place these outside the code block. Never omit them.

**For layout verification specifically,** the prompt includes:
```
1. [The actual CSS change Claude Code made]
2. Refresh the browser at localhost:5001
3. Navigate to [the specific page/tab]
4. Display a summary of all changes made with a copy button
5. Save a screenshot to /Users/nickbroyzer/Desktop/PC-Screenshots/[descriptive-name].png
```

### If Hoverify Is Unavailable
Re-install it. Chrome Web Store → search "Hoverify". Do not fall back to manual DevTools — Hoverify is the standard tool for this project.

---

## Blueprint Revert History

Session 11 identified that a blueprint refactor (splitting `app.py` into 14 utility modules and 6 route blueprints) caused a sharp productivity drop. The Ash tab was reverted after minified HTML caused cascading failures. Session 12 reverted to clean single `app.py` (commit `a3f8305`), then rebuilt Ash tab cleanly.

**Lesson:** Large refactors without incremental verification are dangerous. Always verify after each small change.

---

## Known Issues & Tech Debt

- **Zero automated tests.** pytest for Flask routes flagged as needed but not implemented.
- **No MFA, no RBAC, no backups.** Security gaps documented but not addressed. Reference: ByteByteGo 12 security domains — Auth=MFA, Authz=RBAC, Encryption=TLS+at-rest, API=OAuth2+rate limit+input validation, 3rdParty=vendor risk (Retell/Twilio/Gmail), DR=backups+redundancy.
- **API keys leaked once in git history.** A full git history rewrite was performed to scrub them. All secrets are now externalized via `.env` (gitignored). If adding new integrations, verify credentials are in `.env` BEFORE committing.
- **Retell AI SIP routing issue** sent to Retell support, unresolved.
- **Twilio SMS integration** deferred due to technical issues.
- **623KB single HTML file** — the dashboard.html is massive. Works but is a maintenance challenge.

---

## Installed Dev Tools

- **GSD** — Build process manager (manual phases)
- **obra/superpowers** (Jesse Vincent) — Agentic skills framework, triggers automatically. Installed Session 23 (2026-03-17).
- **Future:** gstack (Garry Tan/YC) — 6 Claude Code skills for role-based dev. Repo: `https://github.com/garrytan/gstack`
- **Future:** Context 7 plugin — for Retell API integration work. Command: `/plugin add context-7`
- **Future:** Warp Terminal (warp.dev) — quality-of-life terminal upgrade. Remind Kolya to try when he has a free 10 minutes.

---

## Coding Conventions (Reference)

- Python: `snake_case`, 4-space indent, PEP 8 informal
- Routes: Blueprint pattern with `_bp` suffix
- Functions: Public `snake_case`, private `_underscore_prefix`
- Auth decorators: `@require_auth`, `@require_owner`
- Frontend: Vanilla JS, fetch API, no framework, no build step
- CSS: Custom properties (CSS variables), dark theme
- Data access: Always through `utils/data.py`, never direct file I/O

See `.planning/codebase/` for detailed docs:
- `ARCHITECTURE.md` — Full system architecture
- `CONVENTIONS.md` — Naming and code style
- `CONCERNS.md` — Known bugs and tech debt
- `INTEGRATIONS.md` — External API details
- `STACK.md` — Technology stack
- `STRUCTURE.md` — File organization
- `TESTING.md` — Test strategies

---

## Post-Build Business Checklist

Remind Kolya after the dashboard ships:
1. Pick a business name
2. Register LLC in Washington state ($200 at Secretary of State website)
3. Open business bank account
4. Build simple one-page website
5. Document Pacific Construction build as sales deck
6. Develop client pitch and value-based pricing strategy
