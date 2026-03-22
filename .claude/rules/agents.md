# Agent Delegation Rules

Use subagents to keep the main conversation context clean.

## Auto-delegate (no user prompt needed):
- Need to find something in the codebase -> Use pc-explorer agent
- About to commit code -> Use pc-verifier agent
- Starting a multi-step feature -> Use planner agent
- Code just written/modified -> Use code-reviewer agent
- Build or runtime error -> Use build-error-resolver agent
- Before pushing to Railway -> Use security-reviewer agent

## Parallel execution:
When tasks are independent, launch multiple agents in parallel.
Example: Run code-reviewer AND security-reviewer simultaneously before a commit.

## Context preservation:
Subagents run in their own context window. Use them for exploration
and verbose operations to keep the main session clean.
