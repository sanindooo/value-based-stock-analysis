---
title: "feat: Integrate universal framework learnings into CEDOE template"
type: feat
status: completed
date: 2026-05-15
---

# feat: Integrate universal framework learnings into CEDOE template

## Summary

Add universal, reusable assets to the CEDOE template — a hardened execution script starter, a directive starter, a solution doc starter, enhanced CLAUDE.md standards with "why" context, a runnable example, and process learnings — so the next project built from this template inherits hard-won knowledge from day one instead of rediscovering the same bugs across multiple build phases.

---

## Problem Frame

The CEDOE template was extracted from a working email marketing project that went through 3 build phases, 5 multi-agent code reviews, and produced 5 solution docs. During template conversion, the execution script standards were distilled into CLAUDE.md as "what" rules — but the "why" context, prevention checklists, Python-specific gotchas, and structural templates were lost.

The most critical finding across all 3 phases: **the same vulnerability classes (SSRF, path traversal, insecure permissions, missing structured output) recurred in every phase because new scripts were written from scratch**. Phase 1 found and fixed SSRF + path traversal. Phase 2 found the exact same patterns in new code. Phase 3 found PII + suppression gaps. The CLAUDE.md rules tell agents *what* to do, but without a hardened script template, each new script starts from zero.

Secondary gaps: the GETTING_STARTED.md tutorial describes a weather API example but the actual files don't exist, directive structure evolved across 4 iterations but was never codified, solution docs follow a consistent pattern but no template exists, and universal process learnings (like "deferred decisions need explicit triggers" and "review agent diversity catches different bug classes") live only in deleted git history.

---

## Requirements

- R1. New execution scripts must start from a hardened template containing all security helpers, so vulnerability classes don't recur across phases
- R2. CLAUDE.md must include Python-specific gotchas and "why" context behind execution standards, mirrored to AGENTS.md and GEMINI.md
- R3. Directive structure must be codified in a reusable template reflecting the mature pattern that evolved over 4 directives
- R4. The GETTING_STARTED tutorial must include actual runnable files, not just code blocks to copy
- R5. Solution doc format must be standardized via template so the compound loop produces consistent, searchable learnings
- R6. Universal process learnings must be preserved in the template's compound engineering configuration

---

## Scope Boundaries

- Email marketing content: ICP models, Apollo/Prospeo/MillionVerifier specifics, GTM strategy, deliverability rules, cold email best practices
- Restoring deleted solution docs verbatim — the template ships with structure, not project-specific war stories
- Adding new execution scripts beyond the template and starter example
- Changing the 3-layer architecture itself
- Adding new dependencies to requirements.txt beyond what the starter example needs (it uses `requests` and `python-dotenv`, which are already there)

### Deferred to Follow-Up Work

- GitHub issue/PR templates (`.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`): useful but separate from framework learnings
- Stale worktree cleanup in `.claude/worktrees/`: operational housekeeping, not template content
- Renaming the branch from `feat/phase4-sequence-generation` to something accurate: separate decision

---

## Context & Research

### Relevant Code and Patterns

- `CLAUDE.md:95-133` — Existing Execution Script Standards (the distilled "what" rules)
- `GETTING_STARTED.md` — Tutorial with weather API example (code blocks only, no actual files)
- `compound-engineering.local.md` — Review agent config and DOE-aware review rules
- Git history at `b7e2a8e~1` — Pre-conversion project with 8 scripts, 4 directives, 5 solution docs showing mature patterns

### Institutional Learnings

All learnings are from the pre-conversion project (preserved in git history). Universal findings only:

