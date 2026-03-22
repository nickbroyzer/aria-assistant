---
name: session-start
description: Loads session context for Pacific Construction dashboard — git status, recent commits, and latest Obsidian session note. Run at the start of every new work session after handoff.
disable-model-invocation: true
---

# Session Start — Load Context

Run these steps in order and display the results:

1. Show current git state:
   - Current branch
   - Last 3 commits (oneline)
   - Any uncommitted changes (git status --short)

2. Find and read the most recent Obsidian session note:
   - Look in: ~/Documents/Obsidian/MyVault/PC Project/
   - Find the newest file matching Session-*.md from the last 7 days
   - Display the first 40 lines of that file

3. Display these reminders:
   - GSD phase = work scope (run /gsd:progress to confirm)
   - Read planning session instructions BEFORE touching code
   - Commit at every meaningful milestone
   - Never push to Railway until full end-to-end verification
   - Use pc-verifier agent before commits
   - Use pc-explorer agent for codebase lookups (saves main context)

4. End with: "Session context loaded. Ready to work."
