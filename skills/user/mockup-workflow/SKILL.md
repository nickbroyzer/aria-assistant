---
name: mockup-workflow
description: Hoverify-first mockup workflow for the Pacific Construction dashboard. Use this skill whenever creating visual mockups, layout previews, or UI designs for approval before implementation. Triggers include "mockup", "show me what it will look like", "preview", "design this", "lay it out", or any request to visualize a planned UI change. This skill ensures mockups use real viewport dimensions from Hoverify instead of guesses, preventing layout mismatches between mockup and final implementation.
---

# Mockup Workflow — Hoverify-First Process

This skill captures the exact mockup process that produces accurate, implementation-ready previews. Previous sessions wasted hours because mockups used guessed dimensions that didn't match the real viewport. This process fixes that.

---

## The Core Rule

**Get real measurements from Hoverify FIRST — never guess viewport dimensions.**

Hoverify is a Chrome extension ($30/yr) that shows exact rendered pixel values when hovering over elements. It replaced DevTools as the primary measurement tool because it's faster and shows computed values directly.

---

## Step 1 — Get viewport dimensions from Hoverify

Ask the user to:

1. Open the dashboard in Chrome
2. Hover over the outermost container (the main content area, not the browser window)
3. Read the rendered width x height in pixels (e.g., 1737x973)

**Never proceed without these numbers.** If the user can't provide them, explicitly state you're estimating and flag that the mockup may not match reality.

---

## Step 2 — Calculate the mockup dimensions

Use the real viewport dimensions to set the aspect ratio:

    aspect-ratio: [width] / [height]

Example: If Hoverify shows 1737x973, the mockup wrapper uses:

    .mockup-wrap {
      width: 100%;
      aspect-ratio: 1737 / 973;
    }

This ensures the mockup scales proportionally at any chat width while maintaining exact proportions.

---

## Step 3 — Apply fixed layout values

These values are constants from the PC Dashboard design:

| Element | Value |
|---------|-------|
| Sidebar width | 96px fixed |
| Topbar height | 27px fixed |
| Font sizes | 5-10px throughout |
| Card border-radius | 10px |
| Modal border-radius | 16px |

**Never use:**
- transform: scale() — causes blurry text
- em units — unpredictable scaling
- Large fonts — mockups are miniaturized previews

---

## Step 4 — Use fixed pixel widths for columns

Column widths should be in fixed pixels, not percentages. This prevents rounding errors and ensures the mockup matches implementation exactly.

Example for a 3-column layout in a 1641px content area (1737 - 96 sidebar):

    .col-1 { width: 400px; }
    .col-2 { width: 400px; }
    .col-3 { width: 400px; }
    /* Gap: ~220px distributed */

**Math check:** Always verify column widths + gaps = content area width.

---

## Step 5 — Show full page edge-to-edge

Every mockup must show:

- Complete sidebar (96px, dark, with icons)
- Complete topbar (27px)
- All visible sections in the viewport
- No cropping or partial views

The user should see exactly what their browser shows, miniaturized.

---

## Step 6 — Get explicit approval before implementation

After showing the mockup, ask:

> "Does this layout match what you want? Confirm before I write any code."

**Do not proceed to implementation until you receive explicit approval** like "yes", "looks good", "approved", or "go ahead".

If the user says "that's not right", "too wide", "wrong spacing", etc. — rebuild the mockup. Never proceed with a questioned design.

---

## Step 7 — Document the measurements for implementation

Once approved, record the exact values that will be used in implementation:

    APPROVED MOCKUP VALUES:
    - Viewport: 1737 x 973
    - Content area: 1641px (1737 - 96 sidebar)
    - Column 1: 400px
    - Column 2: 400px
    - Column 3: 400px
    - Gap: 20px
    - Card height: 120px

These values go directly into the CSS. No interpretation, no rounding.

---

## Hoverify Quick Reference

**Installation:** Chrome Web Store -> Hoverify ($30/year)

**Usage:**
1. Click Hoverify extension icon to activate
2. Hover over any element
3. Read dimensions in the overlay tooltip
4. Click to copy values

**What to measure:**
- Viewport: hover over main or outermost content container
- Cards: hover over individual card elements
- Gaps: measure adjacent elements and subtract

---

## Common Mistakes This Process Prevents

| Mistake | How This Process Prevents It |
|---------|------------------------------|
| Mockup proportions don't match browser | Step 1 requires real Hoverify measurements |
| Columns overflow or wrap | Step 4 uses fixed pixels with math verification |
| Font too large/small | Step 3 enforces 5-10px range |
| Sidebar/topbar wrong size | Step 3 locks these as constants |
| Implementation differs from mockup | Step 7 documents exact values for code |

---

## Integration with Other Skills

This skill feeds into:
- **pc-ui-implementation** — Mockup approval is Step 4-5 of that process
- **qa-verify** — Screenshot comparison uses mockup as reference
- **cowork-prompt** — Cowork screenshots verify mockup accuracy

---

## Project Reference

- Dashboard: ~/Projects/my-assistant/templates/dashboard.html
- Hoverify: Chrome extension for element measurement
- Sidebar: 96px fixed width
- Topbar: 27px fixed height
- Design was created on external display (higher resolution than MacBook Pro)
- Responsive zoom fix: zoom = h / DESIGN_HEIGHT where DESIGN_HEIGHT = 1298