1. **Recurring vulnerability pattern**: Same security bugs appeared in every phase because scripts were written from scratch. Fix: hardened template with helpers baked in
2. **Python gotchas in agent context**: `continue` in for-loops doesn't retry (advances iterator), `ThreadPoolExecutor` silently swallows exceptions, `sys.exit(1)` kills the agent process with no structured error
3. **Schema drift**: When new data producers are added without updating downstream consumers, things break silently. Prevention: checklists for adding new pipeline stages
4. **Formula injection whitespace bypass**: Checking only the first character isn't enough — Google Sheets strips leading whitespace, so `"\t=SUM(A1)"` bypasses protection
5. **`os.rename()` not atomic**: Replace with `os.replace()` which is guaranteed atomic when target exists
6. **PII amplification chain**: Each pipeline step makes data more sensitive; apply security proportionally
7. **Deferred decisions with triggers**: Not just "later" but "revisit when [specific condition]"
8. **Review agent diversity**: Different agent archetypes catch different bug classes — `agent-native-reviewer` caught missing structured success output, `security-sentinel` caught SSRF, `learnings-researcher` surfaced relevant past solutions
9. **Compound loop effectiveness**: The learnings-researcher successfully surfaced Phase 1 solutions during Phase 2 review, proving the documentation loop works — but recurrence still happened because no proactive template existed

---

## Key Technical Decisions

- **Template file naming**: Use `_template.py` / `_template.md` prefix (underscore convention signals "not a real script/directive, copy and rename"). This keeps templates discoverable in `execution/` and `directives/` alongside real files without confusion
- **Starter example uses Open-Meteo API**: No API key required, genuinely free, well-documented. The GETTING_STARTED.md currently references `weatherapi.com` which requires an API key — switching to Open-Meteo removes the signup friction for new users
- **Python gotchas go in CLAUDE.md, not a separate doc**: They are execution-time rules that agents need at authoring time. Separate docs risk not being read. Keeping them in CLAUDE.md alongside the standards they complement ensures they're always loaded
- **Process learnings go in compound-engineering.local.md**: This is where compound engineering context lives. Review agents read this file. Process insights about review agent diversity, the deferred-decisions pattern, and checklist discipline belong here so they inform future plan and review cycles

---

## Open Questions

### Resolved During Planning

- **Should the starter example use a paid API?**: No — Open-Meteo is free with no API key, reducing friction. The weather API in GETTING_STARTED.md already demonstrates the pattern; we just need to make the files real and switch to a key-free API
- **Should we include example solution docs?**: No — the template provides structure (via `_template.md`), not project-specific content. The first real solution doc in a new project serves as the example

### Deferred to Implementation

- **Exact helper function signatures**: The template will follow the patterns from the pre-conversion scripts (`_error_exit()`, `_safe_path()`, `_validate_url()`, `_redact_pii()`, `_atomic_write()`), but exact signatures may adjust during implementation
- **Open-Meteo API response structure**: Need to verify the exact JSON shape at implementation time to write the example script

---

## Implementation Units

### U1. Add Python gotchas and enhanced "why" context to CLAUDE.md

**Goal:** Strengthen the Execution Script Standards section with Python-specific gotchas, "why" context, and an explicit instruction to use the script template — so agents understand the failure modes behind the rules and are directed to start from `_template.py` when creating new scripts.

**Requirements:** R1, R2

**Dependencies:** U2 (the template must exist before the instruction to use it is added; implement the CLAUDE.md instruction pointing to `execution/_template.py` after U2 creates it)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `GEMINI.md`

**Approach:**
Add three changes to CLAUDE.md:
1. **Template usage instruction** — Add to Operating Principles or the top of Execution Script Standards: "When creating a new execution script, always start by copying `execution/_template.py` and removing helpers you don't need. Never write a script from scratch." This closes the gap between "template exists" and "agents use it."
2. **Python Gotchas** — three specific pitfalls discovered across 3 build phases: for-loop `continue` not retrying, `ThreadPoolExecutor` swallowing exceptions, `sys.exit(1)` killing agent processes
3. **Why These Rules Exist** — brief "why" annotations on the most non-obvious existing rules: formula injection whitespace bypass, `os.replace()` over `os.rename()`, PII amplification chain as a pipeline design principle, schema drift prevention

All changes must be mirrored identically across the three files.

**Patterns to follow:**
- Existing CLAUDE.md structure and tone (concise, bullet-point, practical)
- The "Why this works" pattern already used in the 3-Layer Architecture section

**Test scenarios:**
- Happy path: All three files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) have identical content after changes
- Happy path: Searching CLAUDE.md for "execution/_template.py" finds the template usage instruction
- Edge case: New subsections integrate cleanly with the existing "Agent-Native Output", "Security", "Performance", and "API Integration Patterns" subsections without breaking the document flow

