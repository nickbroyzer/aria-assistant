---
name: handoff-protocol
description: Three-stage, three-pause session handoff process for Pacific Construction dashboard sessions. Trigger when the user says "wrap up", "end session", "handoff", "new session", "get ready for new session", or when message count hits 20. Also trigger at message 15 to warn about wrapping up soon, and at message 18 to offer handoff. NEVER combine stages. NEVER skip waits. NEVER mix chat blocks with terminal blocks.
---

# Session Handoff Protocol

This skill ensures clean session transitions with zero context loss. It exists because previous sessions ended abruptly, losing critical values, dimensions, and next steps.

**RULE: Three stages, three pauses. Never combine. Never skip waits.**

---

## Pre-Handoff Checklist

Before starting Stage 1, verify you know:

- [ ] Commit hashes for everything shipped this session
- [ ] The safe restore point (last known-good commit, all tests green)
- [ ] Any specific values that must carry over (pixel dimensions, field names, config values)
- [ ] Whether there's an unresolved bug that needs "BUG FIX" label
- [ ] Current GSD phase

If any of these are unclear, gather the info before starting handoff.

---

## When To Trigger

| Trigger | Action |
|---------|--------|
| Message count hits 15 | Mention wrapping up soon |
| Message count hits 18 | Offer to start handoff |
| Message count hits 20 | Begin handoff automatically |
| User says "wrap up", "end session", "handoff", "new session" | Begin handoff |

---

## Stage 1 — Summary

Provide a summary of the session:

1. **Session number** (e.g., "Session 23")
2. **What shipped** — commits with hashes, features completed
3. **Safe restore point** — the last known-good commit hash
4. **Current state** — what's working, what's pending
5. **Unresolved issues** — if any

Format as prose or short list. End with:

> **STAGE 1 COMPLETE. Ready for Stage 2?**

**STOP. WAIT for user confirmation before proceeding.**

---

## Stage 2 — Chat Handoff Block

Provide a **plain text block** for Kolya to paste into a **new claude.ai chat**.

**CRITICAL: This is plain text only. No bash commands. No executable code. No code fences around the whole block.**

Structure:

Session: [Title]
Previous session: [Previous Title]
GSD PHASE: [Current phase — work scope / ship / review / etc.]
SHIPPED LAST SESSION:
- [Item 1 — commit abc1234]
- [Item 2 — commit def5678]
SAFE RESTORE: commit [hash] ([description of what's known working])
VALUES TO PRESERVE:
- [Specific dimensions, e.g., "sidebar width: 96px"]
- [Field names, e.g., "API returns action_type not sender"]
- [Config values, e.g., "PORT=5001"]
CURRENT STATE:
- [What's working]
- [What's pending]
NEXT STEPS:
- [Specific instruction with exact values — never vague]
- [Second instruction if applicable]
CONTEXT:
- [Any critical context the next session needs]
STALE WARNING: Re-read any files before editing — previous session's view output is outdated.

**Rules for this block:**
- Include exact commit hashes, not "the last commit"
- Include exact pixel values, not "make it wider"
- Include exact field names, not "the API fields"
- If a bug is pending, prefix with "BUG FIX:" so next session knows
- GSD phase tells the next session what work scope to follow

End with:

> **STAGE 2 COMPLETE. Copy that block and paste into a new claude.ai chat. Ready for Stage 3?**

**STOP. WAIT for user confirmation before proceeding.**

---

## Stage 3 — Terminal Instructions (Claude Code)

Provide instructions for Claude Code terminal. This is the final message — no questions, no waits after this.

**Two tasks:**

1. **Write session note to Obsidian**
   
   Path: /Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/Session-YYYY-MM-DD.md
   
   Content should include:
   - Date and session number
   - What was completed
   - Current state
   - Unresolved issues
   - Next steps with specific values

2. **Run GSD progress check**
   
   Command: /gsd:progress (this is a Claude Code slash command, not bash)

End with:

> **You're set.**

Nothing else. Session is closed.

---

## Message Counter

Track message count internally. Include [Message N/20] on substantive responses.

| Count | Action |
|-------|--------|
| 1-14 | Normal responses with counter |
| 15 | Add: "We're at message 15 — should start thinking about wrapping up." |
| 18 | Add: "Message 18 — want me to start the handoff?" |
| 20 | Begin Stage 1 automatically |

Can skip counter on quick confirmations like "got it" or "yes".

---

## Rules

1. **NEVER combine stages.** Each stage is a separate message with a pause between.
2. **NEVER skip waits.** User must confirm before proceeding to next stage.
3. **NEVER mix formats.** Stage 2 = plain text for chat. Stage 3 = instructions for terminal.
4. **NEVER use vague references.** Exact commits, exact pixels, exact field names.
5. **NEVER forget bug labels.** Unresolved bugs get "BUG FIX:" prefix.
6. **NEVER ask questions in Stage 3.** Deliver and close.
7. **NEVER include bash in Stage 2.** It's a chat context block, not executable code.
8. **NEVER skip the stale warning.** Previous session's file views are always outdated.

---

## Common Mistakes This Skill Prevents

| Mistake | Prevention |
|---------|------------|
| Lost pixel dimensions | VALUES TO PRESERVE section |
| Lost field names | VALUES TO PRESERVE section |
| Mixed up commit hashes | Explicit hashes in SHIPPED section |
| Vague next steps | Require exact values in NEXT STEPS |
| Terminal commands in chat block | Separate Stage 2 (chat) from Stage 3 (terminal) |
| Forgot GSD phase | GSD PHASE field in Stage 2 |
| Stale file edits | STALE WARNING reminder |
| Skipped Obsidian note | Stage 3 requires it |

---

## Project Reference

- Obsidian path: /Users/nickbroyzer/Documents/Obsidian/MyVault/PC Project/
- Session note format: Session-YYYY-MM-DD.md
- GSD command: /gsd:progress (Claude Code slash command)
- Repo: github.com/nickbroyzer/aria-assistant
- Flask port: 5001 (primary) or 5000 (fallback)
