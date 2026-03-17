# AGENTS.md

## Role
You are executing against an existing project plan. Do not change architecture, libraries, folder structure, or naming conventions unless explicitly told.

## Hard rules
- Do not deviate from the stated plan.
- Do not introduce extra features.
- Do not refactor unrelated code.
- Do not rename files or functions unless required.
- Before editing, restate the exact subtask you are executing.
- After editing, show:
  1. Files changed
  2. Why each change was necessary
  3. Test result
  4. Any assumptions made

## Execution process
1. Read the spec first.
2. Identify only the files relevant to the current subtask.
3. Make the smallest valid change.
4. Run the required tests.
5. Stop after completion and wait for next instruction.

## If blocked
- Report the blocker precisely.
- Propose the smallest fix.
- Do not improvise beyond the current plan.

## Coding standards
- Follow existing style in the repo (Flask/Python backend, vanilla JS/HTML/CSS frontend).
- Prefer minimal diffs.
- Preserve backward compatibility unless told otherwise.
- Never push to GitHub mid-session — commit locally only.