**Verification:**
- `diff CLAUDE.md AGENTS.md` and `diff CLAUDE.md GEMINI.md` produce no differences (confirming files remain synchronized)
- New content is findable by searching for "Python Gotchas" in any of the three files
- Template usage instruction is present in Operating Principles or Execution Script Standards

---

### U2. Create execution script template

**Goal:** Provide a hardened starter file that new execution scripts can be copied from, with all security helpers, structured output, and standard patterns baked in — eliminating the recurring-vulnerability problem.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `execution/_template.py`

**Approach:**
Build a copy-and-rename starter containing:
- Standard header: shebang, docstring with usage examples placeholder, imports
- `PROJECT_ROOT` and `load_dotenv` setup
- Logging configuration
- All security helpers: `_safe_path()` (path sandboxing), `_validate_url()` (SSRF protection), `_error_exit()` (structured JSON errors), `_redact_pii()` (email/phone masking for logs), `_atomic_write()` (temp file + `os.replace()` with `0o600` permissions)
- `argparse` skeleton with `--mock` and `--dry-run` flags
- `main()` function with structured JSON success output
- Inline comments marking which helpers to keep/remove based on the script's needs (e.g., "remove if not making HTTP requests")

The template follows the actual structure from the pre-conversion project's most mature scripts (`prospeo_enrich.py`, `email_validator.py`), not a theoretical ideal.

**Patterns to follow:**
- `prospeo_enrich.py` structure (git history at `b7e2a8e~1`) — the most complete example with all patterns
- `GETTING_STARTED.md` weather example — simpler but demonstrates the core pattern

**Test scenarios:**
- Happy path: Copy `_template.py` to `test_script.py`, run `python execution/test_script.py --help` — prints argparse help without errors
- Happy path: Run with `--mock` flag — produces structured JSON success output without calling any external API
- Edge case: `_safe_path()` rejects paths outside `.tmp/` (e.g., `--output /etc/passwd`)
- Edge case: `_validate_url()` rejects private network URLs (e.g., `http://169.254.169.254/`)
- Edge case: `_error_exit()` produces valid JSON with `status`, `error_code`, `message` keys and exits non-zero

**Verification:**
- Template runs without syntax errors (`python -c "import ast; ast.parse(open('execution/_template.py').read())"`)
- All security helpers are present and follow the patterns documented in CLAUDE.md Execution Script Standards

---

### U3. Create directive template

**Goal:** Codify the directive structure that evolved over 4 iterations into a reusable template, so new directives follow the mature pattern from day one.

**Requirements:** R3

**Dependencies:** None

**Files:**
- Create: `directives/_template.md`

**Approach:**
Build a copy-and-rename starter with all sections from the mature directive pattern:
- `# Directive: [Name]` title
- `## Goal` — one paragraph describing what this directive accomplishes
- `## When to Use` — criteria or comparison with other directives
- `## Inputs` — what the orchestrator provides
- `## Outputs` — files produced, side effects, where deliverables go
- `## Workflow` — numbered steps with exact CLI commands in code blocks
- `## Edge Cases` — table format: Situation | Handling
- `## Notes & Learnings` — living section, starts empty, grows as the directive is used

Each section includes a brief placeholder comment explaining what belongs there. The template should make it obvious that:
- Directives define WHAT, not HOW — they tell the agent which script to run
- Edge cases are documented proactively
- The Notes & Learnings section is the self-annealing surface — agents update it when they discover constraints

**Patterns to follow:**
- `enrich_leads.md` (retrieve via `git show b7e2a8e~1:directives/enrich_leads.md`) — most mature directive with credit budgets, workflow steps, and edge cases
- `discover_leads.md` (retrieve via `git show b7e2a8e~1:directives/discover_leads.md`) — good example of filter mapping tables and API constraint documentation

**Test scenarios:**
- Happy path: Template is valid Markdown that renders correctly
- Happy path: All 7 sections are present with placeholder content

**Verification:**
- Template contains all standard sections (Goal, When to Use, Inputs, Outputs, Workflow, Edge Cases, Notes & Learnings)
- No project-specific content remains — all placeholders are generic

