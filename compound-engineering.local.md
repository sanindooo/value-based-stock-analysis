---
review_agents: [code-simplicity-reviewer, security-sentinel, performance-oracle]
plan_review_agents: [code-simplicity-reviewer]
---

# Review Context

## Architecture: 3-Layer System

This project uses a directive/orchestration/execution architecture. The LLM (Layer 2) orchestrates between human-written SOPs (Layer 1) and deterministic Python scripts (Layer 3). This separation exists because LLMs are probabilistic and business logic requires consistency.

- `directives/` — SOPs in Markdown. Before building anything, check if a directive already exists. Directives define goals, inputs, tools/scripts to use, outputs, and edge cases.
- `execution/` — Deterministic Python scripts. These handle API calls, data processing, file operations, database interactions. Always prefer calling an existing script over writing inline logic.
- `.tmp/` — Intermediate files only. Never commit. Always regenerated.
- `.env` — Environment variables and API keys.
- Deliverables go to cloud services (Google Sheets, Slides), not local files.

## Rules for Plans

When creating plans in `docs/plans/`:
- Always list which existing directives in `directives/` are relevant to the work
- Always list which existing execution scripts in `execution/` will be used or need to be created
- If a directive doesn't exist for the workflow being planned, note that one needs to be created as part of the plan
- Reference the self-annealing principle: new scripts should be tested and directives updated with learnings
- Check `docs/solutions/` for past learnings that apply to the current plan

## Rules for Solutions

When writing solutions in `docs/solutions/`:
- If the learning affects an operational workflow, ALSO update the relevant directive in `directives/`
- Tag solutions with which directives and scripts they relate to
- Solutions capture the "why" and the broader pattern; directives capture the "how"
- Include enough context that the learnings-researcher agent can surface this solution for similar future issues

## Rules for Reviews

- Check that new code follows the 3-layer separation (no API calls in orchestration logic—those belong in `execution/` scripts)
- Verify that new scripts have corresponding directive references
- Flag any hardcoded credentials (should be in `.env`)
- Check that deliverables target cloud services, not local files
- Ensure `.tmp/` is used for any intermediate file output

### Review Enforcement Rules

When reviewing new scripts in `execution/`, verify all of the following. Flag any missing item as P1:

1. **Path sandboxing** — `_safe_path()` or equivalent is used for all file path arguments. Must validate that resolved paths are under `PROJECT_ROOT/.tmp/`
2. **Structured JSON output** — all code paths (success AND error) emit parseable JSON to stdout. Stack traces and bare `print()` statements are not acceptable — agents can't parse them
3. **`--mock` flag** — present for any script that calls an external API. Must produce realistic structured output without network calls

When a new script appears to be written from scratch (missing standard helpers, no structured error output, no path validation), flag as P1 with the fix: "Copy `execution/_template.py` and adapt rather than writing from scratch."

## Process Learnings

### Recurring Vulnerability Prevention

Same bug classes (SSRF, path traversal, missing structured output, PII in logs) recurred across 3 consecutive build phases when scripts were written from scratch. The fix is a three-layer defense:
1. **Template** (proactive) — `execution/_template.py` bakes in all security helpers
2. **CLAUDE.md instruction** (directive) — agents are told to start from the template
3. **Code review enforcement** (catch) — review agents flag scripts missing required patterns

All three layers are required. Any single layer alone has failed in practice — templates exist but agents skip them, instructions exist but agents write from scratch anyway, reviews catch issues but only after wasted effort.

### Review Agent Diversity

Different agent archetypes catch different bug classes. Recommended roster and what each catches:
- **security-sentinel** — SSRF, path traversal, PII exposure, injection
- **code-simplicity-reviewer** — dead code, premature abstraction, unused imports
- **performance-oracle** — N+1 queries, unbatched API calls, unnecessary loops

For projects where scripts are called by AI agents, add **agent-native-reviewer** — catches missing structured output, non-parseable error messages, and success paths that emit nothing.

### Deferred Decisions Need Explicit Triggers

When deferring a decision during brainstorm or planning, always document the specific condition that triggers revisiting it (e.g., "revisit if bounce rate exceeds 3%"), not just "later." Decisions deferred without triggers tend to be forgotten until they cause problems.

### Compound Loop Validation

The learnings-researcher agent surfacing past solution docs during review proves the documentation loop works. But reactive surfacing alone is insufficient — proactive application through templates and checklists prevents the bug from being written in the first place. Both sides of the loop (proactive prevention + reactive surfacing) are needed.

### Prevention Checklists Over Prose

Prevention checklists at the end of solution docs (table format: Check | What | Why) are more actionable than prose explanations. Encourage this format when writing solution docs — the learnings-researcher agent can surface checklist items directly into review feedback.
