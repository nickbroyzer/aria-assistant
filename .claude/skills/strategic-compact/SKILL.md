---
name: strategic-compact
description: Suggests context compaction at logical breakpoints during Pacific Construction dashboard sessions. Auto-invokes when context usage is high and a natural pause point is detected.
---

# Strategic Compaction

Monitor context usage and suggest /compact at logical breakpoints:

## When to suggest compaction:
- After completing a phase (backend done, moving to HTML)
- After a successful git commit
- After resolving a bug (before moving to next task)
- When switching between tabs/features (Ash -> Orders -> etc)

## How to compact:
Suggest the command with preservation instructions:

    /compact Focus on: current implementation state, pending tasks,
    API field names in use, CSS class names, last commit hash,
    and any unresolved issues. Discard: exploration output,
    verbose error logs, resolved debugging steps.

## When NOT to compact:
- Mid-implementation (between writing HTML and its CSS)
- While debugging (need the error context)
- Right before a commit (need the full diff context)