---

### U4. Create solution doc template

**Goal:** Standardize the solution doc format so the compound loop produces consistent, searchable learnings across projects.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Create: `docs/solutions/_template.md`

**Approach:**
Build a starter with the YAML frontmatter pattern used across all 5 pre-conversion solution docs:
- Frontmatter: `title`, `date`, `category`, `tags`, `affected_files`, `directives`, `scripts`, `severity`
- Body sections: Problem Statement, Investigation, Root Cause, Fixes Applied, Prevention Checklist
- The Prevention Checklist section is the most important — it's the actionable output that future learnings-researcher agents surface. Structure as a table: Check | What | Why

Include a note about category subdirectory convention (`docs/solutions/<category>/filename.md`).

**Patterns to follow:**
- `phase3-enrichment-validation-code-review-fixes.md` frontmatter (retrieve via `git show b7e2a8e~1:docs/solutions/security-issues/phase3-enrichment-validation-code-review-fixes.md`)
- `outbound-pipeline-phase-1-foundation.md` body structure (retrieve via `git show b7e2a8e~1:docs/solutions/pipeline-architecture/outbound-pipeline-phase-1-foundation.md`)

**Test scenarios:**
- Happy path: Template has valid YAML frontmatter that parses without error
- Happy path: All 5 body sections are present with placeholder content

**Verification:**
- Frontmatter contains all standard fields
- Prevention Checklist section exists with the table format (Check | What | Why)

---

### U5. Create runnable starter example

**Goal:** Make the GETTING_STARTED.md tutorial produce actual files that users can run immediately, demonstrating the full DOE pattern with a working directive + script pair.

**Requirements:** R4

**Dependencies:** U2 (the example script should follow the template's patterns), U3 (the example directive should follow the template's structure)

**Files:**
- Create: `execution/fetch_weather.py`
- Create: `directives/check_weather.md`
- Modify: `GETTING_STARTED.md`

**Approach:**
- Create `execution/fetch_weather.py` using Open-Meteo's geocoding + forecast API (no API key needed). The script should demonstrate all the patterns from the `_template.py`: structured JSON output, path sandboxing, `--mock` mode, argparse, error handling
- Create `directives/check_weather.md` following the `_template.md` structure with real content for the weather use case
- Update `GETTING_STARTED.md` to reference the actual files instead of inline code blocks. Keep the tutorial structure but change it from "create these files" to "look at these files and understand the patterns, then try running them"

Switch from `weatherapi.com` (requires API key) to Open-Meteo (free, no key). This eliminates the setup friction that would stop new users from trying the example.

**Patterns to follow:**
- U2's `_template.py` for the script structure
- U3's `_template.md` for the directive structure
- Existing `GETTING_STARTED.md` tone and tutorial flow

**Test scenarios:**
- Happy path: `python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json` produces structured JSON success output and creates the file
- Happy path: `python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json --mock` produces structured JSON without hitting the network
- Edge case: Invalid city name returns structured JSON error with appropriate error code
- Edge case: `--output /etc/passwd` is rejected by path sandboxing
- Error path: Network timeout returns structured JSON error (not a stack trace)

**Verification:**
- Both files exist at the paths referenced in GETTING_STARTED.md
- The script runs successfully with `--mock` flag (no network dependency for verification)
- GETTING_STARTED.md references actual files rather than inline code blocks

---

### U6. Update compound-engineering.local.md with universal process learnings

**Goal:** Preserve universal process learnings in the compound engineering configuration so they inform future plan, review, and compound cycles across any project built from this template.

**Requirements:** R6

**Dependencies:** U2 (the template must exist before review rules can reference it)

**Files:**
- Modify: `compound-engineering.local.md`

**Approach:**
Two additions to `compound-engineering.local.md`:

**1. New `## Review Enforcement Rules` section** in the existing Rules for Reviews area. This is the enforcement layer — review agents catch what slips through:
- When reviewing new scripts in `execution/`, verify they include: path sandboxing (`_safe_path()` or equivalent), structured JSON output on all code paths (success and error), `--mock` flag for scripts calling external APIs. Flag any new script missing these as P1.
- When reviewing new scripts, check whether the script started from `execution/_template.py`. If it appears to have been written from scratch (missing standard helpers, no structured error output, no path validation), flag as P1 with the fix: "Copy `execution/_template.py` and adapt rather than writing from scratch."

**2. New `## Process Learnings` section** capturing universal insights:
- **Recurring vulnerability prevention**: Same bug classes recur across phases when scripts are written from scratch. Three-layer defense: template (proactive), CLAUDE.md instruction (directive), code review enforcement (catch). All three layers are required — any single layer alone has failed in practice.
- **Review agent diversity**: Different agent archetypes catch different bug classes. Document what each configured agent is best at catching (security-sentinel → SSRF/path traversal/PII, code-simplicity-reviewer → dead code/premature abstraction, performance-oracle → N+1/unbatched calls). Suggest `agent-native-reviewer` as a fourth review agent for projects where scripts are called by AI agents.
- **Deferred decisions with explicit triggers**: When deferring a decision during brainstorm or planning, always document the specific condition that triggers revisiting it (e.g., "revisit if bounce rate exceeds 3%"), not just "later"
- **Compound loop validation**: The learnings-researcher agent surfacing past solutions during review proves the documentation loop works — but proactive application (templates, checklists) is needed alongside reactive surfacing
- **Checklist discipline**: Prevention checklists at the end of solution docs are more actionable than prose rules. Encourage this format in the solution doc template

**Patterns to follow:**
- Existing `compound-engineering.local.md` structure (YAML frontmatter, Review Context section, Rules subsections)

**Test scenarios:**
- Happy path: Review enforcement rules are present and reference `execution/_template.py`
- Happy path: Process Learnings section is well-structured Markdown
- Edge case: Content is universal — no email-marketing-specific references
- Integration: A review agent reading the updated `compound-engineering.local.md` would know to flag a new script missing path sandboxing as P1

**Verification:**
- No references to specific tools (Apollo, Prospeo, MillionVerifier, Instantly, etc.)
- Review enforcement rules explicitly name the three required patterns (path sandboxing, structured JSON, --mock)
- Process learnings are actionable guidance, not historical narrative

---

## System-Wide Impact

- **Interaction graph:** GETTING_STARTED.md references `execution/fetch_weather.py` and `directives/check_weather.md`. The tutorial flow depends on both files existing. CLAUDE.md/AGENTS.md/GEMINI.md are mirrored — changes to one must be reflected in all three
- **Error propagation:** The starter example (`fetch_weather.py`) demonstrates the error propagation pattern — structured JSON errors that agents can parse. This is a teaching artifact, not production infrastructure
- **State lifecycle risks:** None — this work adds static template files and documentation. No runtime state, no data persistence, no migrations
- **API surface parity:** CLAUDE.md, AGENTS.md, and GEMINI.md must remain identical after changes. This is the existing convention and the most likely source of drift
- **Unchanged invariants:** The 3-layer architecture, directory structure, `.env` convention, `.tmp/` ephemeral files convention, and self-annealing loop are all unchanged. This plan strengthens how new projects bootstrap onto the existing architecture, not the architecture itself

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| CLAUDE.md/AGENTS.md/GEMINI.md drift after changes | U1 verification step: diff all three files after editing. Existing README.md already documents the mirroring convention |
| Script template becomes stale as Python/dependency versions change | Template uses only stdlib + `requests` + `python-dotenv` (already in requirements.txt). No version-sensitive patterns |
| Open-Meteo API changes or goes down | Starter example has `--mock` mode for offline use. Open-Meteo has been stable since 2022 and is widely used |
| Template file naming (`_template.*`) conflicts with future tooling | Underscore prefix is a Python convention for "private/internal". If conflicts arise, rename to `TEMPLATE.*` (uppercase signals non-executable) |

---

## Sources & References

- Git history at `b7e2a8e~1`: Pre-conversion project with 8 scripts, 4 directives, 5 solution docs
- `CLAUDE.md:95-133`: Existing Execution Script Standards
- `GETTING_STARTED.md`: Current tutorial (code blocks only)
- `compound-engineering.local.md`: Current review agent config
